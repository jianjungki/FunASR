# 官方 checkpoint 原生 vLLM 验证记录：Fun-ASR-Nano

[English](vllm_official_native_validation.md)

验证日期：**2026-09-07，Asia/Shanghai**，原始 HTTP Date 头对应 2026-09-06 UTC。
本记录独立验证官方
[FunAudioLLM/Fun-ASR-Nano-2512-vllm 快照](https://huggingface.co/FunAudioLLM/Fun-ASR-Nano-2512-vllm/tree/a4362c943d48951f98ca2a62181cc028970270c5)，
不可变 revision 为 `a4362c943d48951f98ca2a62181cc028970270c5`。
这是**模型 revision，不是根目录 FunASR Python 包版本**。本次使用 vLLM 原生
`FunASRForConditionalGeneration`，不经过 FunASR AutoModel，也不是
[split-engine 解码器路径](vllm_guide_zh.md)。

[2026-08-13 社区 checkpoint 历史记录](vllm_native_funasr_validation.md)
及其 `allendou/Fun-ASR-Nano-2512-vllm@e718b36e` benchmark 保持原样。
本次不是给旧数据换模型名称，也不说明官方模型更快。

## 验证范围与环境

8 个已记录 HTTP 请求均返回 200：健康检查、模型列表、中英日单请求转写、
中文热词请求，以及两个并发请求。全部 23 个文件直接从官方固定 revision 下载，
按 Hub Git/LFS 摘要验证，复制到持久备份后再次校验。
没有替换为社区缓存文件，也没有修改上游模型代码。

| 组件 | 实测值 |
| --- | --- |
| Python | 3.12.3 |
| vLLM | 0.27.1+cu129 |
| Torch | 2.13.0+cu129 |
| Transformers | 5.15.0 |
| CUDA runtime / NVIDIA 驱动 | 12.9 / 550.127.08 |
| GPU | 单张 NVIDIA H100 80GB HBM3 |
| 音频依赖 | av 18.1.0、soundfile 0.14.0、scipy 1.18.0、soxr 1.1.0、NumPy 2.3.5 |
| Hub 工具 / HTTP 客户端 | huggingface_hub 1.27.0 / requests 2.34.2 |
| 服务配置 | FP32、eager、GPU memory utilization 0.40、实际 max model length 40,960 |

这是**既有环境验证，不是全新安装验证**。没有安装、升级或重新解析依赖。
以上版本是环境观测结果，不是经全新安装验证的 lockfile。
不能据此宣称浮动 `pip install vllm` 或直接加载浮动 Hub 模型 ID 可复现本次结果。

[vLLM #54944](https://github.com/vllm-project/vllm/pull/54944) 于 2026-09-05
合并，merge commit 为 `e473e9036f979d546830aece9855027049faf0ba`。
它更新 supported-model 文档及测试 registry 的官方 checkpoint 引用，
没有修改推理实现。2026-09-07 审计时 main 已使用官方引用，
但 v0.28.0 仍引用社区产物。**已合并不等于已发布**。
本次也没有验证 main 或 v0.28.0，更不覆盖上游测试 registry 独立的
Transformers 版本约束。

## 准备固定的本地快照

以下命令将实际验证流程中的私有绝对路径替换成可移植变量。
请把 `VLLM_PYTHON` 指向已准备好且符合上表的环境；
示例 `.venv` 路径不代表本次新建过虚拟环境。
使用全新的隔离验证目录并保留下载 manifest。
可使用已有 Hub 认证，不要输出凭据。

```sh
export VLLM_PYTHON="$PWD/.venv/bin/python"
export VALIDATION_DIR="$PWD/.official-native-validation"
export MODEL_DIR="$VALIDATION_DIR/official-model/a4362c943d48951f98ca2a62181cc028970270c5"
```

在与实测相同的 native-import 上下文检查版本：

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

按不可变 revision 下载全部 23 个文件，先校验 Hub 元数据再启动。
此脚本不执行下载内容中的转换脚本，也不修改快照：

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

### Checkpoint 与音频摘要

音频均为单声道 48 kHz MP3。ffprobe 测得容器时长分别为
**中文 5.616 s、英文 7.176 s、日文 7.224 s**。
服务 usage 计数将其向上取整为 6/8/8 秒；取整值不是文件实测时长。

| 文件 | 字节数 | SHA256 |
| --- | --- | --- |
| `example/en.mp3` | 57441 | `f10378336a4e584f3f63799e62f99d5add3c2a401b51d3abe7d3a3a82f255ada` |
| `example/ja.mp3` | 57837 | `496dbc43b289e1d0d0cb916df9737450bca56acd8aaca046a7a2472363b1be53` |
| `example/zh.mp3` | 44973 | `0e64de19e4ff9a02e682955c9112f32d2317cfdbb5bc2f3504664044c993f195` |
| `model.safetensors` | 1970899072 | `96dfbec48282dd24d3334369a01e9e909f321ee39a1b0003c528c5379f68c1a6` |

[可复现元数据](benchmark/vllm_official_native_20260907.json) 包含全部
23 个文件的大小、SHA256、上游 Git/LFS 摘要、包版本、精确 HTTP 字段、
原始响应摘要及未取整耗时。公开内容省略私有主机路径、GPU 标识和凭据。
其中原始 `/v1/models` 响应的本地 root 保留在私有证据中；
其摘要对应原始字节，不是脱敏后的替代响应。

## 离线启动与 loopback

先确认 GPU 0 空闲、loopback 端口 57185 未被占用。如需换端口，
须同步更改所有请求；本记录只使用了 57185。在准备环境的 shell 中以前台启动：

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

实际服务加载经过验证的**本地快照**，Hub 与 Transformers 均为离线模式。
没有使用 `--trust-remote-code`，也没有让服务从浮动模型 ID 加载。
下载完成后，启动至健康状态耗时 84.123246 s；这不是启动性能保证。

在第二个 shell 中将 `VALIDATION_DIR` 和 `MODEL_DIR` 设为相同绝对路径，
然后等待健康检查成功：

```sh
curl --max-time 15 -fsS http://127.0.0.1:57185/health
curl --max-time 15 -fsS http://127.0.0.1:57185/v1/models
```

`/v1/models` 应包含 ID `fun-asr-nano-official-a4362c94`，其 root
应等于展开后的 `MODEL_DIR`。实测同时检查了二者。

## 实际转写请求

实测 harness 使用 Python requests，multipart 音频 MIME 为 `audio/mpeg`，
连接/读取超时为 5/45 s，显式传入 `language=zh`、`language=en`、
`language=ja` 和 `response_format=json`，没有覆盖 temperature 或生成长度。
以下等价 curl 保留实际请求字段，但没有单独测量 curl 耗时：

```sh
curl --max-time 45 -fsS http://127.0.0.1:57185/v1/audio/transcriptions -F "file=@$MODEL_DIR/example/zh.mp3;type=audio/mpeg" -F model=fun-asr-nano-official-a4362c94 -F language=zh -F response_format=json
curl --max-time 45 -fsS http://127.0.0.1:57185/v1/audio/transcriptions -F "file=@$MODEL_DIR/example/en.mp3;type=audio/mpeg" -F model=fun-asr-nano-official-a4362c94 -F language=en -F response_format=json
curl --max-time 45 -fsS http://127.0.0.1:57185/v1/audio/transcriptions -F "file=@$MODEL_DIR/example/ja.mp3;type=audio/mpeg" -F model=fun-asr-nano-official-a4362c94 -F language=ja -F response_format=json
curl --max-time 45 -fsS http://127.0.0.1:57185/v1/audio/transcriptions -F "file=@$MODEL_DIR/example/zh.mp3;type=audio/mpeg" -F model=fun-asr-nano-official-a4362c94 -F language=zh -F 'hotwords=开放时间,开放时间,开放时间' -F response_format=json
```

实际返回文本：

- 中文基线：开饭时间早上九点至下午五点。
- 英文：The tribal chieftain called for the boy, and presented him with fifty pieces of gold.
- 日文：うちの中学は弁当制で、持っていけない場合は、五十円の学校販売のパンを買う。
- 中文加 `hotwords=开放时间,开放时间,开放时间`：开放时间早上九点至下午五点。

保留基线误识别结果。重复热词只证明此样本输出发生改变，
不能直接推广为通用热词策略或准确率保证。

| 已记录请求 | HTTP | 客户端 wall time（秒） |
| --- | --- | --- |
| GET /health | 200 | 0.001023 |
| GET /v1/models | 200 | 0.002583 |
| POST zh (first) | 200 | 0.889547 |
| POST en | 200 | 0.386346 |
| POST ja | 200 | 0.473937 |
| POST zh + hotwords | 200 | 0.190610 |
| Concurrent en | 200 | 0.799900 |
| Concurrent ja | 200 | 0.904910 |

首次中文请求**未经转写预热**：它是健康检查和模型列表之后的第一个转写请求。
后续请求复用同一引擎。时间包含本地 HTTP 与解码，不含模型下载和服务启动；
每项只有一次观测，不是延迟分布。

四个顺序转写请求之后，双 worker 的 `ThreadPoolExecutor` 同时发出相同的
英文和日文 multipart 请求，均返回 200，文本与顺序请求一致。
两请求总 wall time 为 **0.9112209342420101 s（0.911 s）**，
包含 executor 建立与等待两项完成。这只是**两个请求的并发功能探针**，
不是吞吐量、生产容量或准确率研究，也不是与社区历史 1.123 s 探针的性能对比。

## Harness 边界与清理

首次 harness 尝试在**创建服务进程之前**被包清单 guard 拦截。
准备阶段导入 native vLLM，使 setuptools 的 vendored 包进入 `sys.path`，
原始 serve 阶段却使用不同导入上下文比较包清单。
统一导入上下文后差异为空，原始失败和修正均已保留。
早期失败状态字段曾误写为服务已启动，进程证据与修正记录确认当时没有启动。
没有修改依赖或模型代码；之后首次实际启动服务即完成 8 请求 smoke。

有时限的 harness 终止了自己创建的进程组，并等待服务及子进程退出。
服务退出码为 0、端口关闭、GPU 无计算进程，包与 native 源文件摘要不变。
独立检查再次确认全部 23 个原始文件及备份摘要、8 个原始响应、模型身份和清理状态。
手工复现后请停止前台服务，确认其 worker 与端口均已退出，不要终止无关 GPU 任务。

## 部署边界

这里只覆盖 request/response `/v1/audio/transcriptions`，没有验证
`/v1/realtime` 实时流式会话。长音频、说话人分离、时间戳准确率、
其他 GPU、持续负载与生产容量均不在范围内。
不能由原生服务推导 FunASR SDK 或包发布已通过验证。

worker 保持绑定 `127.0.0.1`。对外提供 API 前，由网关完成认证、
TLS、限流、音频大小/时长限制，隔离上传文件并落实保留策略。
网关不在本次 smoke 范围内。参见[部署矩阵](deployment_matrix_zh.md)和
[服务安全边界](../examples/openai_api/SECURITY_zh.md)。

