"""Execute the bilingual recipe and the real rich-text presentation helper."""

import ast
import json
import os
import runpy
import sys
import types
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from markdown import markdown

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ["speaker_emotion.md", "speaker_emotion_zh.md"]


def test_bilingual_task_guides_exist():
    for name in GUIDES:
        assert (ROOT / "docs" / name).is_file()


@pytest.fixture(params=GUIDES)
def recipe(request):
    path = ROOT / "docs" / request.param
    soup = BeautifulSoup(markdown(path.read_text(), extensions=["fenced_code"]), "html.parser")
    blocks = soup.select("code.language-python")
    assert len(blocks) == 1
    ast.parse(blocks[0].get_text())
    return compile(blocks[0].get_text(), str(path), "exec")


class Waveform:
    ndim = 1

    def __init__(self, length=48000, ndim=1):
        self.length, self.ndim = length, ndim

    def __len__(self):
        return self.length


class Embedding:
    ndim = 2

    def __init__(self, rows=None):
        self.rows = [[0.25, -0.5, 0.75]] if rows is None else rows
        self.shape = (len(self.rows), len(self.rows[0]) if self.rows else 0)
        self.detached = self.on_cpu = False

    def detach(self):
        self.detached = True
        return self

    def cpu(self):
        self.on_cpu = True
        return self

    def tolist(self):
        assert self.detached and self.on_cpu
        return self.rows


def run_recipe(recipe, monkeypatch, tmp_path, task="embedding", results=None,
               sample_rate=16000, length=48000, ndim=1, output=None):
    model_dir = tmp_path / "checkpoint"
    model_dir.mkdir(exist_ok=True)
    constructors, calls = [], []
    if results is None:
        results = [{"spk_embedding": Embedding()}] if task == "embedding" else [
            {"key": "sample", "text": "<|zh|><|HAPPY|><|Speech|><|withitn|>你好"}
        ]

    class Model:
        def __init__(self, **kwargs):
            constructors.append(kwargs)

        def generate(self, **kwargs):
            calls.append(kwargs)
            return results

    helper = runpy.run_path(str(ROOT / "funasr/utils/postprocess_utils.py"))
    postprocess = types.ModuleType("funasr.utils.postprocess_utils")
    postprocess.rich_transcription_postprocess = helper["rich_transcription_postprocess"]
    monkeypatch.setitem(sys.modules, "funasr", types.SimpleNamespace(AutoModel=Model))
    monkeypatch.setitem(sys.modules, "funasr.utils", types.ModuleType("funasr.utils"))
    monkeypatch.setitem(sys.modules, "funasr.utils.postprocess_utils", postprocess)
    monkeypatch.setitem(sys.modules, "soundfile", types.SimpleNamespace(
        read=lambda *a, **k: (Waveform(length, ndim), sample_rate)))
    output = output or tmp_path / "result.json"
    monkeypatch.setattr(sys, "argv", ["attributes.py", task, str(model_dir), "speech.wav", str(output)])
    scope = {"__name__": "__main__"}
    exec(recipe, scope)
    return json.loads(output.read_text()), calls, constructors


def test_embedding_is_a_finite_cpu_serializable_vector_not_identity(recipe, monkeypatch, tmp_path):
    data, calls, constructors = run_recipe(recipe, monkeypatch, tmp_path)
    assert data["result"] == {"spk_embedding": [[0.25, -0.5, 0.75]]}
    assert "name" not in data["result"] and "text" not in data["result"]
    assert calls[0]["batch_size"] == 1 and calls[0]["fs"] == 16000
    assert "cache" not in calls[0] and "language" not in calls[0]
    assert constructors[0]["device"] == "cpu"
    assert constructors[0]["trust_remote_code"] is False
    assert all(constructors[0][p] is None for p in ("vad_model", "punc_model", "spk_model"))
    if os.name == "posix":
        assert (tmp_path / "result.json").stat().st_mode & 0o777 == 0o600


def test_raw_tags_survive_real_lossy_display_processing(recipe, monkeypatch, tmp_path):
    raw = "<|zh|><|HAPPY|><|Speech|><|withitn|>你好"
    data, calls, _ = run_recipe(recipe, monkeypatch, tmp_path, task="sensevoice", results=[{"key": "sample", "text": raw}])
    assert data["result"] == [{"key": "sample", "raw_tagged_text": raw, "display_text": "你好😊"}]
    assert calls[0]["language"] == "auto"
    assert calls[0]["use_itn"] is True and calls[0]["output_timestamp"] is False
    assert "return_raw_text" not in calls[0]


def test_multiple_sensevoice_results_are_preserved_in_order(recipe, monkeypatch, tmp_path):
    raw = ["<|en|><|NEUTRAL|><|Speech|><|withitn|>Hello", "<|zh|><|SAD|><|Speech|><|withitn|>再见"]
    data, _, _ = run_recipe(recipe, monkeypatch, tmp_path, task="sensevoice", results=[{"text": text} for text in raw])
    assert [item["raw_tagged_text"] for item in data["result"]] == raw
    assert all(item["key"] is None for item in data["result"])


@pytest.mark.parametrize("rate,length,ndim", [(8000, 48000, 1), (16000, 0, 1), (16000, 48000, 2)])
def test_invalid_audio_rejected(recipe, monkeypatch, tmp_path, rate, length, ndim):
    with pytest.raises(ValueError, match="nonempty mono 16 kHz"):
        run_recipe(recipe, monkeypatch, tmp_path, sample_rate=rate, length=length, ndim=ndim)
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("rows", [[], [[]], [[], []], [[1.0], [2.0]], [[float("nan")]]])
def test_invalid_embedding_is_not_published_as_json(recipe, monkeypatch, tmp_path, rows):
    with pytest.raises(ValueError):
        run_recipe(recipe, monkeypatch, tmp_path, results=[{"spk_embedding": Embedding(rows)}])
    assert not (tmp_path / "result.json").exists()


@pytest.mark.parametrize("task", ["embedding", "sensevoice"])
def test_empty_result_is_not_invented(recipe, monkeypatch, tmp_path, task):
    with pytest.raises(ValueError, match="No result"):
        run_recipe(recipe, monkeypatch, tmp_path, task=task, results=[])
    assert not (tmp_path / "result.json").exists()


def test_existing_output_is_not_overwritten(recipe, monkeypatch, tmp_path):
    path = tmp_path / "prior.json"
    path.write_text("existing result")
    with pytest.raises(FileExistsError):
        run_recipe(recipe, monkeypatch, tmp_path, output=path)
    assert path.read_text() == "existing result"


def test_malformed_rich_text_is_not_silently_discarded(recipe, monkeypatch, tmp_path):
    with pytest.raises(ValueError, match="Expected SenseVoice text"):
        run_recipe(recipe, monkeypatch, tmp_path, task="sensevoice", results=[{"text": 123}])
    assert not (tmp_path / "result.json").exists()
