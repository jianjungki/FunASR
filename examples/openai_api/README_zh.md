([English](README.md)|简体中文|[日本語](README_ja.md)|[한국어](README_ko.md))

# FunASR OpenAI 兼容 API 服务

FunASR OpenAI 兼容 API 提供 `/v1/audio/transcriptions`，可作为私有语音转写服务接入 OpenAI 风格 SDK 或 multipart HTTP 客户端。它实现的是语音接口子集，不是完整 OpenAI API，也不保证兼容所有 SDK/框架功能。

本页启动仓库中的[示例服务](server.py)。打包的 `funasr-server` 是[另一套实现](../../funasr/bin/_server_app.py)，复用配置前请先看[接口边界](#api-contract)。如果需要进程内 `AutoModel.generate()` 而非 HTTP 请求，请查看 [Python SDK 指南](../../docs/python_api_zh.md)（[English](../../docs/python_api.md)）。

打包服务的维护入口见 [Agent 接入指南](../../docs/agent_integration_zh.md)。示例服务**没有内置鉴权或上传大小限制**，`api_key="not-needed"` 也不提供鉴权。本地测试应绑定回环地址；共享前需配置 TLS、网关鉴权、上传/超时/速率限制、音频及转写保留策略，并限制健康检查、模型列表和 schema 的访问，参见[安全指南](SECURITY_zh.md)。

## API Contract

- **在本目录运行示例 `python server.py`：**启动预加载与省略 multipart `model` 时的默认值均为 `sensevoice`。没有 `spk` 表单字段，只保留模型本身已经返回的说话人标签。
- **打包服务 `funasr-server`：**启动 `--model auto` 在设备字符串以 `cuda` 开头时选 `fun-asr-nano`，否则选 `sensevoice`；省略 multipart `model` 时仍独立默认选 `fun-asr-nano`。`spk=true` 为非原生说话人模型请求单独的说话人处理，默认 `False`。

每次请求都应明确指定 `model`：启动预加载与请求默认值是不同设置。请查询实际服务的 `/v1/models`；例如 `paraformer-en` 在示例服务中注册，却不是打包服务的内置别名。表单字段应以运行中服务的 `/openapi.json` 核对，不能只依赖仓库中的[示例规范](OPENAPI_zh.md)。

`response_format=verbose_json` 只选择响应格式，**不会启用说话人分离，也不会强制生成时间戳**。此示例仅在模型返回 `sentence_info` 时将其转换为 `segments`，否则返回 `segments=[]`。说话人标签可能缺失或为 null。MOSS 原生输出匿名标签，不需要 `spk=true` 或外部 VAD/CAM++。

SDK 的 `timestamp` 或 Nano 的 `timestamps` / `ctc_timestamps` 输出不会自动转换为 HTTP 片段。此示例接收 multipart `file`、`model`、`language`、`response_format`；SDK 的 `use_itn`、热词、原始数组及 `spk` 不是其表单字段。示例返回的 `language` 是请求提示或 `auto`，并非检测结果；打包服务可使用后端语言检测。

此示例的 `duration` 是 `generate()` 调用的耗时，单位为秒，不包含初次模型加载，**不是音频时长**。打包服务的 verbose 响应使用秒单位的音频时长，其 fallback 在无法读取音频元数据时可能使用 0。两套服务的片段 `start`/`end` 均为秒。打包服务的 fallback 可能根据文本与音频时长生成粗粒度片段，并非逐词强制对齐。打包服务的 verbose 结构包含 `task` 及片段 `id`/`words`，示例服务则包含 `model`，不能假设 JSON 字段完全相同。参见[响应示例与说话人请求](CLIENTS.md#api-contract)。

## 快速开始

准备 Python 3.11，在 POSIX shell 中创建新的源码目录：

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

这里仅固定源码，未固定依赖、模型权重、音频解码器或 CUDA；只安装 PyPI 包不会得到仓库示例。这些是安装操作说明，不代表已在你的硬件上验证全新安装或声学推理。

模型加载后再检查 `GET /health`；下载及启动耗时取决于 checkpoint、缓存、网络和硬件。健康检查成功不等于转写正确。除非另有说明，下文命令均在本目录执行。准备好 CUDA 依赖后，可将 CPU 启动命令替换为 `python server.py --host 127.0.0.1 --model sensevoice --device cuda --port 8000`，不要同时在相同端口启动两次。

需要直接复制的接入示例？可以继续查看 [客户端配方](CLIENTS.md)、[JavaScript/TypeScript 配方](JAVASCRIPT_zh.md)、[Gradio 浏览器 Demo](GRADIO_zh.md)、[工作流配方](WORKFLOWS_zh.md)、[Postman 集合](POSTMAN_zh.md)、[OpenAPI 规范](OPENAPI_zh.md)、[安全与网关指南](SECURITY_zh.md) 和 [Kubernetes 部署模板](kubernetes/README_zh.md)。

### 端到端 smoke test

在另一个终端进入同一源码目录、激活 `.venv`，再进入 `examples/openai_api`。以下可选脚本检查健康状态与转写：

```bash
bash smoke_test.sh
# 不依赖 curl/bash 的跨平台方式：
python smoke_test.py
```

等价手动命令使用公开的中文示例音频，不是日语或韩语验证集：

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

## Gradio 浏览器 Demo

本地文件上传或录制麦克风音频请使用维护中的 [Gradio 浏览器 Demo](GRADIO_zh.md)。它使用独立的 Python 3.12 环境 `.venv-gradio`，而不是本 API 服务的环境。指南覆盖 `funasr`、`vllm`、`sglang-omni` profiles、显式模型选择、Docker/Kubernetes 连通性、麦克风权限和隐私限制。UI 是独立 HTTP 客户端，不是鉴权网关或实时转写服务。

## 使用 OpenAI SDK

在同一已激活环境运行 `python -m pip install openai` 安装独立的 HTTP 客户端；它不是 FunASR Python SDK。将 `meeting.wav` 替换为解码环境支持的真实本地音频文件。

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed")

with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(model="sensevoice", file=audio)
print(result.text)

with open("meeting.wav", "rb") as audio:
    verbose = client.audio.transcriptions.create(
        model="sensevoice", file=audio, response_format="verbose_json",
    )
# verbose_json does not enable diarization; segments may be empty
print(getattr(verbose, "segments", []))
```

## 使用 curl

```bash
curl http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice

curl http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

## 可用模型

下列别名来自此示例的 `MODEL_CONFIGS`，不是整个 SDK 或所有服务统一支持的模型列表。接口会去除返回文本中的 `<|...|>` 富文本标签，不会输出独立的情感/事件字段。

- `sensevoice`：SenseVoiceSmall + FSMN-VAD。默认不启用句子时间戳或外部说话人聚类。
- `paraformer`：`paraformer-zh` + FSMN-VAD + CT 标点。已配置标点；仅设置 `verbose_json` 不会请求句子记录。
- `paraformer-en`：`paraformer-en` + FSMN-VAD。相对于打包服务，这是示例专有别名；此处没有配置标点组件。
- `fun-asr-nano`：`AutoModel` 加载 Fun-ASR-Nano，HF 平台 + FSMN-VAD。此示例不使用 vLLM；CTC 时间戳依赖完整 checkpoint 权重。
- `moss-transcribe-diarize`：第三方 OpenMOSS 原生转写/说话人适配器。需要独立依赖环境；保留模型返回的时间戳与匿名标签。

具体 checkpoint 的语言与许可证信息请查看[模型选择](../../docs/model_selection_zh.md) 和模型自身许可证。FunASR 软件的 MIT 许可证不代表所有模型权重的许可证。请在实际工作负载上测量所选路线，不应把别名当作统一的速度或容量规格。

Fun-ASR-MLT-Nano 是独立的多语种 checkpoint，不是这两套服务的内置别名；基础 Nano 不能据此宣称支持韩语。自定义 checkpoint 应走打包服务的 `--model-path`、`--hub` 与请求 `model="custom"`，这些不是示例服务的选项。具体环境与权重配置见模型选择和 Agent 指南。

MOSS 使用固定 revision 的第三方 HF 模型，不能外挂 VAD 或说话人模型。完整的
`funasr-server`、Docker Compose、Kubernetes、vLLM、SGLang Omni、LocalAI 与
FunClip 路径见 [MOSS 部署指南](../../docs/moss_transcribe_diarize_zh.md)。
说话人标签仅表示单段录音内的匿名说话人，不代表真实身份或跨录音识别。别名出现在 `/v1/models` 中，也不代表其依赖及权重已经就绪。

## API 端点

| Endpoint | Method | 说明 |
|---|---|---|
| `/v1/audio/transcriptions` | POST | OpenAI 兼容音频转写 |
| `/v1/models` | GET | 列出模型别名 |
| `/health` | GET | 健康检查、已加载模型和可用模型 |
| `/docs` | GET | FastAPI Swagger 文档 |

不想写代码验证接口时，可以使用 [Gradio 浏览器 Demo](GRADIO_zh.md) 做本地上传或麦克风测试，也可以导入 [Postman 集合](POSTMAN_zh.md)。如果要接入 API 网关、开发者门户或生成内部客户端，可以使用 [OpenAPI 规范](OPENAPI_zh.md)。

## Agent 与低代码工作流

可以通过 multipart HTTP 或工具函数模式接入 **LangChain**、**LlamaIndex**、**AutoGen**、**CrewAI**、**Semantic Kernel**、**Dify**、**n8n**，但应按本服务支持的字段验证具体集成。这些示例不保证兼容每个框架版本或实时 API。

两套服务均将工作流请求别名 `whisper-1` 映射到启动选择的模型，不会因此运行 OpenAI Whisper。工作流容器内的 `localhost` 指向该容器；应配置经过授权、可到达的网关或服务地址，不要用无保护的公网暴露绕过网络问题。

- SDK、JavaScript/TypeScript 和 Agent tool 写法见 [客户端配方](CLIENTS.md) 与 [JavaScript/TypeScript 配方](JAVASCRIPT_zh.md)。
- Dify、n8n、HTTP 节点和 webhook worker 见 [工作流配方](WORKFLOWS_zh.md)。
- 图形界面 smoke test 见 [Postman 集合](POSTMAN_zh.md)。
- schema 驱动导入见 [OpenAPI 规范](OPENAPI_zh.md)。

## Docker 部署

从仓库根目录执行下列命令。默认镜像以 CPU 模式启动示例 `server.py`，不是打包的 `funasr-server`。

以下仅是本地开发的端口发布设置，不提供鉴权。容器内仍监听 `0.0.0.0`，宿主机发布端口才绑定 `127.0.0.1`，不能将容器监听改为回环地址。当前 Dockerfile 安装未锁版本的 PyPI FunASR/依赖并复制此示例，不能视为上方固定源码的 Python 环境或可复现的声学环境。

```bash
cd examples/openai_api
cp .env.example .env

FUNASR_HOST_PORT=127.0.0.1:8000 docker compose up --build
```

等价 `docker run`：

```bash
docker build -t funasr-api .

docker run --rm -p 127.0.0.1:8000:8000 \
  -e FUNASR_DEVICE=cpu \
  -e FUNASR_MODEL=sensevoice \
  funasr-api
```

GPU 环境需要 NVIDIA Container Toolkit 和 CUDA-capable PyTorch/FunASR 镜像。适配 CUDA 依赖后，可使用：

```bash
docker run --rm --gpus all -p 127.0.0.1:8000:8000 \
  -e FUNASR_DEVICE=cuda \
  -e FUNASR_MODEL=sensevoice \
  funasr-api
```

验证容器：

```bash
BASE_URL=http://localhost:8000 bash smoke_test.sh
python smoke_test.py --base-url http://localhost:8000
```

可选的 [validate_docker.sh](validate_docker.sh) 整合了 build/run/smoke，但**默认向所有宿主机接口发布端口**，不会继承上方的回环地址设置。执行前须检查其网络配置；在共享网络做本地测试时，请使用上方明确绑定回环地址的 build/run/smoke 配方。脚本的 GPU 模式还需要 NVIDIA Container Toolkit 和 CUDA-capable 镜像。这些说明不代表已完成 Docker 或声学推理测试。

## Kubernetes 部署

在跨团队共享服务或通过网关暴露服务前，请先阅读 [安全与网关指南](SECURITY_zh.md)，补齐 TLS、鉴权、上传限制、限流和日志策略。

如果需要在集群内部提供带持久化模型缓存、健康检查和私有 `ClusterIP` 的语音 API，可以从 [Kubernetes 部署模板](kubernetes/README_zh.md) 开始。先构建并推送示例镜像，应用 manifests，再通过 `kubectl port-forward` 和 `python smoke_test.py --base-url http://localhost:8000` 验证。

在没有 CUDA-capable 镜像和 GPU 调度配置前，请保持默认 CPU 模式。

## 配置

以下默认值属于示例 `server.py`，不属于 `funasr-server`；参见[接口边界](#api-contract)。

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8000` | 监听端口 |
| `--device` | `cuda` | `cuda`、`cpu` 或 `mps` |
| `--model` | `sensevoice` | 启动时预加载模型 |

Docker 环境变量：

| Env | 默认值 | 说明 |
|---|---|---|
| `FUNASR_PORT` | `8000` | 传给 `server.py` 的容器端口 |
| `FUNASR_DEVICE` | `cpu` | 容器设备模式；只有在镜像已适配 CUDA 时才设为 `cuda` |
| `FUNASR_MODEL` | `sensevoice` | 容器启动时加载的模型别名 |

## 故障排查

| 现象 | 处理方式 |
|---|---|
| CUDA 不可用 | 先用 `--device cpu` 跑通 smoke test。 |
| 8000 端口被占用 | 改用 `--port 9000`，并运行 `BASE_URL=http://localhost:9000 bash smoke_test.sh` 或 `python smoke_test.py --base-url http://localhost:9000`。 |
| 模型下载很慢 | 换稳定网络，或提前从 ModelScope/Hugging Face 下载模型。 |
| Dify/n8n 容器里访问 `localhost` 失败 | 使用工作流运行时可访问的主机名、Compose service name 或 Kubernetes service name。 |
| 响应中没有 `segments` | 设置 `response_format=verbose_json` 可选择包含该字段的响应格式；数组仍可能为空，它不会启用时间戳或说话人分离。参见[接口边界](#api-contract)。 |
