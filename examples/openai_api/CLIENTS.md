# Client Recipes for the FunASR OpenAI-Compatible API

Use this page when the packaged `funasr-server` or the repository's example `server.py` is already running. They share a multipart transcription request subset, but not identical defaults, aliases, or response schemas; see [API boundaries](#api-contract). For in-process `AutoModel.generate()` and model-specific options, use the [Python SDK guide](../../docs/python_api.md) ([中文](../../docs/python_api_zh.md)). For JavaScript, TypeScript, and Next.js examples, see the [JavaScript/TypeScript recipes](JAVASCRIPT.md) or [Chinese JavaScript/TypeScript recipes](JAVASCRIPT_zh.md). For Dify, n8n, HTTP nodes, and webhook workers, see the [workflow recipes](WORKFLOWS.md) or [Chinese workflow recipes](WORKFLOWS_zh.md). For browser upload or microphone demos, use the [Gradio browser demo](GRADIO.md). For no-code API smoke tests, import the [Postman collection](POSTMAN.md). For schema-driven imports or client generation, use the [OpenAPI spec](OPENAPI.md). Before sharing the service, review the [security and gateway guide](SECURITY.md).

## API Contract

The [example server](server.py) defaults to `sensevoice` at startup and when multipart `model` is omitted. The packaged [CLI](../../funasr/bin/server.py) defaults to `--model auto`: its [app](../../funasr/bin/_server_app.py) selects `fun-asr-nano` for device strings starting with `cuda`, otherwise `sensevoice`. The packaged transcription form defaults to `fun-asr-nano`, independently of startup preloading. Always specify `model` explicitly and check the deployed `/v1/models` and `/openapi.json`. The checked-in OpenAPI spec describes the example, not every packaged-server field.

`response_format=verbose_json` selects a response format; **it does not enable diarization or force timestamp generation**. The example copies model-provided `sentence_info` to `segments`, otherwise returns `segments=[]`, and has no `spk` form field. In the packaged server, `spk=true` opts into external speaker processing for non-native diarization models (default `False`). MOSS has native anonymous labels and should not be combined with external VAD or speaker models. Labels are not verified identities or stable IDs across recordings.

For an already-running **packaged `funasr-server` only**, this multipart request opts into speaker processing when supported by its installed dependencies and model:

```bash
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@meeting.wav \
  -F model=sensevoice \
  -F response_format=verbose_json \
  -F spk=true
```

Do not send `spk=true` to the example and assume it enables anything. Neither endpoint exposes every `AutoModel.generate()` option as a form field. Review [response formats](#response-formats) for timestamp and duration semantics, and the [example README](README.md#api-contract) ([中文](README_zh.md#api-contract)) for startup instructions and scope.

## Preflight

```bash
export BASE_URL=http://localhost:8000
curl -fsS "$BASE_URL/health"
curl -fsS "$BASE_URL/v1/models"
```

If the server is on another machine, replace `localhost` with the reachable host name or service address. Keep `/v1` in SDK base URLs, and omit `/v1` for direct endpoint checks like `/health`.

## Model aliases

| Alias | Good first use | Notes |
|---|---|---|
| `sensevoice` | Private transcription API | Example startup default, not the unconditional packaged default. Services strip rich tags from display text; no dedicated emotion/event fields. |
| `paraformer` | Mandarin production transcription | Includes VAD and punctuation. |
| `paraformer-en` | English transcription | Registered in the example, not a built-in alias of packaged `funasr-server`. |
| `fun-asr-nano` | LLM-based ASR experiments | The packaged app tries vLLM and can fall back to AutoModel; the example uses AutoModel. Validate dependencies and checkpoint contents for the chosen route. |
| `moss-transcribe-diarize` | Offline multi-speaker long-form audio | Returns timestamps and anonymous speaker labels in `verbose_json`; do not add external VAD or diarization. |

For MOSS server, Docker, Kubernetes, vLLM, SGLang Omni, LocalAI, and FunClip
paths, use the [dedicated deployment guide](../../docs/moss_transcribe_diarize.md).

## Python OpenAI SDK

Install this separate HTTP client with `pip install openai`; it is not the FunASR in-process SDK. The recipes use only the transcription subset supported by these services, not the complete OpenAI API.

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="sensevoice",
        file=audio,
        response_format="verbose_json",
    )

print(result.text)
for segment in getattr(result, "segments", []):
    print(segment)
```

Most OpenAI SDKs require an API key value even when the local FunASR server does not check it. Use any placeholder for local development, then add real authentication at your gateway if the service is shared.

## JavaScript and TypeScript

Use the [JavaScript/TypeScript recipes](JAVASCRIPT.md) for OpenAI JS SDK, built-in `fetch`, TypeScript helper functions, and Next.js route handlers. Minimal OpenAI SDK shape:

```javascript
import OpenAI from "openai";
import { createReadStream } from "node:fs";

const client = new OpenAI({
  baseURL: "http://localhost:8000/v1",
  apiKey: "local-development",
});

const result = await client.audio.transcriptions.create({
  model: "sensevoice",
  file: createReadStream("meeting.wav"),
  response_format: "verbose_json",
});

console.log(result.text);
```

For browser uploads, send audio to your backend first, then proxy to FunASR with authentication and upload limits. See the [Chinese JavaScript/TypeScript recipes](JAVASCRIPT_zh.md) for localized guidance.

## Plain Python requests

```python
import requests

with open("meeting.wav", "rb") as audio:
    response = requests.post(
        "http://localhost:8000/v1/audio/transcriptions",
        files={"file": ("meeting.wav", audio, "audio/wav")},
        data={"model": "sensevoice", "response_format": "verbose_json"},
        timeout=300,
    )
response.raise_for_status()
print(response.json()["text"])
```

This is the most portable pattern for internal services, queues, notebooks, and low-code tools that can issue multipart HTTP requests.

## Agent tool pattern

Expose transcription as a regular tool function. The agent does not need to know FunASR internals; it only needs a file path or uploaded audio object.

```python
from pathlib import Path
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="local")

def transcribe_audio(audio_path: str) -> str:
    """Transcribe a local audio file with FunASR and return plain text."""
    path = Path(audio_path)
    with path.open("rb") as audio:
        result = client.audio.transcriptions.create(
            model="sensevoice",
            file=audio,
        )
    return result.text
```

For LangChain, LlamaIndex, AutoGen, CrewAI, Semantic Kernel, and similar frameworks, register the function above using that framework's normal tool or function-calling mechanism.

## Dify, workflow engines, and HTTP nodes

Use a multipart HTTP node or custom tool:

| Setting | Value |
|---|---|
| Method | `POST` |
| URL | `http://<funasr-host>:8000/v1/audio/transcriptions` |
| Body type | `multipart/form-data` |
| File field | `file` |
| Text fields | `model=sensevoice`, `response_format=verbose_json` |
| Result path | `text` for transcript; `segments` may be empty and speaker labels are conditional |

When the workflow system cannot send files directly, upload audio to an internal object store first, then run a small worker that downloads the object and calls FunASR with the `requests` recipe above. See [workflow recipes](WORKFLOWS.md) for Dify, n8n, and webhook-worker patterns, or the [Chinese workflow recipes](WORKFLOWS_zh.md).

## Response formats

`response_format=json` returns a compact response:

```json
{"text": "recognized speech"}
```

`response_format=verbose_json` does not enable diarization. Its fields depend on the deployed entry point:

| Field | Example `server.py` | Packaged `funasr-server` |
|---|---|---|
| `duration` | Elapsed seconds around `generate()`, excluding initial model loading; not audio duration. | Audio duration in seconds; fallback can return 0 if audio metadata cannot be read. |
| `segments` | Converted from model-provided `sentence_info`; otherwise `[]`. | Uses available segments; fallback can synthesize coarse text-based intervals over the audio duration. |
| `start`, `end` | Segment times in seconds. | Segment times in seconds, not necessarily word-level alignment. |
| `speaker` | Model-provided label or null when a segment lacks a label. | Included only when a label is present; external clustering needs `spk=true`, while MOSS has native labels. |
| Other fields | Includes `model`; `language` echoes the requested hint or `auto`. | Includes `task` and segment `id`/`words`; does not add a top-level `model` field in the verbose builder. |

Illustrative **packaged-server** response for a 3.2-second recording, without speaker opt-in. The single coarse segment is not a claim of forced alignment; actual text, language, and segmentation vary:

```json
{
  "task": "transcribe",
  "language": "en",
  "duration": 3.2,
  "text": "recognized speech",
  "segments": [
    {"id": 0, "start": 0.0, "end": 3.2, "text": "recognized speech", "words": []}
  ]
}
```

Illustrative **example-server** response when no `sentence_info` was returned. Here `0.42` is inference elapsed time, not the recording length:

```json
{
  "text": "recognized speech",
  "segments": [],
  "language": "auto",
  "duration": 0.42,
  "model": "sensevoice"
}
```

Check segment availability and provenance before generating subtitles. A nonempty `segments` array or `verbose_json` response is not evidence of speaker diarization or token-level alignment. The SDK's millisecond `sentence_info` coordinates are converted to seconds by these service adapters; see the [Python SDK result contract](../../docs/python_api.md).

## Production checklist

- Put TLS, authentication, rate limits, and upload-size limits in front of the service before exposing it outside a trusted network; use the [security and gateway guide](SECURITY.md) as the rollout checklist.
- Preload the default model at startup and use `/health` for readiness checks.
- Set client timeouts based on maximum audio duration; long recordings need longer HTTP timeouts.
- Log audio duration, model alias, device, latency, response format, and error type for every request.
- Pin SDK/dependency versions, deployment images, full model IDs and resolved revisions/artifact hashes; aliases alone are not reproducible model pins. See [SDK offline and revision caveats](../../docs/python_api.md).
- For GPU hosts, keep one worker per GPU until you have measured memory headroom and concurrency behavior.

## Troubleshooting quick checks

| Symptom | Check |
|---|---|
| SDK says authentication is missing | Pass any placeholder `api_key` for local development. |
| 400 unknown model | Call `/v1/models` and use one of the listed aliases. |
| Request times out | Increase client timeout or split very long recordings. |
| First request is slow | The model may be loading; preload with `--model sensevoice`. |
| CUDA is unavailable | Start with `--device cpu` to verify the API path, then fix GPU drivers/runtime. |
| Port conflict | Start with `--port 9000` and set `BASE_URL=http://localhost:9000`. |
