"""Run both published KWS examples with a recording SDK double, not weights."""

import ast
import shlex
import sys
import types
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from markdown import markdown

ROOT = Path(__file__).resolve().parents[1]


def test_bilingual_guides_exist():
    for name in ("keyword_spotting.md", "keyword_spotting_zh.md"):
        assert (ROOT / "docs" / name).is_file()


@pytest.mark.parametrize("name", ["keyword_spotting.md", "keyword_spotting_zh.md"])
def test_pinned_install_replaces_an_existing_same_version(name):
    soup = BeautifulSoup(markdown((ROOT / "docs" / name).read_text(), extensions=["fenced_code"]), "html.parser")
    commands = [shlex.split(line) for line in soup.select_one("code.language-sh").get_text().splitlines() if line.strip()]
    assert commands == [
        ["python", "-m", "pip", "uninstall", "-y", "funasr"],
        ["python", "-m", "pip", "install", "funasr @ git+https://github.com/modelscope/FunASR.git@403555289a6d4f79f5c4a48e5beb00f521c5e172"],
    ]


class Audio:
    ndim = 1

    def __init__(self, length, start=0):
        self.length = length
        self.start = start

    def __len__(self):
        return self.length

    def __getitem__(self, item):
        start, end, step = item.indices(self.length)
        assert step == 1
        return Audio(end - start, self.start + start)


@pytest.fixture(params=["keyword_spotting.md", "keyword_spotting_zh.md"])
def guide(request):
    path = ROOT / "docs" / request.param
    assert path.is_file(), f"Missing runnable guide: {path}"
    soup = BeautifulSoup(markdown(path.read_text(), extensions=["fenced_code"]), "html.parser")
    blocks = soup.select("code.language-python")
    assert len(blocks) == 1
    code = blocks[0].get_text()
    ast.parse(code)
    return compile(code, str(path), "exec")


def run_guide(guide, monkeypatch, tmp_path, length=1921, rate=16000, mode="stream", ndim=1):
    calls, constructors = [], []
    speech = Audio(length)
    speech.ndim = ndim
    model_dir = tmp_path / "checkpoint"
    model_dir.mkdir(exist_ok=True)

    class Model:
        def __init__(self, **kwargs):
            constructors.append(kwargs)

        def generate(self, **kwargs):
            calls.append(kwargs)
            # Simulate SDK mutation of the very same caller-owned dictionary.
            kwargs["cache"]["calls"] = kwargs["cache"].get("calls", 0) + 1
            if kwargs["is_final"]:
                return [{"key": "demo", "text": "detected 小云小云 0.900"}]
            return []

    monkeypatch.setitem(sys.modules, "funasr", types.SimpleNamespace(AutoModel=Model))
    monkeypatch.setitem(sys.modules, "soundfile", types.SimpleNamespace(read=lambda *a, **k: (speech, rate)))
    monkeypatch.setattr(sys, "argv", ["kws.py", str(model_dir), "positive.wav", "--mode", mode])
    scope = {"__name__": "__main__"}
    exec(guide, scope)
    return scope, calls, constructors


@pytest.mark.parametrize("length,sizes", [(1, [1]), (960, [960]), (961, [960, 1]), (1920, [960, 960])])
def test_full_stream_entry_point(guide, monkeypatch, tmp_path, capsys, length, sizes):
    _, calls, constructors = run_guide(guide, monkeypatch, tmp_path, length=length)
    assert [len(call["input"]) for call in calls] == sizes
    assert [call["input"].start for call in calls] == list(range(0, length, 960))
    assert [call["is_final"] for call in calls] == [False] * (len(sizes) - 1) + [True]
    assert all(call["cache"] is calls[0]["cache"] for call in calls)
    assert all(call["chunk_size"] == [4, 8, 4] and call["batch_size"] == 1 and call["fs"] == 16000 for call in calls)
    assert constructors[0]["keywords"] == "小云小云"
    assert constructors[0]["device"] == "cpu"
    assert constructors[0]["trust_remote_code"] is False
    assert "output_dir" not in constructors[0]
    assert "detected 小云小云" in capsys.readouterr().out


def test_file_mode_is_one_complete_utterance(guide, monkeypatch, tmp_path):
    _, calls, _ = run_guide(guide, monkeypatch, tmp_path, mode="file")
    assert len(calls) == 1 and calls[0]["input"] == "positive.wav"
    assert calls[0]["is_final"] is True


@pytest.mark.parametrize("length,rate,ndim", [(0, 16000, 1), (960, 8000, 1), (960, 16000, 2)])
def test_invalid_audio_is_rejected(guide, monkeypatch, tmp_path, length, rate, ndim):
    with pytest.raises(ValueError, match="nonempty mono 16 kHz"):
        run_guide(guide, monkeypatch, tmp_path, length=length, rate=rate, ndim=ndim)


def test_second_session_gets_a_new_cache(guide, monkeypatch, tmp_path):
    scope, calls, _ = run_guide(guide, monkeypatch, tmp_path)
    first_cache = calls[0]["cache"]
    first_count = len(calls)
    scope["detect_stream"](scope["model"], Audio(960), 16000)
    assert len(calls) == first_count + 1
    assert calls[-1]["cache"] is not first_cache


def test_invalid_packet_size_rejected(guide, monkeypatch, tmp_path):
    scope, _, _ = run_guide(guide, monkeypatch, tmp_path)
    for size in (0, -1):
        with pytest.raises(ValueError, match="positive"):
            scope["detect_stream"](scope["model"], Audio(960), 16000, packet_samples=size)
