"""Model-free tests for the real Gradio UI and multipart HTTP client."""

import importlib.util
import json
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import wave

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gradio_app", ROOT / "examples/openai_api/gradio_app.py"
)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "sample.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\x00\x00" * 1600)
    return path


@pytest.fixture
def endpoint():
    state = {
        "requests": [],
        "status": 200,
        "metadata": True,
        "payload": {
            "text": "\u4f60\u597d",
            "segments": [
                {"start": 0, "end": 0.5, "text": "\u4f60", "speaker": "speaker_0"},
                {"start": 0.5, "end": 1, "text": "\u597d", "speaker": 1},
                {"text": "[S02] untouched", "speaker": None},
            ],
        },
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            state["requests"].append(("GET", self.path, {}))
            self.reply(200 if state["metadata"] else 404, {"path": self.path})

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            message = BytesParser(policy=policy.default).parsebytes(
                ("Content-Type: " + self.headers["Content-Type"] + "\r\n\r\n").encode() + body
            )
            fields = {
                part.get_param("name", header="content-disposition"): part.get_payload(decode=True)
                for part in message.iter_parts()
            }
            state["requests"].append(("POST", self.path, fields))
            self.reply(state["status"], state["payload"])

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()


def component(demo, label):
    matches = [item for item in demo.config["components"] if item["props"].get("label") == label]
    assert len(matches) == 1
    return matches[0]["props"]


@pytest.mark.parametrize(
    "backend,model,formats,default_format",
    [
        ("funasr", "sensevoice", ["json", "verbose_json"], "verbose_json"),
        ("vllm", "moss-transcribe-diarize", ["json", "diarized_json"], "diarized_json"),
        ("sglang-omni", "OpenMOSS-Team/MOSS-Transcribe-Diarize", ["verbose_json"], "verbose_json"),
    ],
)
def test_real_ui_backend_contract(backend, model, formats, default_format):
    demo = app.build_app("http://127.0.0.1:8000", 300, backend=backend)
    try:
        model_control = component(demo, "Model alias")
        assert model_control["value"] == model
        choices = [choice[1] for choice in model_control["choices"]]
        assert model in choices
        if backend == "sglang-omni":
            assert model_control["choices"] == [("MOSS-Transcribe-Diarize", model)]
        if backend == "funasr":
            assert choices == ["sensevoice", "paraformer", "paraformer-en", "fun-asr-nano", "moss-transcribe-diarize"]
        response = component(demo, "Response format")
        assert [choice[0] for choice in response["choices"]] == formats
        assert response["value"] == default_format
        assert component(demo, "API base URL")["value"] == "http://127.0.0.1:8000"
        for label in ["API base URL", "Model alias", "Response format", "Timeout seconds"]:
            assert component(demo, label)["min_width"] >= 240
        assert component(demo, "Audio")["type"] == "filepath"
    finally:
        demo.close()


def test_original_build_app_call_remains_supported():
    demo = app.build_app("http://127.0.0.1:8000", 300)
    try:
        assert component(demo, "Model alias")["value"] == "sensevoice"
        assert component(demo, "Response format")["value"] == "verbose_json"
    finally:
        demo.close()


@pytest.mark.parametrize("backend", ["funasr", "vllm", "sglang-omni"])
def test_served_model_override_is_exact(backend):
    demo = app.build_app("http://127.0.0.1:8000", 300, backend=backend, default_model="operator/custom-model")
    try:
        control = component(demo, "Model alias")
        assert control["value"] == "operator/custom-model"
        assert "operator/custom-model" in [choice[1] for choice in control["choices"]]
    finally:
        demo.close()


def test_cli_profile_and_model_defaults(monkeypatch):
    for name in ["BASE_URL", "GRADIO_HOST", "GRADIO_PORT", "TIMEOUT"]:
        monkeypatch.delenv(name, raising=False)
    args = app.parse_args([])
    assert (args.backend, args.model, args.host, args.port, args.share) == ("funasr", None, "127.0.0.1", 7860, False)
    args = app.parse_args(["--backend", "vllm", "--model", "served-id", "--base-url", "http://127.0.0.1:8898"])
    assert (args.backend, args.model, args.base_url) == ("vllm", "served-id", "http://127.0.0.1:8898")
    with pytest.raises(SystemExit):
        app.parse_args(["--backend", "not-a-backend"])


@pytest.mark.parametrize("model,format_", [
    ("moss-transcribe-diarize", "verbose_json"),
    ("moss-transcribe-diarize", "diarized_json"),
    ("OpenMOSS-Team/MOSS-Transcribe-Diarize", "verbose_json"),
    ("operator/custom-model", "json"),
])
def test_real_http_preserves_fields_and_response(endpoint, audio, model, format_):
    url, state = endpoint
    transcript, raw = app.transcribe_audio(url + "/", str(audio), model, format_, 5)
    assert transcript == state["payload"]["text"]
    assert json.loads(raw) == state["payload"]
    assert state["requests"] == [("POST", "/v1/audio/transcriptions", {
        "file": audio.read_bytes(), "model": model.encode(), "response_format": format_.encode(),
    })]


@pytest.mark.parametrize("payload", [{"text": "only text"}, {"text": "", "segments": []}, {"segments": [{"text": "[S00] raw"}]}])
def test_no_speaker_or_segment_fabrication(endpoint, audio, payload):
    url, state = endpoint
    state["payload"] = payload
    text, raw = app.transcribe_audio(url, str(audio), "moss-transcribe-diarize", "verbose_json", 5)
    assert text == payload.get("text", "")
    assert json.loads(raw) == payload


def test_optional_metadata_failure_does_not_gate_transcription(endpoint, audio):
    url, state = endpoint
    state["metadata"] = False
    assert "HTTP 404" in app.safe_check(url, 5)
    text, raw = app.safe_transcribe(url, str(audio), "moss-transcribe-diarize", "diarized_json", 5)
    assert text == state["payload"]["text"]
    assert json.loads(raw) == state["payload"]


def test_service_check_and_http_failure(endpoint, audio):
    url, state = endpoint
    assert json.loads(app.check_service(url, 5)) == {
        "health": {"path": "/health"}, "models": {"path": "/v1/models"},
    }
    state["status"] = 422
    state["payload"] = {"detail": "unsupported model"}
    text, raw = app.safe_transcribe(url, str(audio), "bad-model", "verbose_json", 5)
    assert text == ""
    assert "HTTP 422" in raw and "unsupported model" in raw


def test_missing_audio_never_calls_backend(endpoint):
    url, state = endpoint
    assert app.safe_transcribe(url, None, "sensevoice", "json", 5)[0] == ""
    assert state["requests"] == []


@pytest.mark.parametrize("backend,model,format_", [
    ("funasr", "moss-transcribe-diarize", "verbose_json"),
    ("vllm", "moss-transcribe-diarize", "diarized_json"),
    ("sglang-omni", "OpenMOSS-Team/MOSS-Transcribe-Diarize", "verbose_json"),
])
def test_live_gradio_upload_and_event_binding(endpoint, audio, backend, model, format_):
    from gradio_client import Client, handle_file

    url, state = endpoint
    demo = app.build_app(url, 5, backend=backend, default_model=model)
    try:
        _, local_url, _ = demo.launch(server_name="127.0.0.1", prevent_thread_lock=True, quiet=True)
        client = Client(local_url, verbose=False)
        transcript, raw = client.predict(url, handle_file(str(audio)), model, format_, 5, api_name="/safe_transcribe")
        assert transcript == state["payload"]["text"]
        assert json.loads(raw) == state["payload"]
        post = state["requests"][-1]
        assert post[:2] == ("POST", "/v1/audio/transcriptions")
        assert post[2]["model"] == model.encode()
        assert post[2]["response_format"] == format_.encode()
        assert post[2]["file"] == audio.read_bytes()
    finally:
        demo.close()
