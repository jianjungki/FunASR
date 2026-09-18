#!/usr/bin/env python3
"""Browser demo for the FunASR OpenAI-compatible API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
from pathlib import Path
import urllib.error
import urllib.request
import uuid

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_MODEL = "sensevoice"
BACKEND_PROFILES = {
    "funasr": {
        "models": (DEFAULT_MODEL, "paraformer", "paraformer-en", "fun-asr-nano", "moss-transcribe-diarize"),
        "formats": ("json", "verbose_json"),
        "default_format": "verbose_json",
    },
    "vllm": {
        "models": ("moss-transcribe-diarize",),
        "formats": ("json", "diarized_json"),
        "default_format": "diarized_json",
    },
    "sglang-omni": {
        "models": ("OpenMOSS-Team/MOSS-Transcribe-Diarize",),
        "formats": ("verbose_json",),
        "default_format": "verbose_json",
    },
}


def request_json(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def multipart_body(audio_path: Path, model: str, response_format: str) -> tuple[bytes, str]:
    boundary = f"----funasr-gradio-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(str(audio_path))[0] or "application/octet-stream"
    parts: list[bytes] = []

    def add_text(name: str, value: str) -> None:
        parts.append(
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n"
            ).encode("utf-8")
        )

    parts.append(
        (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{audio_path.name}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(audio_path.read_bytes())
    parts.append(b"\r\n")
    add_text("model", model)
    add_text("response_format", response_format)
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(parts), boundary


def transcribe_audio(base_url: str, audio_path: str | None, model: str, response_format: str, timeout: float) -> tuple[str, str]:
    if not audio_path:
        return "", "Upload or record an audio file first."

    base_url = base_url.rstrip("/")
    path = Path(audio_path)
    body, boundary = multipart_body(path, model, response_format)
    request = urllib.request.Request(
        f"{base_url}/v1/audio/transcriptions",
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    text = payload.get("text", "")
    return text, json.dumps(payload, ensure_ascii=False, indent=2)


def check_service(base_url: str, timeout: float) -> str:
    base_url = base_url.rstrip("/")
    health = request_json(f"{base_url}/health", timeout)
    models = request_json(f"{base_url}/v1/models", timeout)
    return json.dumps({"health": health, "models": models}, ensure_ascii=False, indent=2)


def safe_transcribe(base_url: str, audio_path: str | None, model: str, response_format: str, timeout: float) -> tuple[str, str]:
    try:
        return transcribe_audio(base_url, audio_path, model, response_format, timeout)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        return "", f"HTTP {error.code} from {error.url}: {detail}"
    except Exception as error:
        return "", f"Transcription failed: {error}"


def safe_check(base_url: str, timeout: float) -> str:
    try:
        return check_service(base_url, timeout)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        return f"HTTP {error.code} from {error.url}: {detail}"
    except Exception as error:
        return f"Service check failed: {error}"


def build_app(default_base_url: str, default_timeout: float, *, backend: str = "funasr", default_model: str | None = None):
    profile = BACKEND_PROFILES[backend]
    models = list(profile["models"])
    selected_model = default_model if default_model is not None else models[0]
    if selected_model not in models:
        models.append(selected_model)
    model_choices = [
        ("MOSS-Transcribe-Diarize" if value == "OpenMOSS-Team/MOSS-Transcribe-Diarize" else value, value)
        for value in models
    ]

    try:
        import gradio as gr
    except ImportError as error:
        raise SystemExit("Install Gradio in the client environment: python -m pip install gradio==6.26.0") from error

    with gr.Blocks(title="FunASR OpenAI API Demo") as demo:
        gr.Markdown("# FunASR OpenAI-Compatible API Demo")

        with gr.Row():
            base_url = gr.Textbox(label="API base URL", value=default_base_url, min_width=240)
            model = gr.Dropdown(
                label="Model alias",
                choices=model_choices,
                value=selected_model,
                min_width=240,
            )
            response_format = gr.Radio(label="Response format", choices=profile["formats"], value=profile["default_format"], min_width=240)
            timeout = gr.Number(label="Timeout seconds", value=default_timeout, precision=0, min_width=240)

        audio = gr.Audio(label="Audio", sources=["upload", "microphone"], type="filepath")
        with gr.Row():
            check_button = gr.Button("Check service")
            transcribe_button = gr.Button("Transcribe", variant="primary")

        transcript = gr.Textbox(label="Transcript", lines=6)
        raw_json = gr.Code(label="Raw JSON or status", language="json")

        check_button.click(fn=safe_check, inputs=[base_url, timeout], outputs=raw_json)
        transcribe_button.click(
            fn=safe_transcribe,
            inputs=[base_url, audio, model, response_format, timeout],
            outputs=[transcript, raw_json],
        )

    return demo


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Gradio demo for the FunASR OpenAI-compatible API")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", DEFAULT_BASE_URL), help="Backend origin without /v1; reached from the Gradio process")
    parser.add_argument("--backend", choices=tuple(BACKEND_PROFILES), default="funasr", help="Transcription protocol profile (native profiles default to MOSS)")
    parser.add_argument("--model", help="Exact served-model ID; overrides the profile's default model")
    parser.add_argument("--host", default=os.getenv("GRADIO_HOST", "127.0.0.1"), help="Gradio bind host")
    parser.add_argument("--port", type=int, default=int(os.getenv("GRADIO_PORT", "7860")), help="Gradio bind port")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("TIMEOUT", "300")), help="HTTP timeout in seconds")
    parser.add_argument("--share", action="store_true", help="Create a temporary Gradio share link")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    app = build_app(args.base_url, args.timeout, backend=args.backend, default_model=args.model)
    app.launch(server_name=args.host, server_port=args.port, share=args.share)


if __name__ == "__main__":
    main()
