# Gradio Browser Demo for the FunASR OpenAI-Compatible API

Use this optional browser UI to upload a file or record audio for a prepared FunASR, native vLLM, or native SGLang Omni transcription service. The Gradio app is an HTTP client: it does not load models or install the server's acoustic dependencies. Recording is submitted as a complete file; this is not streaming transcription or a realtime wake-word service.

Keep both listeners private. The demo is not an authentication gateway: it does not configure UI authentication or send backend `Authorization` credentials. The API base URL is editable, and requests originate from the **Gradio process**, not directly from the browser. Do not share this operator UI with untrusted users. Read the [security and gateway guide](SECURITY.md) before the first launch; its Basic gateway is not directly compatible with this client's unauthenticated requests.

## 1. Start the API server

For the repository's example API, start with the same prepared checkout as the [HTTP server guide](README.md#quick-start). In a POSIX shell with Python 3.11 available:

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

This pins source, not dependencies, model weights, decoders, or CUDA. It is an installation recipe, not a clean-install or acoustic validation result. Wait for model loading before checking the service. After preparing GPU dependencies, use the HTTP guide's CUDA alternative instead of running a second server on port 8000.

For MOSS, prepare the dedicated environment and pinned server/model revisions in the [MOSS deployment guide](../../docs/moss_transcribe_diarize.md). Choose its FunASR service, native vLLM, or native SGLang Omni path first; the UI profile does not launch, convert, or reconfigure that server. MOSS performs joint offline transcription and diarization without an external VAD or speaker model. Do not try to install its GPU environment into the lightweight Gradio environment below.

Docker and Kubernetes are alternative backend deployments. Publish container port 8000 only on host loopback, or use a private `kubectl port-forward`; container-internal `0.0.0.0` is different from host exposure. `ClusterIP` alone is not network isolation. A cluster DNS name works only where the Gradio process can resolve and reach it. From a laptop, use the locally forwarded address, not an unresolvable `*.svc.cluster.local` URL. See [Docker deployment](README.md#docker-deployment) and [Kubernetes deployment](kubernetes/README.md).

## 2. Install and launch the browser UI

Open a **new terminal**, starting in the directory that contains `FunASR-api`. Use a separate Python 3.12 environment `.venv-gradio`, not the server's `.venv` or a native backend environment. The client recipe selects Gradio 6.26.0; this version pin alone is not evidence of a successful installation or compatibility with every backend release.

```bash
cd FunASR-api
python3.12 -m venv .venv-gradio
source .venv-gradio/bin/activate
python -m pip install "gradio==6.26.0"
python -m pip check
cd examples/openai_api
python gradio_app.py --backend funasr --model sensevoice --base-url http://127.0.0.1:8000 --host 127.0.0.1 --port 7860
```

No FunASR, Torch, CUDA, or model download is required by the Gradio client itself. The separately running backend still needs its own prepared dependencies and models. In subsequent client terminals, activate `.venv-gradio` from the checkout root and then enter `examples/openai_api` before running the commands below.

Open the printed local URL, allow microphone access only when needed, upload or record an audio file, choose **Model alias** and **Response format**, and click **Transcribe**. The CLI defaults are backend `funasr`, model `sensevoice`, and format `verbose_json`. The UI listens on port 7860, separate from the backend's port. Browser microphone access depends on permissions and a secure context; a remote plain-HTTP UI is not a portable microphone recipe.

The following launches are **alternatives**, using the same activated client environment and directory. Stop the previous UI before reusing port 7860; start the matching backend separately first. `--backend` explicitly selects a client profile: it does not detect or switch the running server. Use the service base URL **without `/v1`**, unlike an OpenAI SDK base URL. The client appends `/v1/audio/transcriptions`.

For the FunASR example or packaged service prepared with MOSS:

```bash
python gradio_app.py --backend funasr --model moss-transcribe-diarize --base-url http://127.0.0.1:8000 --host 127.0.0.1 --port 7860
```

For the pinned native vLLM recipe with `--served-model-name moss-transcribe-diarize`:

```bash
python gradio_app.py --backend vllm --model moss-transcribe-diarize --base-url http://127.0.0.1:8898 --host 127.0.0.1 --port 7860
```

For the native SGLang Omni recipe using its full model ID, the dropdown displays the shorter label `MOSS-Transcribe-Diarize`; the request still sends the complete ID:

```bash
python gradio_app.py --backend sglang-omni --model OpenMOSS-Team/MOSS-Transcribe-Diarize --base-url http://127.0.0.1:8898 --host 127.0.0.1 --port 7860
```

An explicit `--model` is an operator override, added to the choices and sent exactly as the request's `model`; it does not register a server alias or change the checkpoint. For example, only after configuring a vLLM service to accept the served name `meeting-asr`, use:

```bash
python gradio_app.py --backend vllm --model meeting-asr --base-url http://127.0.0.1:8898 --host 127.0.0.1 --port 7860
```

Do not substitute a full Hugging Face ID for a FunASR request alias. The example API validates its five aliases; the packaged service's `--model-path`/`--hub` deployment uses request model `custom`. The UI override does not bypass either server's model validation. Check the active profile, model, and format before sending audio.

## 3. Verify the backend first

**Check service** requests `/health` and `/v1/models`. This is metadata inspection, not an acoustic test and not a model-readiness guarantee. Server schemas and route policies differ: a native service or gateway may deny a metadata route while allowing transcription. Do not expose private metadata or remove authentication merely to make the button succeed.

For the unauthenticated loopback FunASR example service, in the activated client environment and `examples/openai_api` directory:

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:8000/v1/models
python smoke_test.py --base-url http://127.0.0.1:8000 --model sensevoice
```

The first two commands inspect metadata only. The optional `smoke_test.py` command is different: if its default `sample.wav` is missing, it downloads a public Chinese sample, writes it in the current directory, performs transcription, and prints the result. It is not a multilingual accuracy benchmark or a metadata-only check. Use controlled audio and protect diagnostic output. The smoke script's model must match the prepared service too; this command does not validate a MOSS/native deployment.

The UI's timeout defaults to 300 seconds and is passed to the HTTP client. It is not a total job deadline; a client timeout does not cancel backend inference or establish safe concurrency limits.

## Model aliases

The `funasr` profile offers these five request aliases. A listed alias does not mean the checkpoint is loaded, cached, or supported by the installed dependencies; selecting another model can cause the example API to load it on demand.

- `sensevoice`: SenseVoice transcription through FunASR. HTTP text has its language/emotion/event tags removed; the UI's raw response is not the SDK's raw tagged output.
- `paraformer`: Mandarin-oriented transcription through the configured FunASR pipeline, not a throughput or production-capacity guarantee.
- `paraformer-en`: English transcription through the configured FunASR pipeline.
- `fun-asr-nano`: The base Fun-ASR-Nano model, not the separate 31-language Fun-ASR-MLT-Nano checkpoint; do not assume Korean support. Choosing this alias on example `server.py` does not start native vLLM.
- `moss-transcribe-diarize`: Third-party OpenMOSS joint offline transcription and diarization in its dedicated environment. Its recording-local anonymous speaker label is not an identity determination; it is not a realtime microphone model. Use `verbose_json` to inspect the FunASR service's segments.

Backend profiles deliberately have different defaults and formats:

**funasr** defaults to `sensevoice` and `verbose_json`, and also offers `json`. The example API's `json` contains `text`; its `verbose_json` maps `sentence_info` to `segments` with `start`/`end` in seconds and a model-dependent `speaker`. Segments can be empty; requesting verbose output does not create diarization. Example `duration` is inference time, whereas packaged FunASR reports audio duration. See [API boundaries](README.md#api-contract).

**vllm** defaults to `moss-transcribe-diarize` and `diarized_json`, and also offers `json`. On the pinned MOSS serving path, `diarized_json` contains structured speaker-attributed segments; `json` preserves compact tagged text. This is not a promise for arbitrary vLLM models or releases. Do not send `diarized_json` to the FunASR profile expecting the same result.

**sglang-omni** defaults to `OpenMOSS-Team/MOSS-Transcribe-Diarize` and offers only `verbose_json`. In the documented native contract, `[Sxx]` remains in `segments[].text`; it is not a separate `speaker` field. The Gradio client displays the returned `text` and JSON without stripping tags, inventing labels, or normalizing these backend differences. See the pinned [MOSS deployment guide](../../docs/moss_transcribe_diarize.md) for protocol/version limits and long-audio controls; this UI does not expose backend-specific token budgets.

See the [model selection guide](../../docs/model_selection.md) for a deeper comparison.

## Production notes

- Treat this as a private operator demo, not a public production frontend. Do not enable `--share` for sensitive audio. A loopback UI does not make a separately exposed backend private.
- The editable API URL controls server-side requests. There is no application target allowlist or redirect restriction; the HTTP client can follow redirects. Restrict who can operate the UI and the Gradio process's network access. Do not put passwords or access tokens into URLs.
- The demo does not configure Basic, Bearer, OIDC, or mTLS backend credentials. TLS, authentication, upload and response limits, rate/concurrency admission, and network isolation require a separately designed deployment. An OpenAI SDK `api_key` example does not add authentication to this Gradio client.
- Audio travels from browser to Gradio and then to the API. Gradio uses file-path inputs; the multipart builder reads the entire file into memory, and the example API also buffers and writes a temporary file. Do not promise no disk storage, immediate deletion, or safe unlimited uploads. Verify the chosen Gradio version's cache/retention behavior and provision private temporary storage, request-size and duration limits.
- The UI displays the server response and may show upstream error bodies, URLs, or exception details. Redact diagnostics before sharing; do not log raw error text, audio, or transcripts by default. Define access, retention, and deletion rules for both services.
- Validate the exact client/backend revisions with controlled files and your real gateway policy. Successful JSON display is not proof of diarization accuracy, identity recognition, throughput, cancellation, public-network isolation, or compatibility with every native server version.
