#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
# Copyright FunASR (https://github.com/alibaba-damo-academy/FunASR). All Rights Reserved.
#  MIT License  (https://opensource.org/licenses/MIT)

import time
import torch
import logging
from typing import Dict, Tuple
from contextlib import contextmanager
from distutils.version import LooseVersion

from funasr.register import tables
from funasr.models.ctc.ctc import CTC
from funasr.utils import postprocess_utils
from funasr.metrics.compute_acc import th_accuracy
from funasr.utils.datadir_writer import DatadirWriter
from funasr.models.sanm_kws.model import SanmKWS
from funasr.models.paraformer.search import Hypothesis
from funasr.models.paraformer.cif_predictor import mae_loss
from funasr.train_utils.device_funcs import force_gatherable
from funasr.losses.label_smoothing_loss import LabelSmoothingLoss
from funasr.models.transformer.utils.add_sos_eos import add_sos_eos
from funasr.models.transformer.utils.nets_utils import make_pad_mask, pad_list
from funasr.utils.load_utils import load_audio_text_image_video, extract_fbank


if LooseVersion(torch.__version__) >= LooseVersion("1.6.0"):
    from funasr.utils.amp import autocast
else:
    # Nothing to do if torch<1.6.0
    @contextmanager
    def autocast(enabled=True):
        """Autocast.
        
            Args:
                enabled: TODO.
            """
        yield


@tables.register("model_classes", "SanmKWSStreaming")
class SanmKWSStreaming(SanmKWS):
    """
    Author: Speech Lab of DAMO Academy, Alibaba Group
    Paraformer: Fast and Accurate Parallel Transformer for Non-autoregressive End-to-End Speech Recognition
    https://arxiv.org/abs/2206.08317
    """

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        """Initialize SanmKWSStreaming.
        
            Args:
                *args: Variable positional arguments.
                **kwargs: Additional keyword arguments.
            """
        super().__init__(*args, **kwargs)

    def forward(
        self,
        speech: torch.Tensor,
        speech_lengths: torch.Tensor,
        text: torch.Tensor,
        text_lengths: torch.Tensor,
        **kwargs,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor], torch.Tensor]:
        """Encoder + Decoder + Calc loss
        Args:
                speech: (Batch, Length, ...)
                speech_lengths: (Batch, )
                text: (Batch, Length)
                text_lengths: (Batch,)
        """
        decoding_ind = kwargs.get("decoding_ind")
        if len(text_lengths.size()) > 1:
            text_lengths = text_lengths[:, 0]
        if len(speech_lengths.size()) > 1:
            speech_lengths = speech_lengths[:, 0]

        batch_size = speech.shape[0]

        # Encoder
        if hasattr(self.encoder, "overlap_chunk_cls"):
            ind = self.encoder.overlap_chunk_cls.random_choice(self.training, decoding_ind)
            encoder_out, encoder_out_lens = self.encode(speech, speech_lengths, ind=ind)
        else:
            encoder_out, encoder_out_lens = self.encode(speech, speech_lengths)

        # decoder: CTC branch
        if hasattr(self.encoder, "overlap_chunk_cls"):
            encoder_out_ctc, encoder_out_lens_ctc = self.encoder.overlap_chunk_cls.remove_chunk(
                encoder_out, encoder_out_lens, chunk_outs=None
            )
        else:
            encoder_out_ctc, encoder_out_lens_ctc = encoder_out, encoder_out_lens

        loss_ctc, cer_ctc = self._calc_ctc_loss(
            encoder_out_ctc, encoder_out_lens_ctc, text, text_lengths
        )

        # Collect CTC branch stats
        stats = dict()
        stats["loss_ctc"] = loss_ctc.detach() if loss_ctc is not None else None
        stats["cer_ctc"] = cer_ctc

        loss = loss_ctc

        stats["cer"] = cer_ctc
        stats["loss"] = torch.clone(loss.detach())

        # force_gatherable: to-device and to-tensor if scalar for DataParallel
        loss, stats, weight = force_gatherable((loss, stats, batch_size), loss.device)
        return loss, stats, weight

    def encode_chunk(
        self,
        speech: torch.Tensor,
        speech_lengths: torch.Tensor,
        cache: dict = None,
        **kwargs,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Encode chunk.
        
            Args:
                speech: Speech audio tensor, shape (batch, time).
                speech_lengths: Length of each speech sample.
                cache: State cache dict for streaming inference.
                **kwargs: Additional keyword arguments.
            """
        if cache is None:
            cache = {}
        """Frontend + Encoder. Note that this method is used by asr_inference.py
        Args:
                speech: (Batch, Length, ...)
                speech_lengths: (Batch, )
                ind: int
        """
        with autocast(False):
            # Data augmentation
            if self.specaug is not None and self.training:
                speech, speech_lengths = self.specaug(speech, speech_lengths)

            # Normalization for feature: e.g. Global-CMVN, Utterance-CMVN
            if self.normalize is not None:
                speech, speech_lengths = self.normalize(speech, speech_lengths)

        # Forward encoder
        encoder_out, encoder_out_lens, _ = self.encoder.forward_chunk(
            speech, speech_lengths, cache=cache["encoder"]
        )

        if isinstance(encoder_out, tuple):
            encoder_out = encoder_out[0]

        return encoder_out, torch.tensor([encoder_out.size(1)])

    def init_cache(self, cache: dict = None, **kwargs):
        """Init cache.
        
            Args:
                cache: State cache dict for streaming inference.
                **kwargs: Additional keyword arguments.
            """
        if cache is None:
            cache = {}
        chunk_size = kwargs.get("chunk_size", [0, 10, 5])
        encoder_chunk_look_back = kwargs.get("encoder_chunk_look_back", 0)
        decoder_chunk_look_back = kwargs.get("decoder_chunk_look_back", 0)
        batch_size = 1

        enc_output_size = kwargs["encoder_conf"]["output_size"]
        feats_dims = kwargs["frontend_conf"]["n_mels"] * kwargs["frontend_conf"]["lfr_m"]
        cache_encoder = {
            "start_idx": 0,
            "cif_hidden": torch.zeros((batch_size, 1, enc_output_size)),
            "cif_alphas": torch.zeros((batch_size, 1)),
            "encoder_out": None,
            "encoder_out_lens": None,
            "chunk_size": chunk_size,
            "encoder_chunk_look_back": encoder_chunk_look_back,
            "last_chunk": False,
            "opt": None,
            "feats": torch.zeros((batch_size, chunk_size[0] + chunk_size[2], feats_dims)),
            "tail_chunk": False,
        }
        cache["encoder"] = cache_encoder

        cache_decoder = {
            "decode_fsmn": None,
            "decoder_chunk_look_back": decoder_chunk_look_back,
            "opt": None,
            "chunk_size": chunk_size,
        }
        cache["decoder"] = cache_decoder
        cache["frontend"] = {}
        cache["prev_samples"] = torch.empty(0)
        cache["pending_features"] = torch.empty((batch_size, 0, feats_dims))
        cache["frontend_started"] = False
        cache["encoder_started"] = False

        return cache

    def generate_chunk(
        self,
        speech,
        speech_lengths=None,
        key: list = None,
        tokenizer=None,
        frontend=None,
        **kwargs,
    ):
        """Generate chunk.
        
            Args:
                speech: Speech audio tensor, shape (batch, time).
                speech_lengths: Length of each speech sample.
                key: Sample identifiers.
                tokenizer: Tokenizer instance for text encoding/decoding.
                frontend: Audio frontend for feature extraction.
                **kwargs: Additional keyword arguments.
            """
        cache = kwargs.get("cache", {})
        speech = speech.to(device=kwargs["device"])
        speech_lengths = speech_lengths.to(device=kwargs["device"])

        is_final = kwargs.get("is_final", False)
        no_pending_context = (
            is_final
            and speech.shape[1] == 0
            and cache["encoder"]["chunk_size"][2] == 0
            and cache["encoder"]["encoder_out"] is not None
        )
        if no_pending_context:
            # Zero-right-context EOS only decodes output already committed.
            encoder_out_accum = cache["encoder"]["encoder_out"]
        else:
            encoder_out, encoder_out_lens = self.encode_chunk(
                speech, speech_lengths, cache=cache, is_final=is_final
            )
            if isinstance(encoder_out, tuple):
                encoder_out = encoder_out[0]

            chunk_size = cache["encoder"]["chunk_size"]
            real_start_pos = chunk_size[0]

            if encoder_out_lens[0] > chunk_size[0] + chunk_size[1] + chunk_size[2]:
                assert False, print("impossible case 1 !")
            if is_final and encoder_out_lens[0] >= real_start_pos:
                real_end_pos = encoder_out_lens[0]
            elif encoder_out_lens[0] == chunk_size[0] + chunk_size[1] + chunk_size[2]:
                real_end_pos = chunk_size[0] + chunk_size[1]
            elif encoder_out_lens[0] > chunk_size[0] + chunk_size[1]:
                real_end_pos = chunk_size[0] + chunk_size[1]
            elif encoder_out_lens[0] > chunk_size[0]:
                real_end_pos = encoder_out_lens[0]
            else:
                assert False, print("impossible case 2 !")

            encoder_out_accum = cache["encoder"]["encoder_out"]
            if encoder_out_accum is not None:
                encoder_out_accum = torch.cat((encoder_out_accum, encoder_out[:, real_start_pos:real_end_pos, :]), dim=1)
            else:
                encoder_out_accum = encoder_out[:, real_start_pos:real_end_pos, :]
            cache["encoder"]["encoder_out"] = encoder_out_accum

            if cache["encoder"]["encoder_out_lens"] is not None:
                cache["encoder"]["encoder_out_lens"][0] += real_end_pos - real_start_pos
            else:
                cache["encoder"]["encoder_out_lens"] = encoder_out_lens
                cache["encoder"]["encoder_out_lens"][0] = real_end_pos - real_start_pos

        if is_final:
            if kwargs.get("output_dir") is not None:
                if not hasattr(self, "writer"):
                    self.writer = DatadirWriter(kwargs.get("output_dir"))

            results = []
            for i in range(encoder_out_accum.size(0)):
                x = encoder_out_accum[i, : cache["encoder"]["encoder_out_lens"][i], :]
                detect_result = self.kws_decoder.decode(x)
                is_deted, det_keyword, det_score = detect_result[0], detect_result[1], detect_result[2]

                if is_deted:
                    det_info = "detected " + det_keyword + " " + str(det_score)
                else:
                    det_info = "rejected"

                if kwargs.get("output_dir") is not None:
                    self.writer["detect"][key[i]] = det_info

                result_i = {"key": key[i], "text": det_info}
                results.append(result_i)

            return results
        else:
            return None

    def _consume_streaming_features(
        self, speech, speech_lengths, key, tokenizer, frontend, cache, **kwargs
    ):
        """Commit canonical middle windows, then all remaining valid final frames."""
        pending = cache["pending_features"]
        if speech.numel():
            pending = torch.cat((pending, speech[:, : int(speech_lengths[0]), :]), dim=1)
        left, middle, right = cache["encoder"]["chunk_size"]
        needed = middle + (0 if cache["encoder_started"] else right)
        cache["encoder"]["tail_chunk"] = False
        while pending.shape[1] >= needed:
            if not cache["encoder_started"]:
                # Only left padding is synthetic; all real frames get preprocessing.
                cache["encoder"]["feats"] = cache["encoder"]["feats"][:, :left, :]
            block = pending[:, :needed, :].clone()
            self.generate_chunk(
                block, torch.tensor([needed]), key=key, tokenizer=tokenizer,
                frontend=frontend, cache=cache, **{**kwargs, "is_final": False},
            )
            cache["encoder_started"] = True
            if left + right == 0:
                cache["encoder"]["feats"] = cache["encoder"]["feats"][:, :0, :]
            pending = pending[:, needed:, :]
            needed = middle
        cache["pending_features"] = pending.clone()
        if not kwargs.get("is_final", False):
            return []
        if not cache["encoder_started"]:
            if pending.shape[1] == 0:
                return []
            cache["encoder"]["feats"] = cache["encoder"]["feats"][:, :left, :]
        # An empty new-feature tensor flushes preprocessed overlap without embedding it twice.
        return self.generate_chunk(
            pending.clone(), torch.tensor([pending.shape[1]]), key=key,
            tokenizer=tokenizer, frontend=frontend, cache=cache,
            **{**kwargs, "is_final": True},
        )

    def inference(
        self,
        data_in,
        data_lengths=None,
        key: list = None,
        tokenizer=None,
        frontend=None,
        cache: dict = None,
        **kwargs,
    ):
        """Consume audio packets and decode once at the end of an utterance.

        Array/tensor packets must share the same caller-owned cache. Nonfinal
        calls return an empty result list while retaining unconsumed audio and
        features. Finalization flushes valid frames, returns detection results,
        and resets cache fields in place. File/URL inputs finalize automatically.

        Args:
            data_in: Mono audio samples, a file path, or a URL.
            data_lengths: Optional input lengths.
            key: Utterance identifiers; batch size must be one.
            tokenizer: Keyword tokenizer with token_list and seg_dict.
            frontend: Streaming audio frontend.
            cache: Caller-owned state, reused until is_final=True.
            **kwargs: Includes device, keywords, is_final, and chunk_size
                [left, middle, right] in frontend feature frames.

        Returns:
            Tuple of a result list and timing metadata. Results are emitted
            only at utterance end; this is not a per-packet wake-event API.
        """
        if cache is None:
            cache = {}
        keywords = kwargs.get("keywords")
        from funasr.utils.kws_utils import KwsCtcPrefixDecoder
        self.kws_decoder = KwsCtcPrefixDecoder(
            ctc=self.ctc,
            keywords=keywords,
            token_list=tokenizer.token_list,
            seg_dict=tokenizer.seg_dict,
        )

        meta_data = {}
        chunk_size = kwargs["chunk_size"]
        if len(chunk_size) != 3 or chunk_size[0] < 0 or chunk_size[1] <= 0 or chunk_size[2] < 0:
            raise ValueError("chunk_size must be [left >= 0, middle > 0, right >= 0]")
        frame_stride_samples = int(frontend.fs * frontend.frame_shift * frontend.lfr_n / 1000)
        if frame_stride_samples <= 0:
            raise ValueError("frontend frame stride must be positive")

        if len(cache) == 0:
            self.init_cache(cache, **kwargs)

        time1 = time.perf_counter()
        cfg = {"is_final": kwargs.get("is_final", False)}
        audio_sample_list = load_audio_text_image_video(
            data_in,
            fs=frontend.fs,
            audio_fs=kwargs.get("fs", 16000),
            data_type=kwargs.get("data_type", "sound"),
            tokenizer=tokenizer,
            cache=cfg,
        )
        is_final = cfg["is_final"]
        time2 = time.perf_counter()
        meta_data["load_data"] = f"{time2 - time1:0.3f}"
        assert len(audio_sample_list) == 1, "batch_size must be set 1"
        incoming = audio_sample_list[0]
        if incoming.numel():
            meta_data["batch_data_time"] = incoming.numel() / frontend.fs
        audio = torch.cat((cache["prev_samples"], incoming))

        # Frontend calls and encoder windows do not depend on caller packet sizes.
        offset = 0
        while True:
            frames = chunk_size[1] + (0 if cache["frontend_started"] else chunk_size[2])
            sample_count = frames * frame_stride_samples
            if len(audio) - offset < sample_count:
                break
            speech, speech_lengths = extract_fbank(
                [audio[offset : offset + sample_count]],
                data_type=kwargs.get("data_type", "sound"),
                frontend=frontend,
                cache=cache["frontend"],
                is_final=False,
            )
            cache["frontend_started"] = True
            self._consume_streaming_features(
                speech, speech_lengths, key, tokenizer, frontend, cache,
                **{**kwargs, "is_final": False},
            )
            offset += sample_count

        cache["prev_samples"] = audio[offset:].clone()
        results = []
        if is_final:
            speech, speech_lengths = extract_fbank(
                [cache["prev_samples"]],
                data_type=kwargs.get("data_type", "sound"),
                frontend=frontend,
                cache=cache["frontend"],
                is_final=True,
            )
            results = self._consume_streaming_features(
                speech, speech_lengths, key, tokenizer, frontend, cache,
                **{**kwargs, "is_final": True},
            )
            self.init_cache(cache, **kwargs)

        meta_data["extract_feat"] = f"{time.perf_counter() - time2:0.3f}"
        return results, meta_data

    def export(self, **kwargs):
        """Export.
        
            Args:
                **kwargs: Additional keyword arguments.
            """
        from .export_meta import export_rebuild_model

        models = export_rebuild_model(model=self, **kwargs)
        return models
