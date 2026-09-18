# FAQ and Troubleshooting

This compatibility page keeps earlier FAQ links usable. Detailed diagnosis and
current commands live in [troubleshooting](../troubleshooting.md) /
[中文](../troubleshooting_zh.md). Choose the model and runtime before applying a
workaround: Python SDK, Python HTTP, native vLLM and C++ WebSocket are distinct.

## Which install command should I use?

Follow [installation](../installation/installation.md). Choose a released PyPI
package or a recorded source checkout, install matching PyTorch/torchaudio builds,
and verify imports in the same environment used for inference. Repository
examples are not all installed as package data by PyPI.

## Which Python and PyTorch versions are recommended?

Use the selected model/backend's requirements, not a universal version promise.
The installation guide uses Python 3.11 as an environment example and explains
the difference between package metadata and resolved dependency requirements.
MOSS and vLLM have their own dependencies; keep conflicting stacks isolated.

## Model download is slow or fails. What should I check?

Check the chosen hub, full model ID, revision, cache permissions and available
disk space. See [models, cache and offline use](../installation/installation.md#4-models-cache-and-offline-use).
For offline inference, prepare every required model and dependency; disabling
FunASR's update check does not disable all network access.

## `funasr-server` says FastAPI or multipart packages are missing

Install the dependencies documented in the
[Python HTTP service guide](../../examples/openai_api/README.md) using the same
interpreter that launches the service. An SDK-only installation is not evidence
that an HTTP server or a model-specific backend is ready.

## Port 8000 is already in use

Choose another port with the service's `--port` option and update the client base
URL accordingly. For Compose, use its documented host-port setting. Verify the
health endpoint of the intended process before submitting audio.

## How do I verify the OpenAI-compatible API quickly?

Use the startup and transcription checks in the
[service guide](../../examples/openai_api/README.md). Compare the response with
the [HTTP schema](../../examples/openai_api/OPENAPI.md). A health response verifies
service readiness, not transcription accuracy or every optional output field.

## How do I run the OpenAI-compatible API with Docker Compose?

Follow the [Compose instructions](../../examples/openai_api/README.md) and
[container selection guide](../installation/docker.md). Verify image dependencies,
device, cache and ports together. Changing a device environment variable does
not add CUDA support to an image.

## Docker starts but `/health` or transcription fails

Inspect startup logs, model-loading state, dependencies, host-port mapping and
device availability. Preserve the failing configuration and relevant logs,
redacting secrets and private audio. Do not delete a shared model-cache volume
as a first diagnostic step; isolate an incomplete download only after identifying
it and retaining any needed local artifacts. See [troubleshooting](../troubleshooting.md).

## Long audio is slow, split incorrectly, or runs out of memory

Choose the workflow in the [Python SDK guide](../python_api.md). Paraformer-style
pipelines can use VAD and batch-size controls; shorter chunks can also introduce
boundary errors. Separate recognition, punctuation and timestamp errors before
changing segmentation. No single segment length is a universal accuracy fix.

[MOSS](../moss_transcribe_diarize.md) jointly transcribes and diarizes long-form
audio. Do not add external `vad_model` or `spk_model` to its adapter: independent
chunk processing can break recording-level speaker consistency. Check its own
context, output-token and device requirements instead.

## Speaker diarization has no speaker labels

There are two different routes:

- A Paraformer-style VAD/ASR/punctuation/speaker-embedding pipeline: inspect
  `sentence_info` and the [SDK speaker contract](../python_api.md#vad-timestamps-and-speakers).
- [MOSS-Transcribe-Diarize](../moss_transcribe_diarize.md): use its native labels,
  without a second VAD or speaker model. The adapter normalizes structured
  output into `sentence_info`; malformed tagged output must not invent labels.

Speaker labels are anonymous within a recording. They do not identify an enrolled
person and are not guaranteed to match labels in another recording.

## Can I use a speaker model other than cam++?

For the embedding-based pipeline, use a compatible registered speaker model
whose inference output contains `spk_embedding`; then test clustering with the
chosen ASR/VAD pipeline. See the
[SDK contract](../python_api.md#vad-timestamps-and-speakers) and
[model registration](../model_registration.md).
A model that emits diarized segments directly is not interchangeable with a
speaker-embedding model. MOSS uses its dedicated adapter, not `spk_model`.

## The same command works on CPU but fails on CUDA

Record the driver, GPU, Python, PyTorch, torchaudio and CUDA build versions,
then check device support and peak memory for that model. Start with the
[environment checks](../installation/installation.md#3-verify-the-interpreter-and-imports)
and [troubleshooting](../troubleshooting.md). A CPU success does not establish GPU
wheel or model compatibility.

## What information should I include in an issue?

Provide a minimal command or script, expected versus actual output, package and
source versions, model ID/revision, runtime/device details, and relevant logs.
Include audio duration, format, sample rate and a shareable reproducer when
permitted. Remove credentials, private endpoints and personal audio before
posting. Keep the issue open while the proposed fix is being verified.

## Existing ModelScope pipeline examples

These are historical community discussions. Check their source/package versions
before reusing code; begin new integrations with the maintained SDK guide.

- [VAD model with ModelScope pipeline](https://github.com/modelscope/FunASR/discussions/236)
- [Punctuation model with ModelScope pipeline](https://github.com/modelscope/FunASR/discussions/238)
- [Paraformer streaming with ModelScope pipeline](https://github.com/modelscope/FunASR/discussions/241)
- [VAD + ASR + punctuation with ModelScope pipeline](https://github.com/modelscope/FunASR/discussions/278)
- [VAD + ASR + punctuation + NNLM with ModelScope pipeline](https://github.com/modelscope/FunASR/discussions/134)
- [Timestamp prediction with ModelScope pipeline](https://github.com/modelscope/FunASR/discussions/246)
- [Switch online/offline decoding for UniASR](https://github.com/modelscope/FunASR/discussions/151)
