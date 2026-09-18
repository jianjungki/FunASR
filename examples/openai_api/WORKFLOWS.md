# Low-code Workflow Recipes for the FunASR OpenAI-Compatible API

[中文](WORKFLOWS_zh.md)

Use this guide when you want Dify, n8n, webhook workers, or another workflow engine to call a private FunASR speech API. These are multipart HTTP recipes, not a compatibility guarantee for every workflow product or version.

The example server has **no built-in authentication or upload limit**. A client URL containing `localhost` does not restrict the server's listening address. Keep local checks on loopback; before sharing, configure TLS, gateway authentication, upload/time/rate limits, private health/model/schema access, and audio/transcript retention using the [security and gateway guide](SECURITY.md). A placeholder API key does not authenticate the server.

## Server preflight

First prepare the checkout and environment in the [example README](README.md#quick-start). Its fixed source revision is not a dependency/model lock or proof of a clean installation. The commands below start in that checkout's root, with its `.venv` already prepared. If the server is already running, skip startup and proceed to the checks; do not start a second process on the same port.

```bash
cd examples/openai_api
source ../../.venv/bin/activate
python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000
```

After preparing CUDA dependencies, replace the CPU command with `python server.py --host 127.0.0.1 --model sensevoice --device cuda --port 8000`. For the distinct packaged `funasr-server` route, use [Agent integration](../../docs/agent_integration.md); startup defaults, aliases and response fields differ from this example.

In a second terminal on the same host, enter the same checkout's `examples/openai_api` directory and activate the same environment. Wait for model loading, then check the local service:

```bash
source ../../.venv/bin/activate
export FUNASR_BASE_URL="http://127.0.0.1:8000"
curl -fsS "$FUNASR_BASE_URL/health"
curl -fsS "$FUNASR_BASE_URL/v1/models"
curl -fsS "$FUNASR_BASE_URL/openapi.json"
```

Health and schema checks do not establish acoustic correctness. For transcription, use an existing local audio file as `meeting.wav` below; the README's public Chinese smoke sample is not a multilingual accuracy benchmark.

If the workflow engine runs in Docker, `localhost` usually means the workflow container itself. A host-loopback server is not automatically reachable from that container. Deliberately configure a private gateway/container network, then replace `FUNASR_BASE_URL` and the worker's `FUNASR_URL` with the address reachable from the workflow runtime. Use real gateway credentials when required; the local curl/Python examples below do not add authentication headers. Do not solve connectivity by exposing an unauthenticated port publicly.

## Postman smoke test

Before configuring a low-code tool, you can import the [Postman collection](POSTMAN.md) and run health, model-list, and transcription requests from a GUI. For schema-driven imports, use the [OpenAPI spec](OPENAPI.md). Set `FUNASR_BASE_URL`, choose a local audio file for the multipart `file` field, and keep `MODEL_ALIAS=sensevoice` for the first test.

For offline multi-speaker meetings, first prepare the isolated third-party MOSS service in the [MOSS deployment guide](../../docs/moss_transcribe_diarize.md), including its GPU and file-duration limits. Then set `MODEL_ALIAS=moss-transcribe-diarize` and keep `response_format=verbose_json` to preserve available native anonymous speaker segments. Do not add external VAD or `spk=true`; recording-local labels are not verified identities or stable IDs across recordings. Changing a client alias alone does not prepare that service.

## Multipart HTTP request

Every workflow engine eventually needs to send this request shape:

- **Method:** `POST`
- **URL:** `http://<funasr-host>:8000/v1/audio/transcriptions`
- **Body type:** `multipart/form-data`
- **File field:** `file`
- **Text field:** `model=sensevoice`
- **Text field:** `response_format=verbose_json`
- **Timeout:** Set according to maximum audio duration, for example 300 seconds for long files.

Equivalent curl command:

```bash
curl -fsS "$FUNASR_BASE_URL/v1/audio/transcriptions" \
  -F file=@meeting.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

Map `text` to the transcript. `response_format=verbose_json` selects a format: it does not enable diarization or force timestamps. Check the [client response contract](CLIENTS.md#response-formats) before consuming the other fields:

- **Example `server.py`:** `segments` comes only from model-provided `sentence_info`, otherwise `segments=[]`. `duration` is elapsed seconds around `generate()`, excluding initial model loading, not recording length. `model` is the resolved request alias; `language` echoes the submitted hint or `auto`, not detected language.
- **Packaged `funasr-server`:** `duration` is audio length in seconds, with 0 possible if fallback audio metadata cannot be read. It can return coarse text-based segments, not forced alignment. Its verbose response includes `task` and segment `id`/`words`, but no top-level `model`; language can use backend detection. For non-native diarization models, `spk=true` opts into a separate speaker pipeline, subject to its model/dependencies. The example has no `spk` form field.

Segment `start`/`end` use seconds, not the SDK's millisecond coordinates. A `speaker` field can be absent, null, numeric or a string; labels do not identify a person. Neither nonempty segments nor `verbose_json` guarantees accurate subtitle alignment. HTTP display text strips SenseVoice rich tags; it is not the SDK raw-tag result or a dedicated emotion/event response. SDK fields/options such as `timestamp`, `timestamps`, `ctc_timestamps`, `use_itn`, hotwords and raw arrays are not additional form fields; raw SDK timestamps are not automatically converted into HTTP segments.

Illustrative example-server response with no `sentence_info`; `0.42` is processing time, not audio duration:

```json
{"text": "recognized speech", "segments": [], "language": "auto", "duration": 0.42, "model": "sensevoice"}
```

Illustrative packaged-server response for a 3.2-second file and a coarse fallback segment, without speaker opt-in. These examples describe schemas, not new model measurements:

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

## Dify custom tool or HTTP node

Use this pattern when a Dify application receives an uploaded audio file or a URL to internal audio storage.

### Direct file upload path

Configure an HTTP request node or custom tool with:

- Method: `POST`
- URL: `http://<funasr-host>:8000/v1/audio/transcriptions`
- Body: `multipart/form-data`
- File part: `file`, bound to the uploaded audio variable
- Text parts: `model=sensevoice`, `response_format=verbose_json`
- Output variable: map `text` as the transcript; inspect `segments` availability and provenance before using timestamps or speaker labels

### Audio URL path

Some workflow tools pass a file URL rather than raw multipart bytes. A URL string in the multipart `file` field is not an audio upload. Prefer direct binary uploads or controlled storage object IDs resolved by a reviewed storage client.

The following sketch is only for an operator-approved URL in trusted storage. Destination allowlists, private-network access policy, redirect validation, download byte limits and authentication are **not implemented**. `requests.get` follows redirects and buffers the entire response; its timeout is not a byte cap or a complete end-to-end deadline. Do not pass user-supplied URLs to this helper. Before accepting them, require a reviewed download boundary enforcing all those controls, including blocking unintended private/metadata destinations and checking each redirect. Being inside a trusted network is not an SSRF defense.

For this trusted-input illustration:

1. An operator supplies an approved audio URL and metadata to the worker.
2. The worker downloads the file from trusted storage.
3. The worker posts multipart data to FunASR.
4. The worker returns the service JSON; downstream nodes check optional fields. Logs must not expose signed URLs, credentials or private transcripts.

In the same activated client environment, install the separate HTTP dependency:

```bash
python -m pip install requests
```

Set `FUNASR_URL` for the prepared service; this default is for a worker on the same host. The function definitions can be imported by your worker, but do not create an HTTP listener or implement inbound authentication/upload limits.

```python
import requests

FUNASR_URL = "http://127.0.0.1:8000/v1/audio/transcriptions"

def transcribe_from_url(audio_url: str) -> dict:
    audio_response = requests.get(audio_url, timeout=120)
    audio_response.raise_for_status()
    files = {"file": ("audio.wav", audio_response.content, "audio/wav")}
    data = {"model": "sensevoice", "response_format": "verbose_json"}
    response = requests.post(FUNASR_URL, files=files, data=data, timeout=300)
    response.raise_for_status()
    return response.json()
```

Keep this illustration restricted to approved inputs; hostname validation alone is not a complete safe-download policy.

## n8n HTTP Request node

A common n8n flow is: trigger -> binary audio data -> HTTP Request -> transcript consumer.

Recommended HTTP Request settings:

- **Method:** `POST`
- **URL:** `http://<funasr-host>:8000/v1/audio/transcriptions`
- **Send Body:** enabled
- **Body Content Type:** `Form-Data` / multipart
- **Binary file field:** `file`
- **Additional form fields:** `model=sensevoice`, `response_format=verbose_json`
- **Response Format:** JSON
- **Timeout:** Increase for long recordings.

After the request, use `{{$json.text}}` as the transcript. Route `{{$json.segments}}` onward only after checking it exists and is useful for the task; empty or coarse segments must not be treated as verified subtitle timing or diarization. Node labels and binary-property configuration vary with the installed n8n version; `file` is the outgoing multipart field, not necessarily the name of the incoming binary property.

### n8n OpenAI Audio node

For OpenAI Audio > Transcribe node versions that send `model=whisper-1`, FunASR maps that compatibility alias to the model selected at server startup; it does not select a Whisper checkpoint. Set Base URL to your reachable service URL with `/v1`. A non-empty placeholder key is only for an unprotected local endpoint; supply real credentials for an authenticated gateway. Verify the installed node version's request behavior rather than assuming all versions match. Use this recipe for plain transcription; use the HTTP Request node for explicit `response_format` and any supported speaker opt-in, still subject to the response limits above.

## Webhook worker pattern

Use this when the workflow engine cannot send multipart files reliably or when audio needs pre-processing. This POSIX temporary-file example uses the same `requests` dependency and closes the upload handle. It accepts bytes already held in memory: apply upload limits before buffering them. It is a function, not a protected webhook server.

```python
from pathlib import Path
import tempfile
import requests

FUNASR_URL = "http://127.0.0.1:8000/v1/audio/transcriptions"

def transcribe_bytes(filename: str, payload: bytes, content_type: str = "audio/wav") -> dict:
    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".wav") as tmp:
        tmp.write(payload)
        tmp.flush()
        with open(tmp.name, "rb") as audio:
            response = requests.post(
                FUNASR_URL,
                files={"file": (filename, audio, content_type)},
                data={"model": "sensevoice", "response_format": "verbose_json"},
                timeout=300,
            )
    response.raise_for_status()
    return response.json()
```

Audio conversion, file-size checks, request IDs, inbound/upstream authentication and retry policy are not implemented here. Enforce them at the appropriate boundary before shared use; retries can repeat expensive transcription work.

## Production guardrails

- Put authentication, TLS, upload-size limits, and rate limits in front of FunASR before sharing it across teams; use the [security and gateway guide](SECURITY.md) for proxy and gateway patterns.
- Use `/health` for workflow readiness checks and `/v1/models` to validate model aliases.
- Log request id, audio duration, model alias, response format, device, latency, and error type.
- Set workflow timeouts according to maximum audio duration; split very long recordings before sending them through low-code tools.
- Keep private audio in trusted storage and avoid putting signed URLs, credentials, or transcripts into public logs.
- Run the same workflow with at least one public smoke sample and one realistic private sample before production use.

## Troubleshooting

- **Workflow can call `/health` but transcription fails:** Confirm the request is `multipart/form-data` and the binary field is named `file`.
- **`localhost` connection fails from Dify or n8n:** Use the host, Compose service, or Kubernetes service reachable from the workflow runtime.
- **Response has no usable `segments`:** Check the format and deployed schema, then the model's `sentence_info` and speaker configuration; `verbose_json` alone cannot create timestamps or labels.
- **Requests time out:** Increase HTTP timeout or split long recordings.
- **First request is slow:** Preload the model with `--model sensevoice` and use `/health` as a readiness check.
- **Unknown model alias:** Call `/v1/models` and use one of the returned aliases.
