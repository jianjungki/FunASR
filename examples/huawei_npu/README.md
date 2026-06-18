# FunASR Huawei Ascend NPU Support

This folder records the current FunASR support status for Huawei Ascend NPU and provides runnable checks for environments with CANN and `torch_npu` installed.

## Current support level

FunASR currently has **basic PyTorch NPU inference support** rather than a full Ascend-specific optimization stack.

| Area | Status | Notes |
| --- | --- | --- |
| Device selection | Supported | `AutoModel` accepts `device="npu:0"` and falls back to CPU when NPU is unavailable. |
| Availability check | Supported | `torch_npu.npu.is_available()` is used by `funasr.auto.auto_model.is_npu_available`. |
| OpenAI-compatible API container | Partial | `examples/openai_api/Dockerfile` has a `BUILD_DEVICE=npu` branch and recommends Huawei Ascend PyTorch base images. |
| Model coverage | Best effort | Most pure PyTorch inference models may work if all operators are supported by `torch_npu`; each model still needs validation. |
| Training | Not validated | No dedicated distributed NPU training scripts are present in this repository. |
| ONNX/runtime C++ acceleration | Not present | Existing runtime deployment docs focus on CPU/GPU-style runtime paths, not Ascend CANN runtime integration. |
| Ascend-specific graph/compiler optimization | Not present | No dedicated `torch_npu` graph mode, ATC/OM export, AOE tuning, or custom operator handling is present. |

## Environment prerequisites

Use a Huawei-supported Linux environment rather than Windows or macOS for actual NPU execution.

- Ascend driver and firmware installed on the host.
- CANN toolkit/runtime installed and sourced.
- Python version compatible with the selected Ascend PyTorch package.
- Matching `torch`, `torch_npu`, and `torchaudio` versions.
- FunASR installed from this repository or from PyPI.

A typical runtime environment should pass:

```bash
python check_env.py
```

## Minimal inference smoke test

After the environment check passes, run:

```bash
python smoke_infer.py --device npu:0 --model paraformer-zh
```

If no NPU is available, the script can verify fallback behavior:

```bash
python smoke_infer.py --device cpu --model paraformer-zh
```

## OpenAI API Docker path

The existing OpenAI-compatible API Dockerfile already includes a Huawei NPU branch. Build it with an Ascend PyTorch base image and `BUILD_DEVICE=npu`:

```bash
docker build \
  -f examples/openai_api/Dockerfile \
  --build-arg BASE_IMAGE=ascendhub.huawei.com/public-ascendhub/ascend-pytorch:2.1.0-ubuntu22.04 \
  --build-arg BUILD_DEVICE=npu \
  -t funasr-openai-npu \
  examples/openai_api
```

Run it with the Ascend device files and driver/runtime mounts required by your host deployment standard. Exact Docker run flags vary by Ascend driver, CANN version, and container runtime configuration.

For a full NPU-specific deployment checklist, see [`examples/huawei_npu/openai_api.md`](examples/huawei_npu/openai_api.md).

## Recommended next implementation steps

1. Validate representative models on a real Ascend card: `paraformer-zh`, `fsmn-vad`, `ct-punc`, `SenseVoiceSmall`, and speaker models.
2. Add model-specific compatibility notes for unsupported operators or dtype issues.
3. Add CI/manual test records for `device="npu:0"` inference.
4. Decide whether to keep support at PyTorch eager mode or add Ascend-specific export/optimization paths.
5. If serving is the priority, harden the OpenAI API Docker path first because it already has the most NPU-related scaffolding.

## Known caveats

- `device="npu:0"` only works when `torch_npu` is importable and reports an available NPU.
- FunASR falls back to CPU when NPU is unavailable, so logs should be checked to confirm that inference actually ran on NPU.
- Version matching is strict in Ascend environments; prefer Huawei official compatibility matrices over arbitrary PyPI combinations.
- Some audio preprocessing steps may still run on CPU even when model inference runs on NPU.
