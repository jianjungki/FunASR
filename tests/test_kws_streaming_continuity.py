"""KWS public streaming contracts with production overlap and no model weights."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import soundfile as sf
import torch

from funasr.auto.auto_model import AutoModel
from funasr.frontends.wav_frontend import WavFrontendOnline
from funasr.models.sanm_kws_streaming.model import SanmKWSStreaming
from funasr.models.scama.encoder import SANMEncoderChunkOpt
from funasr.models.transformer.embedding import StreamSinusoidalPositionEncoder
from funasr.utils.load_utils import extract_fbank


class MarkerFrontend:
    """One feature per complete 960-sample block; never invent short-input frames."""

    fs, frame_shift, lfr_n, n_mels, lfr_m = 16000, 10, 6, 1, 1

    def __call__(self, audio, lengths, cache, is_final=False, **kwargs):
        samples = torch.cat((cache.get("samples", audio[:, :0]), audio), dim=1)
        count = samples.shape[1] // 960
        features = samples[:, : count * 960 : 960, None].clone()
        cache["samples"] = samples[:, count * 960 :].clone()
        return features, torch.tensor([count])


class IdentityChunkEncoder(SANMEncoderChunkOpt):
    """Keep the real forward_chunk and overlap cache, replacing acoustic layers."""

    def __init__(self):
        torch.nn.Module.__init__(self)
        self.embed = None
        self.encoders0 = torch.nn.ModuleList()
        self.encoders = torch.nn.ModuleList()
        self.normalize_before = False

    def output_size(self):
        return 1


class RecordingDecoder:
    def __init__(self, ctc, **kwargs):
        self.state = ctc

    def decode(self, features):
        self.state.frames.append(features.detach().clone())
        return self.state.detected, "wake", 0.9


class FourDimFrontend(MarkerFrontend):
    n_mels = 4

    def __call__(self, *args, **kwargs):
        features, lengths = super().__call__(*args, **kwargs)
        return features.repeat(1, 1, 4), lengths


class ContextLayer(torch.nn.Module):
    def forward_chunk(self, features, state, chunk_size, look_back):
        return features + 0.01 * features.mean(dim=1, keepdim=True), state


class PositionedEncoder(IdentityChunkEncoder):
    def __init__(self, contextual=False):
        super().__init__()
        self.embed = StreamSinusoidalPositionEncoder()
        if contextual:
            self.encoders0.append(ContextLayer())
        self.positions = []

    def output_size(self):
        return 4

    def forward_chunk(self, features, lengths, cache, **kwargs):
        before = cache["start_idx"]
        result = super().forward_chunk(features, lengths, cache, **kwargs)
        self.positions.append((before, cache["start_idx"]))
        return result


class LightweightKws(SanmKWSStreaming):
    def __init__(self, detected=True):
        torch.nn.Module.__init__(self)
        self.anchor = torch.nn.Parameter(torch.zeros(1))
        self.encoder = IdentityChunkEncoder()
        self.specaug = self.normalize = None
        self.ctc = SimpleNamespace(frames=[], detected=detected)
        self.eval()


class KwsStreamingContinuityTest(unittest.TestCase):
    def setUp(self):
        p = patch("funasr.utils.kws_utils.KwsCtcPrefixDecoder", RecordingDecoder)
        p.start()
        self.addCleanup(p.stop)

    def setup_model(self, frontend=None, detected=True, chunk_size=None):
        model = LightweightKws(detected)
        frontend = frontend or MarkerFrontend()
        config = {
            "device": "cpu",
            "batch_size": 1,
            "disable_pbar": True,
            "keywords": "wake",
            "chunk_size": chunk_size or [4, 8, 4],
            "encoder_conf": {"output_size": 1},
            "frontend_conf": {"n_mels": frontend.n_mels, "lfr_m": frontend.lfr_m},
            "frontend": frontend,
            "tokenizer": SimpleNamespace(token_list=["wake"], seg_dict={}),
        }
        wrapper = AutoModel.__new__(AutoModel)
        wrapper.model = model
        wrapper.kwargs = config
        wrapper.vad_model = wrapper.punc_model = None
        wrapper._store_base_configs()
        self.addCleanup(
            lambda: model.writer.close() if hasattr(model, "writer") else None
        )
        return model, wrapper, config

    @staticmethod
    def markers(frames):
        return torch.arange(1, frames + 1, dtype=torch.float32).repeat_interleave(960)

    def stream(self, wrapper, audio, pieces, empty_flush=False, **kwargs):
        cache = {}
        offset, index = 0, 0
        while offset < len(audio):
            end = min(len(audio), offset + pieces[index % len(pieces)])
            final = end == len(audio) and not empty_flush
            result = wrapper.generate(
                input=audio[offset:end],
                cache=cache,
                key="sample",
                is_final=final,
                **kwargs
            )
            if not final:
                self.assertEqual(result, [])
                self.assertFalse(cache["encoder"]["tail_chunk"])
            offset, index = end, index + 1
        if empty_flush or len(audio) == 0:
            result = wrapper.generate(
                input=audio[:0], cache=cache, key="sample", is_final=True, **kwargs
            )
        self.assertEqual(cache["prev_samples"].numel(), 0)
        self.assertIsNone(cache["encoder"]["encoder_out"])
        return result

    def test_public_nonfinal_contract_and_unflushed_cache(self):
        model, wrapper, config = self.setup_model()
        cache = {}
        results, metadata = model.inference(
            [self.markers(12)], key=["sample"], cache=cache, is_final=False, **config
        )
        self.assertEqual(results, [])
        self.assertIsInstance(metadata, dict)
        self.assertFalse(cache["encoder"]["tail_chunk"])
        self.assertEqual(model.ctc.frames, [])
        self.assertEqual(
            wrapper.generate(
                input=self.markers(12), cache={}, key="sample", is_final=False
            ),
            [],
        )

    def test_complete_inputs_keep_each_valid_frame_once(self):
        for frames in (1, 3, 4, 5, 7, 8, 9, 12, 13, 16, 20, 21, 32, 37):
            with self.subTest(frames=frames):
                model, wrapper, _ = self.setup_model()
                self.assertEqual(
                    self.stream(wrapper, self.markers(frames), [100000]),
                    [{"key": "sample", "text": "detected wake 0.9"}],
                )
                self.assertEqual(len(model.ctc.frames), 1)
                torch.testing.assert_close(
                    model.ctc.frames[0][:, 0],
                    torch.arange(1, frames + 1, dtype=torch.float32),
                )

    def test_partitions_and_empty_flush_preserve_marker_frames(self):
        for pieces in ([959], [960], [3840], [7680], [1, 959, 3001, 7000]):
            for empty_flush in (False, True):
                with self.subTest(pieces=pieces, empty_flush=empty_flush):
                    model, wrapper, _ = self.setup_model()
                    self.stream(wrapper, self.markers(37), pieces, empty_flush)
                    self.assertEqual(len(model.ctc.frames), 1)
                    torch.testing.assert_close(
                        model.ctc.frames[0][:, 0],
                        torch.arange(1, 38, dtype=torch.float32),
                    )

    def test_empty_and_insufficient_audio_do_not_fabricate_detection(self):
        for length in (0, 1, 399, 959):
            with self.subTest(length=length):
                model, wrapper, _ = self.setup_model()
                self.assertEqual(self.stream(wrapper, torch.ones(length), [100]), [])
                self.assertEqual(model.ctc.frames, [])

    def test_final_output_once_and_second_utterance_starts_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            model, wrapper, _ = self.setup_model(detected=False)
            cache = {}
            for key in ("first", "second"):
                self.assertEqual(
                    wrapper.generate(
                        input=self.markers(12),
                        cache=cache,
                        key=key,
                        is_final=False,
                        output_dir=directory,
                    ),
                    [],
                )
                if key == "first":
                    self.assertFalse((Path(directory) / "detect").exists())
                result = wrapper.generate(
                    input=self.markers(5),
                    cache=cache,
                    key=key,
                    is_final=True,
                    output_dir=directory,
                )
                self.assertEqual(result, [{"key": key, "text": "rejected"}])
                self.assertIsNone(cache["encoder"]["encoder_out"])
            self.assertEqual(
                (Path(directory) / "detect").read_text(),
                "first rejected\nsecond rejected\n",
            )
            self.assertEqual(len(model.ctc.frames), 2)
            torch.testing.assert_close(model.ctc.frames[0], model.ctc.frames[1])

    def test_file_input_finalizes_even_when_flag_is_false(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "markers.wav"
            sf.write(path, self.markers(21).numpy(), 16000, subtype="FLOAT")
            model, wrapper, _ = self.setup_model()
            self.assertEqual(
                wrapper.generate(
                    input=str(path), cache={}, key="sample", is_final=False
                ),
                [{"key": "sample", "text": "detected wake 0.9"}],
            )
            torch.testing.assert_close(
                model.ctc.frames[0][:, 0], torch.arange(1, 22, dtype=torch.float32)
            )

    def test_real_frontend_frames_match_complete_audio_and_partitions(self):
        def frontend():
            return WavFrontendOnline(n_mels=8, lfr_m=7, lfr_n=6, dither=0.0)

        for length in (
            0,
            399,
            400,
            559,
            560,
            879,
            960,
            3839,
            3840,
            3841,
            11520,
            12479,
            12480,
            15360,
            15361,
            19199,
            40000,
        ):
            with self.subTest(length=length):
                time = torch.arange(length, dtype=torch.float32) / 16000
                audio = 0.1 * torch.sin(2 * torch.pi * (300 * time + 100 * time**2))
                expected, lengths = extract_fbank(
                    [audio], frontend=frontend(), cache={}, is_final=True
                )
                count = int(lengths[0]) if lengths.numel() else 0
                fbank_count = max(0, 1 + (length - 400) // 160)
                self.assertEqual(count, (fbank_count + 5) // 6)
                for pieces in ([100000], [1, 959, 3001, 7000]):
                    model, wrapper, _ = self.setup_model(frontend())
                    result = self.stream(wrapper, audio, pieces, empty_flush=True)
                    if not count:
                        self.assertEqual(result, [])
                        self.assertEqual(model.ctc.frames, [])
                    else:
                        self.assertEqual(len(model.ctc.frames), 1)
                        torch.testing.assert_close(
                            model.ctc.frames[0],
                            expected[0, :count],
                            rtol=1e-5,
                            atol=1e-5,
                        )

    def test_real_position_encoding_covers_prefix_and_never_reembeds_overlap(self):
        for pieces in ([100000], [1, 959, 3001, 7000]):
            with self.subTest(pieces=pieces):
                model, wrapper, _ = self.setup_model(FourDimFrontend())
                model.encoder = PositionedEncoder()
                self.stream(wrapper, self.markers(37), pieces, empty_flush=True)
                raw = torch.arange(1, 38, dtype=torch.float32)[None, :, None].repeat(
                    1, 1, 4
                )
                expected = StreamSinusoidalPositionEncoder()(raw * 2, {"start_idx": 0})
                torch.testing.assert_close(model.ctc.frames[0], expected[0])
                self.assertEqual(
                    sum(end - start for start, end in model.encoder.positions), 37
                )

    def test_context_sensitive_windows_are_independent_of_packet_and_final_boundaries(
        self,
    ):
        for frames in (12, 13, 19, 20, 21, 28, 37):
            reference = None
            for pieces, empty_flush in (
                ([100000], False),
                ([100000], True),
                ([959, 3841], False),
            ):
                with self.subTest(
                    frames=frames, pieces=pieces, empty_flush=empty_flush
                ):
                    model, wrapper, _ = self.setup_model(FourDimFrontend())
                    model.encoder = PositionedEncoder(contextual=True)
                    self.stream(wrapper, self.markers(frames), pieces, empty_flush)
                    observed = model.ctc.frames[0]
                    if reference is None:
                        reference = observed
                    else:
                        torch.testing.assert_close(observed, reference)

    def test_asymmetric_and_zero_overlap_chunk_shapes(self):
        for chunk_size in ([0, 8, 4], [2, 8, 4], [4, 8, 0], [0, 8, 0]):
            with self.subTest(chunk_size=chunk_size):
                model, wrapper, _ = self.setup_model(chunk_size=chunk_size)
                self.stream(wrapper, self.markers(24), [959, 3841], empty_flush=True)
                torch.testing.assert_close(
                    model.ctc.frames[0][:, 0], torch.arange(1, 25, dtype=torch.float32)
                )

    def test_real_sanm_convolution_handles_exact_stride_endings(self):
        for chunk_size in ([0, 8, 0], [4, 8, 0], [4, 8, 4]):
            reference = None
            for pieces in ([100000], [959, 3841]):
                with self.subTest(chunk_size=chunk_size, pieces=pieces):
                    model, wrapper, _ = self.setup_model(
                        FourDimFrontend(), chunk_size=chunk_size
                    )
                    torch.manual_seed(23)
                    model.encoder = SANMEncoderChunkOpt(
                        input_size=4,
                        output_size=4,
                        attention_heads=2,
                        linear_units=8,
                        num_blocks=1,
                        kernel_size=3,
                        input_layer="pe_online",
                        dropout_rate=0.0,
                        positional_dropout_rate=0.0,
                        attention_dropout_rate=0.0,
                    ).eval()
                    self.stream(wrapper, self.markers(24), pieces, empty_flush=True)
                    observed = model.ctc.frames[0]
                    self.assertEqual(observed.shape, (24, 4))
                    if reference is None:
                        reference = observed
                    else:
                        torch.testing.assert_close(observed, reference)

    def test_short_final_frontend_waveforms_align_to_real_samples(self):
        for lfr_m, lfr_n in ((7, 6), (5, 1)):
            for length in (0, 399, 400, 559, 560, 879, 960, 12479):
                for pieces in ([100000], [1, 399, 401]):
                    with self.subTest(lfr=(lfr_m, lfr_n), length=length, pieces=pieces):
                        frontend = WavFrontendOnline(
                            n_mels=8, lfr_m=lfr_m, lfr_n=lfr_n, dither=0.0
                        )
                        audio = torch.linspace(-0.1, 0.1, length)
                        cache, offset, emitted, index = {}, 0, 0, 0
                        while offset < length:
                            end = min(length, offset + pieces[index % len(pieces)])
                            features, _ = frontend(
                                audio[None, offset:end],
                                [end - offset],
                                cache=cache,
                                is_final=False,
                                return_waveform=True,
                            )
                            if features.ndim == 3 and features.shape[1]:
                                count = features.shape[1]
                                start = emitted * lfr_n * 160
                                stop = start + (count - 1) * lfr_n * 160 + 400
                                torch.testing.assert_close(
                                    cache["aligned_waveforms"], audio[None, start:stop]
                                )
                                emitted += count
                            offset, index = end, index + 1
                        features, _ = frontend(
                            audio[None, :0],
                            [0],
                            cache=cache,
                            is_final=True,
                            return_waveform=True,
                        )
                        if features.ndim == 3 and features.shape[1]:
                            count = features.shape[1]
                            start = emitted * lfr_n * 160
                            stop = start + (count - 1) * lfr_n * 160 + 400
                            self.assertLessEqual(stop, length)
                            torch.testing.assert_close(
                                cache["aligned_waveforms"], audio[None, start:stop]
                            )
                            emitted += count
                        fbank_count = max(0, 1 + (length - 400) // 160)
                        self.assertEqual(emitted, (fbank_count + lfr_n - 1) // lfr_n)

    def test_short_nonempty_eos_aligns_final_waveform(self):
        for lfr_m, lfr_n in ((7, 6), (5, 1)):
            for length in (399, 400, 559, 560, 879, 960, 12479):
                with self.subTest(lfr=(lfr_m, lfr_n), length=length):
                    frontend = WavFrontendOnline(
                        n_mels=8, lfr_m=lfr_m, lfr_n=lfr_n, dither=0.0
                    )
                    audio = torch.linspace(-0.1, 0.1, length)
                    cache = {}
                    features, _ = frontend(
                        audio[None],
                        [length],
                        cache=cache,
                        is_final=True,
                        return_waveform=True,
                    )
                    fbank_count = max(0, 1 + (length - 400) // 160)
                    count = (fbank_count + lfr_n - 1) // lfr_n
                    if not count:
                        self.assertEqual(features.numel(), 0)
                        self.assertEqual(cache["aligned_waveforms"].numel(), 0)
                    else:
                        self.assertEqual(features.shape[1], count)
                        stop = (count - 1) * lfr_n * 160 + 400
                        self.assertLessEqual(stop, length)
                        torch.testing.assert_close(
                            cache["aligned_waveforms"], audio[None, :stop]
                        )


if __name__ == "__main__":
    unittest.main()
