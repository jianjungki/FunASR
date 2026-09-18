(English|[简体中文](README_zh.md)|[日本語](README_ja.md)|[한국어](README_ko.md))

# FunASR OpenAI-Compatible API Server

An OpenAI-style `/v1/audio/transcriptions` endpoint for private speech transcription. This example implements a speech API subset, not the entire OpenAI API or a compatibility guarantee for every SDK/framework feature.

This page starts the repository's [example server](server.py). The packaged `funasr-server` is a [different implementation](../../funasr/bin/_server_app.py); see [API boundaries](#api-contract) before reusing its settings. For in-process `AutoModel.generate()` rather than HTTP requests, use the [Python SDK guide](../../docs/python_api.md) ([中文](../../docs/python_api_zh.md)).

For the maintained packaged-service route, start with [Agent integration](../../docs/agent_integration.md). The example has **no built-in authentication or upload limit**; `api_key="not-needed"` does not authenticate it. Keep local testing on loopback. Before sharing, configure TLS, gateway authentication, upload/time/rate limits, audio/transcript retention, and private health/model/schema access using the [security guide](SECURITY.md).

## API Contract

- **Example `python server.py` in this directory:** startup and omitted multipart `model` both default to `sensevoice`. There is no `spk` form field; the example only preserves speaker labels already returned by the model.
- **Packaged `funasr-server`:** startup `--model auto` selects `fun-asr-nano` for a device string starting with `cuda`, otherwise `sensevoice`. Omitted multipart `model` independently defaults to `fun-asr-nano`. `spk=true` requests the separate speaker pipeline for non-native diarization models; default is `False`.

Specify `model` explicitly in requests: startup preloading and the request default are different settings. Query the deployed `/v1/models`; for example, `paraformer-en` is registered by this example but is not a built-in alias of the packaged server. Verify fields with the running `/openapi.json`, not just the checked-in [example schema](OPENAPI.md).

`response_format=verbose_json` selects a response shape; **it does not enable diarization or force timestamp generation**. This example copies `sentence_info` into `segments` if present, otherwise returns `segments=[]`. Speaker labels can be absent or null. MOSS supplies native anonymous labels; it does not need `spk=true` or external VAD/CAM++.

SDK output such as `timestamp`, or Nano's `timestamps` / `ctc_timestamps`, is not automatically converted into HTTP segments. This example accepts multipart `file`, `model`, `language`, and `response_format`; SDK options such as `use_itn`, hotwords, raw arrays, and `spk` are not its form fields. Its `language` is the submitted hint or `auto`, not detected language; the packaged service can use backend language detection.

In this example, `duration` is elapsed time around `generate()` in seconds, excluding initial model loading; it is **not audio duration**. The packaged server's verbose response uses audio duration in seconds (its fallback can use 0 when audio metadata is unavailable). Segment `start`/`end` use seconds in both services. The packaged fallback can synthesize coarse segments from text and audio duration; those are not word-level forced alignment. Its verbose schema includes `task` and per-segment `id`/`words`, while this example includes `model`; do not assume identical JSON fields. See [response examples and speaker requests](CLIENTS.md#api-contract).

## Quick Start

Use a fresh checkout and a POSIX shell with Python 3.11 installed:

```bash
git clone https://github.com/modelscope/FunASR.git FunASR-api
cd FunASR-api
git checkout --detach d91d961e37a005837b1523bcc6b09f087877be54
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install fastapi uvicorn python-multipart
python -m pip check
cd examples/openai_api
python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000
```

This pins source only, not dependencies, model weights, audio decoders, or CUDA. A PyPI install alone does not provide repository examples. These are setup instructions, not evidence of a fresh installation or successful acoustic inference on your hardware.

Wait for model loading before checking `GET /health`; download and startup time depend on the checkpoint, cache, network, and hardware. Health alone does not verify transcription. The commands below use this directory unless stated otherwise. After preparing CUDA-capable dependencies, replace the CPU command with `python server.py --host 127.0.0.1 --model sensevoice --device cuda --port 8000`; do not start both on the same port.

Need copy-paste integration snippets for Python SDK, JavaScript/TypeScript, HTTP clients, agent tools, a browser demo, Postman, OpenAPI imports, Kubernetes deployment, or Dify/n8n-style workflows? See [Client recipes](CLIENTS.md), [JavaScript/TypeScript recipes](JAVASCRIPT.md), [Gradio browser demo](GRADIO.md), [workflow recipes](WORKFLOWS.md), the [Chinese workflow recipes](WORKFLOWS_zh.md), the [Postman collection](POSTMAN.md), the [OpenAPI spec](OPENAPI.md), the [security and gateway guide](SECURITY.md), and the [Kubernetes deployment template](kubernetes/README.md).

### End-to-end smoke test

In another terminal, enter the same checkout, activate `.venv`, and enter `examples/openai_api`. The optional scripts check health and transcription:

```bash
bash smoke_test.sh
# Cross-platform alternative without curl/bash:
python smoke_test.py
```

Equivalent manual commands using public Chinese sample audio, not a Japanese/Korean validation set:

```bash
curl -L https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/BAC009S0764W0121.wav -o sample.wav
curl http://localhost:8000/health
curl http://localhost:8000/v1/models
curl http://localhost:8000/openapi.json
curl http://localhost:8000/v1/audio/transcriptions \
  -F file=@sample.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

## Browser demo with Gradio

For local file upload or recorded microphone audio, follow the maintained [Gradio browser demo](GRADIO.md). It uses a separate Python 3.12 environment, `.venv-gradio`, rather than this API server's environment. The guide covers the `funasr`, `vllm`, and `sglang-omni` profiles, explicit model selection, Docker/Kubernetes connectivity, microphone permissions, and privacy limits. The UI is a separate HTTP client, not an authentication gateway or a realtime transcription service.

## Usage with OpenAI SDK (Python)

In the same activated environment, install the separate HTTP client with `python -m pip install openai`. This is not the FunASR Python SDK. Replace `meeting.wav` with a real local audio file supported by your prepared decoders.

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

# Basic transcription
with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(model="sensevoice", file=audio)
print(result.text)

# Inspect the verbose response; segments may be empty
with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="sensevoice", file=audio, response_format="verbose_json",
    )
# verbose_json does not enable diarization; see API Contract above
print(getattr(result, "segments", []))
```

## Usage with curl

```bash
curl http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice

# With verbose output
curl http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

## Available Models

These are aliases in this example's `MODEL_CONFIGS`, not a universal SDK or server model list. The endpoint removes rich `<|...|>` tags from returned text; it does not expose dedicated emotion/event fields.

- `sensevoice`: SenseVoiceSmall + FSMN-VAD. Does not enable sentence timestamps or external speaker clustering by default.
- `paraformer`: `paraformer-zh` + FSMN-VAD + CT punctuation. Punctuation is configured; `verbose_json` alone does not request sentence records.
- `paraformer-en`: `paraformer-en` + FSMN-VAD. Example-only alias relative to the packaged server; no punctuation component configured here.
- `fun-asr-nano`: Fun-ASR-Nano via `AutoModel`, HF hub + FSMN-VAD. Not a vLLM route in this example. CTC timestamp availability depends on complete checkpoint weights.
- `moss-transcribe-diarize`: Third-party OpenMOSS native transcription/diarization adapter. Requires its separate dependency environment; preserves model-provided timestamps and anonymous labels.

For checkpoint-specific language and license information, use [model selection](../../docs/model_selection.md) and the model's own license. FunASR software's MIT license is not a license for every model weight. Benchmark the selected route on your own workload; these aliases do not define universal speed or capacity.

Fun-ASR-MLT-Nano is a separate multilingual checkpoint, not a built-in alias in either service; base Nano does not establish Korean support. For a custom checkpoint, the packaged route uses `--model-path` and `--hub` with request `model="custom"`; these are not example-server options. Follow the model-selection and Agent guides for checkpoint-specific setup.

MOSS uses a pinned third-party HF revision and must not be combined with an
external VAD or speaker model. See the [complete MOSS deployment guide](../../docs/moss_transcribe_diarize.md)
for `funasr-server`, Docker Compose, Kubernetes, vLLM, SGLang Omni, LocalAI,
and FunClip paths.
Its speaker labels are anonymous within one recording, not real-world identities or cross-recording speaker recognition. An alias appearing in `/v1/models` does not prove its dependencies or weights are ready.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/audio/transcriptions` | POST | Transcribe audio (OpenAI-compatible) |
| `/v1/models` | GET | List available models |
| `/health` | GET | Health check + loaded models |
| `/docs` | GET | Interactive API documentation (Swagger) |

Prefer no-code API checks? Use the [Gradio browser demo](GRADIO.md) for local upload or microphone testing, or import the [Postman collection](POSTMAN.md) and run health, model-list, and transcription requests from Postman. For API gateways, developer portals, or client generation, use the [OpenAPI spec](OPENAPI.md).

## Agent Framework Integration

The multipart HTTP/tool-function pattern can be used to integrate **LangChain**, **LlamaIndex**, **AutoGen**, **CrewAI**, **Semantic Kernel**, **Dify**, and **n8n**; validate the chosen integration against this service's supported fields. These recipes do not establish compatibility with every framework version or realtime API. See [Client recipes](CLIENTS.md) and [JavaScript/TypeScript recipes](JAVASCRIPT.md) for SDK and agent-tool patterns, plus [workflow recipes](WORKFLOWS.md) for low-code HTTP nodes and webhook workers ([中文](WORKFLOWS_zh.md)).

Both services map the workflow request alias `whisper-1` to the startup-selected model; this does not run OpenAI Whisper. A workflow container's `localhost` refers to that container. Use an intentionally authorized reachable gateway/service address, not unrestricted public exposure.

### LangChain Example
```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="x")

def transcribe_for_agent(audio_path: str) -> str:
    """Tool function for LangChain agent."""
    with open(audio_path, "rb") as audio:
        result = client.audio.transcriptions.create(model="sensevoice", file=audio)
    return result.text
```

## Docker Deployment

From the repository root, build the example image with the following commands. The default image starts the example `server.py` in CPU mode, not the packaged `funasr-server`.

This is a local-development publication setting, not authentication. The container still listens on `0.0.0.0`; only the host-published port binds to `127.0.0.1`. Do not change the container listener to loopback. The current Dockerfile installs unpinned PyPI FunASR/dependencies while copying this example, so it is not the source-pinned Python environment above or a reproducible acoustic environment.

```bash
cd examples/openai_api
cp .env.example .env

FUNASR_HOST_PORT=127.0.0.1:8000 docker compose up --build
```

Equivalent one-off `docker run` command:

```bash
docker build -t funasr-api .

docker run --rm -p 127.0.0.1:8000:8000 \
  -e FUNASR_DEVICE=cpu \
  -e FUNASR_MODEL=sensevoice \
  funasr-api
```

For GPU hosts, use NVIDIA Container Toolkit and a CUDA-capable PyTorch/FunASR image. After adapting the image dependencies for CUDA, run the same server with `FUNASR_DEVICE=cuda`:

```bash
docker run --rm --gpus all -p 127.0.0.1:8000:8000 \
  -e FUNASR_DEVICE=cuda \
  -e FUNASR_MODEL=sensevoice \
  funasr-api
```

Verify the container from another terminal:

```bash
BASE_URL=http://localhost:8000 bash smoke_test.sh
python smoke_test.py --base-url http://localhost:8000
```

The optional [validate_docker.sh](validate_docker.sh) combines build/run/smoke steps, but **its default port publication uses all host interfaces** and does not inherit the loopback settings above. Review its networking before running it; use the explicit loopback build/run/smoke recipe above for local testing on shared networks. Its GPU mode additionally requires NVIDIA Container Toolkit and a CUDA-capable image. These instructions are not evidence of a Docker or acoustic inference test.

## Kubernetes Deployment

Before sharing the service across a team or exposing it through a gateway, review the [security and gateway guide](SECURITY.md) for TLS, authentication, upload limits, rate limits, and logging.

For an internal cluster service with persistent model cache, health probes, and a private `ClusterIP`, start from the [Kubernetes deployment template](kubernetes/README.md). Build and push the example image, apply the manifests, then verify through `kubectl port-forward` with `python smoke_test.py --base-url http://localhost:8000`.

Keep the default CPU mode until you have built a CUDA-capable image and configured GPU scheduling for your cluster.

## Configuration

The following defaults belong to this example's `server.py`, not `funasr-server`; compare [API boundaries](#api-contract).

| Arg | Default | Description |
|-----|---------|-------------|
| `--host` | 0.0.0.0 | Bind address |
| `--port` | 8000 | Port |
| `--device` | cuda | Device (cuda/cpu/mps) |
| `--model` | sensevoice | Pre-load model at startup |

Docker environment variables:

| Env | Default | Description |
|-----|---------|-------------|
| `FUNASR_PORT` | 8000 | Container port passed to `server.py` |
| `FUNASR_DEVICE` | cpu | Container device mode; set to `cuda` only when the image has CUDA-capable dependencies |
| `FUNASR_MODEL` | sensevoice | Model alias loaded at container startup |

## Troubleshooting

- If CUDA is unavailable, use `--device cpu` for a slower but simple smoke test.
- If port 8000 is occupied, start with `--port 9000` and run `BASE_URL=http://localhost:9000 bash smoke_test.sh` or `python smoke_test.py --base-url http://localhost:9000`.
- If model download is slow, retry with a stable network or pre-download the model from ModelScope/Hugging Face.
