# FunASR Agent Integration

[中文](agent_integration_zh.md)

Connect a speech application through the interface it actually needs: an HTTP
file-transcription request, a local MCP tool, desktop recording, or a local
subtitle pipeline. These paths do not share every model, option, or result field.
For direct in-process inference, use the [Python SDK](python_api.md).

## HTTP server

The following source-based starting point includes the example scripts used
later on this page. The commands use a POSIX shell. Use a new checkout and virtual environment; installing the
PyPI package alone does not install these repository examples.

```bash
git clone https://github.com/modelscope/FunASR.git FunASR-agent
cd FunASR-agent
git checkout --detach e19029adca384a06a2f60bd8c18cb98f1a0499aa
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install fastapi uvicorn python-multipart
python -m pip check
```

This pins the source, not all dependencies or model weights. Use the
[installation guide](installation/installation.md) to prepare the selected
CPU/GPU environment, record resolved package/model versions, and validate a
real request. `pip check` alone is not a CUDA, audio-decoder, or clean-install test.

From that environment, run **one** of these commands. The CPU recipe selects
SenseVoice explicitly; the CUDA alternative needs a working GPU environment.
Keep this terminal running and use another prepared terminal for clients.

```bash
funasr-server --host 127.0.0.1 --device cpu --model sensevoice --port 8000
# Alternative: stop the CPU server before using the same port.
funasr-server --host 127.0.0.1 --device cuda --model sensevoice --port 8000
```

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/models
```

Use `/v1/audio/transcriptions` for uploaded files, `/openapi.json` for the running
service schema, and `/docs` for its Swagger UI. This service `/docs` is not the
FunASR website's documentation directory. Health or model-list responses do not
replace a successful transcription with the intended model.

The packaged `funasr-server` and [example HTTP server](../examples/openai_api/README.md#api-contract)
have different defaults, aliases, and response schemas. Specify `model` in the
request as well as at startup. `paraformer-en` is an example-server alias, not a
built-in packaged-server alias. SenseVoice HTTP display text has rich tags removed;
it is not a dedicated emotion/event output API. Nano and MLT-Nano language coverage
and timestamp paths must be selected through the [model guide](model_selection.md),
not inferred from the HTTP interface. For a custom packaged-server model, use
`--model-path` with the appropriate `--hub` and request `model=custom`; an
arbitrary model ID is not automatically a built-in `--model` alias.

[MOSS-Transcribe-Diarize](moss_transcribe_diarize.md) is a third-party OpenMOSS
model with its own deployment requirements. Its native anonymous speaker labels
do not require external VAD or an external speaker model; do not add those stages
or assume every client exposes all of its output.

The local server does not authenticate the placeholder SDK key below. Before
network access, add TLS, authentication, upload limits and rate limits according
to the [security guide](../examples/openai_api/SECURITY.md). CORS is not authentication.

## SDK and curl

Install the separate OpenAI HTTP client in the client environment:

```bash
python -m pip install openai
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="local-development")
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

```bash
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

`verbose_json` chooses a format; it does not enable diarization, recover rich
tags, or guarantee word alignment. The example server copies available
`sentence_info` into segments, otherwise returning an empty list. The packaged
server can supply coarse fallback segments. Both expose segment times in seconds,
but their `duration` fields differ. Use the [client result contract](../examples/openai_api/CLIENTS.md#response-formats)
before consuming timestamps. `json` and `text` are simpler response choices.
Speaker processing via `spk=true` belongs to the packaged API, not the example's
request schema; see [speaker labels and identity limits](speaker_emotion.md).

## Workflow integrations

Use a multipart HTTP node with method `POST`, the transcription endpoint, a
binary file field named `file`, and text fields `model` and `response_format`.
A file URL in the `file` field is not equivalent to uploading audio bytes.
For Dify/n8n running in a container, `localhost` means that container, not the
FunASR host; configure a reachable service address behind the intended gateway.

- [Dify, n8n and webhook workers](../examples/openai_api/WORKFLOWS.md) provide request wiring examples.
- [JavaScript and TypeScript](../examples/openai_api/JAVASCRIPT.md) cover SDK and multipart clients.
- [Postman](../examples/openai_api/POSTMAN.md) and the [smoke test](../examples/openai_api/smoke_test.py) check a deployed endpoint.
- [Gradio](../examples/openai_api/GRADIO.md) provides a browser upload/microphone example.
- [OpenAPI](../examples/openai_api/OPENAPI.md) distinguishes the checked-in example schema from the deployed packaged schema.

Register transcription as a tool in the host framework using these request and
result boundaries. The URL worker example does not implement a complete secure
downloader: add destination allowlists, private-network blocking, redirect
validation, size limits and timeouts before accepting untrusted URLs. Use the
client result contract above instead of assuming the workflow field table fits
both server implementations. These recipes are not proof that every framework version has
been integrated or that untrusted download URLs are safe.

## MCP server

From the prepared repository root and environment:

```bash
python examples/mcp_server/funasr_mcp.py
```

Prepare PyTorch and a compatible audio-feature backend using the installation
guide before attempting transcription. Installing the toolkit or completing an
MCP handshake alone does not verify model execution; this script does not need
a separate MCP SDK package. An MCP client launches it over stdio, not HTTP.
Configure absolute paths to the prepared Python environment and checkout:

```json
{
  "mcpServers": {
    "funasr": {
      "command": "/path/to/FunASR-agent/.venv/bin/python",
      "args": ["/path/to/FunASR-agent/examples/mcp_server/funasr_mcp.py"],
      "env": {
        "FUNASR_DEVICE": "cpu",
        "FUNASR_MODEL": "iic/SenseVoiceSmall"
      }
    }
  }
}
```

`transcribe_audio` accepts an existing local `audio_path` visible to the server,
including a read-only mounted path in a container. It does not accept URLs or
live streams. The first call may download and load weights. The language hints
are `auto`, `zh`, `yue`, `en`, `ja`, and `ko`; setting `FUNASR_MODEL` does not
change that tool schema or guarantee another model is compatible with its VAD path.

The result is formatted MCP `content` with `type=text`, optionally including
segments, not the HTTP response object. Top-level transcript rich tags are
removed; optional segment text is copied from model output. `FUNASR_DEVICE`
defaults to `cpu`, and `FUNASR_MODEL` defaults to `iic/SenseVoiceSmall`.
See the [MCP source and container setup](../examples/mcp_server/README.md) for
client configuration and filesystem mounts. Control which files the assistant
and server can access; a local tool is not a filesystem authorization boundary.

## Desktop voice input

With the HTTP server already running, use a second terminal in the prepared checkout:

```bash
python -m pip install sounddevice numpy pyperclip openai pynput
python examples/voice_input/funasr_input.py --server http://localhost:8000/v1 --model sensevoice
```

The script toggles recording, uploads WAV audio to the HTTP service, and copies
the transcript for pasting. Microphone permissions and audio-device support are
required; macOS may also require accessibility permissions, and Linux automatic
paste uses `xdotool`. Clipboard/paste behavior varies by desktop session.
The current `--lang` option is parsed but not forwarded to the transcription
request, so it is not an effective language control in this path.

A remote `--server` sends the recorded audio to that endpoint. Do not treat this
as an unconditional offline/privacy guarantee or a measured latency promise.
See [configuration](../examples/voice_input/README.md#配置选项) and the
[implementation](../examples/voice_input/funasr_input.py) before deployment.

## Subtitle generation

This is a local `AutoModel` pipeline, not an HTTP or MCP client. From the prepared
checkout, with local input files and a suitable inference environment:

```bash
python examples/subtitle/generate_subtitle.py video.mp4
python examples/subtitle/generate_subtitle.py meeting.wav --spk
python examples/subtitle/generate_subtitle.py podcast.mp3 --format vtt
python examples/subtitle/generate_subtitle.py audio.wav --device cpu
```

The default device is CUDA; the last command explicitly selects CPU. The default
model is SenseVoiceSmall with VAD and punctuation. This fixed pipeline is not a
generic recipe for arbitrary models. `--spk` adds
CAM++ anonymous labels, not verified identities. `--format` selects SRT or VTT;
`--output` chooses a path, and existing output files are overwritten. Choose a
new output path when preserving prior subtitles. `--lang` passes a non-auto language hint to generation.
`--max-single-segment-time` is in milliseconds, with current default `60000`.

`--segment-mode readable` groups display cues without rewriting recognized
text or punctuation; `sentence` retains raw model sentence grouping. Neither
mode fixes punctuation errors or guarantees phonetic boundaries. Check actual
timestamp availability and playback against the original audio: a missing timing
result can fall back to a zero-duration `(0, 0)` interval, not a validated subtitle.
Input decoding,
model/dependency loading and GPU capacity still require environment-specific
validation. See [subtitle options](../examples/subtitle/README.md#options) and
the [speaker guide](speaker_emotion.md) for output interpretation.
