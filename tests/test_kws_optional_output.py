"""Exercise production KWS output handling without loading acoustic models."""

import itertools
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import torch

from funasr.models.fsmn_kws.model import FsmnKWS
from funasr.models.fsmn_kws_mt.model import FsmnKWSMT
from funasr.models.sanm_kws.model import SanmKWS
from funasr.models.sanm_kws_streaming.model import SanmKWSStreaming


class FixedDecoder:
    def __init__(self, ctc, keywords=None, token_list=None, seg_dict=None):
        self.result = ctc

    def decode(self, encoder_out):
        return self.result


VARIANTS = (FsmnKWS, FsmnKWSMT, SanmKWS, SanmKWSStreaming)
OMITTED = object()


class KwsOptionalOutputTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.patch_decoder = patch(
            "funasr.utils.kws_utils.KwsCtcPrefixDecoder", FixedDecoder
        )
        self.patch_decoder.start()
        self.addCleanup(self.patch_decoder.stop)

    def model(self, variant, detected=True, detected2=False):
        result = (detected, "wake", 0.9)
        model = SimpleNamespace(ctc=result, ctc2=(detected2, "hello", 0.8))
        model.encode = lambda speech, lengths: (speech, lengths)
        if variant is FsmnKWSMT:
            model.encode = lambda speech, lengths: (speech, speech, lengths)
        model.encode_chunk = lambda speech, lengths, **kwargs: (speech, lengths)
        model.kws_decoder = FixedDecoder(result)
        self.addCleanup(
            lambda: model.writer.close() if hasattr(model, "writer") else None
        )
        return model

    def call(
        self, variant, model, output_dir=OMITTED, key="sample", final=True, cache=None
    ):
        kwargs = {"device": "cpu", "data_type": "fbank", "keywords": "wake"}
        if output_dir is not OMITTED:
            kwargs["output_dir"] = output_dir
        speech = torch.zeros(1, 3, 1)
        lengths = torch.tensor([3])
        tokenizer = SimpleNamespace(token_list=["wake"], seg_dict={})
        if variant is FsmnKWSMT:
            tokenizer = [tokenizer, tokenizer]
        if variant is SanmKWSStreaming:
            if cache is None:
                cache = {
                    "encoder": {
                        "chunk_size": [0, 3, 0],
                        "encoder_out": None,
                        "encoder_out_lens": None,
                    }
                }
            return variant.generate_chunk(
                model,
                speech,
                lengths,
                key=[key],
                tokenizer=tokenizer,
                cache=cache,
                is_final=final,
                **kwargs,
            )
        results, _ = variant.inference(
            model,
            speech,
            data_lengths=lengths[:, None],
            key=[key],
            tokenizer=tokenizer,
            **kwargs,
        )
        return results

    def expected(self, variant, detected=True, detected2=False, key="sample"):
        result = {"key": key, "text": "detected wake 0.9" if detected else "rejected"}
        if variant is FsmnKWSMT:
            result["text2"] = "detected hello 0.8" if detected2 else "rejected"
        return [result]

    def test_omitted_and_none_return_results_without_creating_writer(self):
        for variant, detected, detected2, output_dir in itertools.product(
            VARIANTS, (False, True), (False, True), (OMITTED, None)
        ):
            with self.subTest(
                variant=variant.__name__,
                detected=detected,
                detected2=detected2,
                output_dir=output_dir,
            ):
                model = self.model(variant, detected, detected2)
                self.assertEqual(
                    self.call(variant, model, output_dir),
                    self.expected(variant, detected, detected2),
                )
                self.assertFalse(hasattr(model, "writer"))

    def test_enabled_output_preserves_result_and_file_format(self):
        for variant, detected, detected2 in itertools.product(
            VARIANTS, (False, True), (False, True)
        ):
            with self.subTest(
                variant=variant.__name__, detected=detected, detected2=detected2
            ):
                path = (
                    Path(self.directory.name)
                    / f"{variant.__name__}-{detected}-{detected2}"
                )
                model = self.model(variant, detected, detected2)
                expected = self.expected(variant, detected, detected2)
                self.assertEqual(self.call(variant, model, str(path)), expected)
                self.assertEqual(
                    (path / "detect").read_text(), f"sample {expected[0]['text']}\n"
                )
                if variant is FsmnKWSMT:
                    self.assertEqual(
                        (path / "detect2").read_text(),
                        f"sample {expected[0]['text2']}\n",
                    )

    def test_disabled_output_does_not_reuse_cached_writer(self):
        for variant, output_dir in itertools.product(VARIANTS, (OMITTED, None)):
            with self.subTest(variant=variant.__name__, output_dir=output_dir):
                path = (
                    Path(self.directory.name)
                    / f"{variant.__name__}-{output_dir is None}"
                )
                model = self.model(variant)
                self.call(variant, model, str(path), key="first")
                before = {p.name: p.read_bytes() for p in path.iterdir()}
                self.assertEqual(
                    self.call(variant, model, output_dir, key="second"),
                    self.expected(variant, key="second"),
                )
                self.assertEqual(
                    {p.name: p.read_bytes() for p in path.iterdir()}, before
                )

    def test_consecutive_enabled_calls_append(self):
        for variant in VARIANTS:
            with self.subTest(variant=variant.__name__):
                path = Path(self.directory.name) / variant.__name__
                model = self.model(variant)
                for key in ("first", "second"):
                    self.call(variant, model, str(path), key=key)
                self.assertEqual(
                    (path / "detect").read_text(),
                    "first detected wake 0.9\nsecond detected wake 0.9\n",
                )
                if variant is FsmnKWSMT:
                    self.assertEqual(
                        (path / "detect2").read_text(),
                        "first rejected\nsecond rejected\n",
                    )

    def test_streaming_nonfinal_accumulates_and_final_returns_without_output(self):
        model = self.model(SanmKWSStreaming)
        cache = {
            "encoder": {
                "chunk_size": [0, 3, 0],
                "encoder_out": None,
                "encoder_out_lens": None,
            }
        }
        self.assertIsNone(self.call(SanmKWSStreaming, model, final=False, cache=cache))
        self.assertFalse(hasattr(model, "writer"))
        self.assertEqual(
            self.call(SanmKWSStreaming, model, final=True, cache=cache),
            self.expected(SanmKWSStreaming),
        )
        self.assertEqual(cache["encoder"]["encoder_out"].shape[1], 6)
        self.assertFalse(hasattr(model, "writer"))


if __name__ == "__main__":
    unittest.main()
