# OpenAI-compatible API on Huawei Ascend NPU

This guide explains how to run the existing FunASR OpenAI-compatible API example on Huawei Ascend NPU. It reuses the implementation in `examples/openai_api` and focuses on the NPU-specific setup, startup, and validation steps.

## Relationship to the shared OpenAI API example

The Huawei NPU path does not duplicate the API server. It uses the existing OpenAI-compatible implementation:

- `examples/openai_api/server.py`: FastAPI server exposing `/v1/audio/transcriptions`, `/v1/models`, and `/health`.
- `examples/openai_api/Dockerfile`: Docker build path with `BUILD_DEVICE=npu` support.
- `examples/openai_api/smoke_test.py`: HTTP smoke test for health, model listing, and transcription.
- `examples/openai_api/smoke_test.sh`: curl-based smoke test.

Use this file as the Ascend deployment checklist around those shared files.

## Prerequisites

Run on a Huawei-supported Linux host with:

- Ascend driver and firmware installed.
- CANN runtime/toolkit installed and sourced.
- Matching `torch`, `torch_npu`, and `torchaudio` versions.
- FunASR installed from this repository or inside the OpenAI API container.
- `examples/huawei_npu/check_env.py` passing in the target environment.

Before starting the API, verify the local environment:

```bash
cd examples/huawei_npu
python check_env.py
python smoke_infer.py --device npu:0 --model paraformer-zh
```

## Run directly with Python

From the repository root, install the OpenAI API dependencies according to `examples/openai_api/README.md`, then start the server with an NPU device:

```bash
cd examples/openai_api
python server.py --host 0.0.0.0 --port 8000 --model sensevoice --device npu:0
```

Useful alternatives:

```bash
python server.py --host 0.0.0.0 --port 8000 --model paraformer --device npu:0
python server.py --host 0.0.0.0 --port 8000 --model paraformer-en --device npu:0
```

Confirm that `/health` reports the expected device:

```bash
curl http://localhost:8000/health
```

If the server reports CPU instead of NPU, check whether `torch_npu` is importable and whether `torch_npu.npu.is_available()` returns true.

### NPU frontend switch

The server now supports an optional frontend acceleration switch that keeps the original behavior by default:

- `FUNASR_NPU_FRONTEND=auto`: try the NPU frontend when the request device is NPU, then fall back to the original Kaldi frontend on failure.
- `FUNASR_NPU_FRONTEND=off`: always use the original CPU-compatible frontend path.
- `FUNASR_NPU_FRONTEND=force`: require the NPU frontend and raise an error if it cannot run.

You can set it through the environment or the server CLI:

```bash
cd examples/openai_api
FUNASR_NPU_FRONTEND=auto python server.py --host 0.0.0.0 --port 8000 --model sensevoice --device npu:0
python server.py --host 0.0.0.0 --port 8000 --model sensevoice --device npu:0 --npu-frontend force
```

### Throughput-oriented API settings

For lowest latency and higher throughput, keep the default plain `json` response format. The API skips timestamp segment construction and speaker diarization unless a rich output format (`verbose_json`, `srt`, or `vtt`) requests it.

Useful server knobs:

- `FUNASR_ENABLE_SPK=0`: keep speaker diarization disabled to avoid loading and running the speaker model.
- `FUNASR_BATCH_SIZE_S=300`: control the maximum ASR batch duration in seconds for VAD-sliced audio.
- `FUNASR_BATCH_SIZE_THRESHOLD_S=60`: avoid grouping very long segments into the same batch.
- `FUNASR_MERGE_LENGTH_S=15`: control VAD segment merge length before ASR batching.

Example NPU startup focused on throughput:

```bash
cd examples/openai_api
FUNASR_NPU_FRONTEND=auto FUNASR_ENABLE_SPK=0 FUNASR_BATCH_SIZE_S=600 \
  python server.py --host 0.0.0.0 --port 8000 --model sensevoice --device npu:0
```

## Build the NPU Docker image

Use the existing OpenAI API Dockerfile with a Huawei Ascend PyTorch base image and `BUILD_DEVICE=npu`:

```bash
docker build \
  -f examples/openai_api/Dockerfile \
  --build-arg BASE_IMAGE=ascendhub.huawei.com/public-ascendhub/ascend-pytorch:2.1.0-ubuntu22.04 \
  --build-arg BUILD_DEVICE=npu \
  -t funasr-openai-npu \
  examples/openai_api
```

The base image, CANN version, PyTorch version, and `torch_npu` version must match the host driver/runtime compatibility matrix. Prefer Huawei-published image tags for production deployments.

## Run the NPU container

Exact runtime flags vary by Ascend driver, CANN version, and container runtime configuration. A deployment usually needs Ascend device nodes plus driver/runtime mounts from the host. Use your platform's standard Ascend Docker run template, then pass `--device npu:0` to the API process.

Example shape:

```bash
docker run --rm -p 8000:8000 \
  --name funasr-openai-npu \
  funasr-openai-npu \
  python server.py --host 0.0.0.0 --port 8000 --model sensevoice --device npu:0
```

If your base image already defines the API startup command, configure the device through the server arguments or environment wrapper used by your deployment system.

## Validate the API

Run the Python smoke test:

```bash
cd examples/openai_api
python smoke_test.py --base-url http://localhost:8000 --model sensevoice --response-format verbose_json
```

Or run the curl-based smoke test:

```bash
cd examples/openai_api
BASE_URL=http://localhost:8000 MODEL=sensevoice RESPONSE_FORMAT=verbose_json bash smoke_test.sh
```

A manual OpenAI-compatible request looks like:

```bash
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F "file=@sample.wav" \
  -F "model=sensevoice" \
  -F "response_format=verbose_json"
```

## Model validation checklist

Validate each model separately on the target NPU before declaring it supported:

1. `sensevoice`: validates `iic/SenseVoiceSmall`, VAD, punctuation, and speaker-related optional paths.
2. `paraformer`: validates the common Mandarin ASR path with `fsmn-vad` and `ct-punc`.
3. `paraformer-en`: validates the English ASR path.
4. Custom model paths: validate operator coverage, dtype behavior, and memory usage.

For each model, record:

- `torch`, `torch_npu`, CANN, and driver versions.
- Actual device reported by `/health`.
- First-request model load time.
- Short and long audio latency.
- Any unsupported operator, dtype, or CPU fallback warning.

## Known caveats

- FunASR falls back to CPU when NPU is unavailable, so always check `/health` and server logs.
- Some preprocessing and postprocessing may still run on CPU even when model inference runs on NPU.
- The shared OpenAI API server currently accepts a device string but is not deeply optimized for Ascend graph/compiler modes.
- Docker runtime flags are intentionally not hard-coded here because they depend on the installed Ascend runtime stack.
