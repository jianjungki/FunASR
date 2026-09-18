# Official native vLLM validation: Fun-ASR-Nano

[中文](vllm_official_native_validation_zh.md)

Verified **2026-09-07, Asia/Shanghai** (raw HTTP Date headers: 2026-09-06 UTC).
This is a separate functional serving record for the official
[FunAudioLLM/Fun-ASR-Nano-2512-vllm snapshot](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-2512-vllm/tree/a4362c943d48951f98ca2a62181cc028970270c5),
revision `a4362c943d48951f98ca2a62181cc028970270c5`.
It is a **model revision, not a root FunASR package version**. This run used
vLLM's native `FunASRForConditionalGeneration`, not FunASR AutoModel or the
[split-engine decoder path](vllm_guide.md).

The [2026-08-13 historical community validation](vllm_native_funasr_validation.md)
and its community `allendou/Fun-ASR-Nano-2512-vllm@e718b36e` benchmark remain
unchanged. The official run is not a relabeling of those timings or evidence of
a speed improvement.

## Tested scope and environment

Eight recorded HTTP requests returned 200: health, model discovery, three
single-language transcriptions, Chinese hotwords, and two concurrent requests.
All 23 files were downloaded directly from the pinned official repository,
verified against Hub Git/LFS digests, copied to a durable backup, and rehashed.
The test did not substitute community cache files or modify upstream model code.

| Component | Observed value |
| --- | --- |
| Python | 3.12.3 |
| vLLM | 0.27.1+cu129 |
| Torch | 2.13.0+cu129 |
| Transformers | 5.15.0 |
| CUDA runtime / NVIDIA driver | 12.9 / 550.127.08 |
| GPU | One NVIDIA H100 80GB HBM3 |
| Audio libraries | av 18.1.0, soundfile 0.14.0, scipy 1.18.0, soxr 1.1.0, NumPy 2.3.5 |
| Hub tooling / HTTP client | huggingface_hub 1.27.0 / requests 2.34.2 |
| Server | FP32, eager, GPU memory utilization 0.40, resolved max model length 40,960 |

This validated an **existing environment, not a clean installation**. No packages
were installed, upgraded or re-resolved. These observed versions are not a
newly validated dependency lockfile. In particular, do not infer that an
unconstrained `pip install vllm` or a floating Hub loader reproduces this run.

[vLLM #54944](https://github.com/vllm-project/vllm/pull/54944) merged at
`e473e9036f979d546830aece9855027049faf0ba` on 2026-09-05. It updates the
supported-model documentation and test registry to the official checkpoint,
not the inference implementation. At the 2026-09-07 audit, main used the
official reference but v0.28.0 still referenced the community artifact.
Merged does not mean released. This run validates neither main nor v0.28.0,
and does not override the upstream test registry's separate Transformers
version constraint.

## Prepare a pinned local snapshot

The following commands are a portable transcription of the tested preparation
and launch procedure: private absolute paths are replaced by variables.
Point `VLLM_PYTHON` at an already provisioned environment matching the table;
the `.venv` path below is a placeholder, not a venv creation command.
Use a new isolated validation directory and keep its download manifest.
Existing Hub authentication may be used without displaying credentials.

```sh
export VLLM_PYTHON="$PWD/.venv/bin/python"
export VALIDATION_DIR="$PWD/.official-native-validation"
export MODEL_DIR="$VALIDATION_DIR/official-model/a4362c943d48951f98ca2a62181cc028970270c5"
```

Check versions in the same native-import context used during validation:

```sh
"$VLLM_PYTHON" - <<'PY'
import importlib.metadata as metadata
import torch
import vllm.model_executor.models.funasr

for name, expected in {"vllm": "0.27.1+cu129", "torch": "2.13.0+cu129",
                       "transformers": "5.15.0"}.items():
    assert metadata.version(name) == expected, (name, metadata.version(name))
assert torch.version.cuda == "12.9" and torch.cuda.is_available()
PY
```

Download all 23 files at the immutable revision and verify the official Hub
metadata before serving. The script does not execute the downloaded conversion
script and does not modify the snapshot:

```sh
HF_HUB_DISABLE_TELEMETRY=1 HF_XET_CACHE="$VALIDATION_DIR/isolated-xet-cache" "$VLLM_PYTHON" - <<'PY'
import hashlib
import json
import os
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

model_id = "FunAudioLLM/Fun-ASR-Nano-2512-vllm"
revision = "a4362c943d48951f98ca2a62181cc028970270c5"
root = Path(os.environ["MODEL_DIR"])
info = HfApi().model_info(model_id, revision=revision, files_metadata=True)
assert info.sha == revision and len(info.siblings) == 23
snapshot_download(model_id, revision=revision, local_dir=str(root),
                  cache_dir=str(Path(os.environ["VALIDATION_DIR"]) / "isolated-hf-cache"),
                  max_workers=4)
files = []
for item in info.siblings:
    content = (root / item.rfilename).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert len(content) == item.size, item.rfilename
    if item.lfs:
        assert digest == item.lfs.sha256, item.rfilename
    else:
        assert hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest() == item.blob_id
    files.append({"path": item.rfilename, "size": len(content), "sha256": digest})
assert json.loads((root / "config.json").read_text())["architectures"] == ["FunASRForConditionalGeneration"]
(root.parent / "download-manifest.json").write_text(json.dumps(files, indent=2) + "\n")
PY
```

### Checkpoint and sample hashes

All examples are mono 48 kHz MP3. Container durations measured by ffprobe were
**zh 5.616 s, en 7.176 s, ja 7.224 s**. Server usage counters rounded those to
6/8/8 seconds; those rounded values are not the measured file durations.

| File | Bytes | SHA256 |
| --- | --- | --- |
| `example/en.mp3` | 57441 | `f10378336a4e584f3f63799e62f99d5add3c2a401b51d3abe7d3a3a82f255ada` |
| `example/ja.mp3` | 57837 | `496dbc43b289e1d0d0cb916df9737450bca56acd8aaca046a7a2472363b1be53` |
| `example/zh.mp3` | 44973 | `0e64de19e4ff9a02e682955c9112f32d2317cfdbb5bc2f3504664044c993f195` |
| `model.safetensors` | 1970899072 | `96dfbec48282dd24d3334369a01e9e909f321ee39a1b0003c528c5379f68c1a6` |

The [reproducibility metadata](benchmark/vllm_official_native_20260907.json)
contains all 23 file sizes, SHA256 and upstream Git/LFS digests, observed package
versions, exact HTTP fields, original response hashes and unrounded timings.
Private host paths, GPU identifiers and credentials are not published. In
particular, the raw `/v1/models` response's local root is retained in private
evidence; its digest refers to the original bytes, not a redacted replacement.

## Launch offline on loopback

First ensure GPU 0 is idle and loopback port 57185 is free. Choose another free
port consistently in every command if necessary; only 57185 was used in this
record. Run in the foreground from the prepared shell:

```sh
CUDA_VISIBLE_DEVICES=0 PYTHONDONTWRITEBYTECODE=1 \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
HF_HUB_DISABLE_IMPLICIT_TOKEN=1 HF_HUB_DISABLE_TELEMETRY=1 VLLM_NO_USAGE_STATS=1 \
VLLM_CACHE_ROOT="$VALIDATION_DIR/runtime-cache" TRITON_CACHE_DIR="$VALIDATION_DIR/triton-cache" \
"$VLLM_PYTHON" -B -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_DIR" --served-model-name fun-asr-nano-official-a4362c94 \
  --host 127.0.0.1 --port 57185 --dtype float32 \
  --gpu-memory-utilization 0.40 --enforce-eager
```

The engine loaded the verified **local snapshot** with Hub and Transformers
offline. No `--trust-remote-code` or floating model ID loader was used.
Startup to healthy took 84.123246 s; download was already complete. This startup
observation is not a startup performance guarantee.

In a second shell, set `VALIDATION_DIR` and `MODEL_DIR` to the same absolute
paths as above, then wait for readiness:

```sh
curl --max-time 15 -fsS http://127.0.0.1:57185/health
curl --max-time 15 -fsS http://127.0.0.1:57185/v1/models
```

`/v1/models` must contain ID `fun-asr-nano-official-a4362c94` and a root equal
to your resolved `MODEL_DIR`. The recorded run checked both.

## Actual transcription requests

The harness used Python requests with multipart audio MIME `audio/mpeg`,
connect/read timeouts of 5/45 s, explicit `language=zh`, `language=en` and
`language=ja`, and `response_format=json`. It sent no temperature or
generation-length override. These equivalent curl requests preserve those
fields; their timings have not been separately measured:

```sh
curl --max-time 45 -fsS http://127.0.0.1:57185/v1/audio/transcriptions -F "file=@$MODEL_DIR/example/zh.mp3;type=audio/mpeg" -F model=fun-asr-nano-official-a4362c94 -F language=zh -F response_format=json
curl --max-time 45 -fsS http://127.0.0.1:57185/v1/audio/transcriptions -F "file=@$MODEL_DIR/example/en.mp3;type=audio/mpeg" -F model=fun-asr-nano-official-a4362c94 -F language=en -F response_format=json
curl --max-time 45 -fsS http://127.0.0.1:57185/v1/audio/transcriptions -F "file=@$MODEL_DIR/example/ja.mp3;type=audio/mpeg" -F model=fun-asr-nano-official-a4362c94 -F language=ja -F response_format=json
curl --max-time 45 -fsS http://127.0.0.1:57185/v1/audio/transcriptions -F "file=@$MODEL_DIR/example/zh.mp3;type=audio/mpeg" -F model=fun-asr-nano-official-a4362c94 -F language=zh -F 'hotwords=开放时间,开放时间,开放时间' -F response_format=json
```

Observed texts:

- Chinese baseline: 开饭时间早上九点至下午五点。
- English: The tribal chieftain called for the boy, and presented him with fifty pieces of gold.
- Japanese: うちの中学は弁当制で、持っていけない場合は、五十円の学校販売のパンを買う。
- Chinese with `hotwords=开放时间,开放时间,开放时间`: 开放时间早上九点至下午五点。

The baseline error is preserved. Repeating this hotword changed this sample's
output; it is not a general hotword policy or an accuracy guarantee.

| Recorded request | HTTP | Client wall seconds |
| --- | --- | --- |
| GET /health | 200 | 0.001023 |
| GET /v1/models | 200 | 0.002583 |
| POST zh (first) | 200 | 0.889547 |
| POST en | 200 | 0.386346 |
| POST ja | 200 | 0.473937 |
| POST zh + hotwords | 200 | 0.190610 |
| Concurrent en | 200 | 0.799900 |
| Concurrent ja | 200 | 0.904910 |

The first Chinese call was **not warmed**: it was the first transcription
after health and model discovery. Later calls reused that engine.
Times include local HTTP and decoding, exclude model download and startup,
and are single observations, not latency distributions.

After the four sequential transcription calls, a two-worker
`ThreadPoolExecutor` sent the same English and Japanese multipart requests.
Both returned 200 with the same texts. The combined wall time was
**0.9112209342420101 s (0.911 s)**, including executor setup and waiting for both
results. This is only a **two-request functional concurrency probe**, not
throughput, production capacity, an accuracy study or a comparison with the
historical 1.123 s community probe.

## Harness boundary and cleanup

The first harness attempt failed a package-inventory guard **before server
spawn**. Preparation imported native vLLM, which exposed setuptools vendored
distributions on `sys.path`; the original serve phase compared a different
import context. Matching that import produced an empty package difference.
The original failure and correction were preserved. An early failure status
flag incorrectly said the server had started; process evidence and the
correction establish that it had not. No dependency or model-code changes were
needed. The first actual server launch then completed the eight-request smoke.

The bounded harness terminated its own process group and waited for the
server and children. Server exit code was 0, the loopback port closed, and no
GPU compute processes remained. Package and native source hashes were
unchanged. A separate check confirmed all 23 original and backup file hashes,
eight raw responses, model identity and cleanup. When reproducing manually,
stop the foreground server after the probes and verify its workers and port
are gone; do not terminate unrelated GPU jobs.

## Deployment boundaries

This is request/response `/v1/audio/transcriptions`, not a validated
`/v1/realtime` streaming session. Long audio, speaker diarization, timestamp
accuracy, other GPUs, sustained load and production capacity were not tested.
Do not infer a FunASR SDK or package-release validation from this native server.

Keep the worker on `127.0.0.1`. Before exposing an API, use a gateway for
authentication, TLS, rate limits and audio size/duration limits, with isolated
uploads and a retention policy. That gateway was not part of this smoke.
See the [deployment matrix](deployment_matrix.md) and
[security boundaries](../examples/openai_api/SECURITY.md).

