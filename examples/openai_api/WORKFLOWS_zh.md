# FunASR OpenAI 兼容 API 低代码工作流配方

[English](WORKFLOWS.md)

当你希望让 Dify、n8n、HTTP 节点、webhook worker 或其他低代码工作流引擎调用私有 FunASR 语音 API 时，可以从这份配方开始。这些是 multipart HTTP 接入示例，不是对所有工作流产品或版本的兼容保证。

示例服务**没有内置鉴权或上传大小限制**。客户端 URL 中的 `localhost` 不会限制服务端监听地址。本地检查只绑定 loopback；共享前按[安全与网关指南](SECURITY_zh.md)配置 TLS、网关鉴权、上传/时限/速率限制、health/model/schema 私有访问和音频/转写保留策略。占位 API key 不会让服务具备鉴权。

## 服务预检

先按[示例 README](README_zh.md#快速开始)准备 checkout 和环境。其中固定的源码 revision 不是依赖/模型锁定，也不代表已验证全新安装。以下命令从该 checkout 根目录开始，假定 `.venv` 已准备好。如果服务已经运行，跳过启动直接检查，不要在同一端口启动第二个进程。

```bash
cd examples/openai_api
source ../../.venv/bin/activate
python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000
```

准备好 CUDA 依赖后，可将 CPU 命令替换为 `python server.py --host 127.0.0.1 --model sensevoice --device cuda --port 8000`。另一个实现即打包的 `funasr-server` 路线见 [Agent 集成指南](../../docs/agent_integration_zh.md)，其启动默认值、别名和响应字段与本示例不同。

在同一主机的第二个终端进入同一 checkout 的 `examples/openai_api` 目录，激活同一环境。等待模型加载后检查本地服务：

```bash
source ../../.venv/bin/activate
export FUNASR_BASE_URL="http://127.0.0.1:8000"
curl -fsS "$FUNASR_BASE_URL/health"
curl -fsS "$FUNASR_BASE_URL/v1/models"
curl -fsS "$FUNASR_BASE_URL/openapi.json"
```

健康与 schema 检查不验证声学正确性。下方转写命令的 `meeting.wav` 应替换为已有本地音频；README 的公开中文 smoke 样例不是多语言准确率基准。

如果工作流引擎运行在 Docker 中，`localhost` 通常指的是工作流容器自身；主机 loopback 服务不会自动对容器可达。请明确配置私有网关/容器网络，再将 `FUNASR_BASE_URL` 和 worker 的 `FUNASR_URL` 替换为工作流运行时能访问的地址。需要网关鉴权时使用真实凭据；下方本地 curl/Python 示例没有添加鉴权 header。不要为解决连通性而把未鉴权端口直接暴露到公网。

## Postman smoke test

在配置低代码工具前，可以先导入 [Postman collection](POSTMAN_zh.md)，从图形界面跑通 health、模型列表和转写请求；需要按 schema 导入时可使用 [OpenAPI spec](OPENAPI_zh.md)。设置 `FUNASR_BASE_URL`，在 multipart `file` 字段选择本地音频文件，第一次测试建议保持 `MODEL_ALIAS=sensevoice`。

处理离线多人会议时，先按 [MOSS 部署指南](../../docs/moss_transcribe_diarize_zh.md)准备独立的第三方 MOSS 服务，包括 GPU 和文件时长边界。再将 `MODEL_ALIAS` 改为 `moss-transcribe-diarize`，保留 `response_format=verbose_json` 以保留可用的原生匿名说话人 segments。不要添加外部 VAD 或 `spk=true`；录音内标签不是已验证身份，也不是跨录音稳定编号。只修改客户端别名不会完成服务环境准备。

## Multipart HTTP 请求

所有工作流引擎最终都需要发出下面这种请求：

- **Method:** `POST`
- **URL:** `http://<funasr-host>:8000/v1/audio/transcriptions`
- **Body type:** `multipart/form-data`
- **File field:** `file`
- **Text field:** `model=sensevoice`
- **Text field:** `response_format=verbose_json`
- **Timeout:** 根据最长音频时长设置，例如长录音可先设为 300 秒。

等价 curl 命令：

```bash
curl -fsS "$FUNASR_BASE_URL/v1/audio/transcriptions" \
  -F file=@meeting.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

将 `text` 映射为转写文本。`response_format=verbose_json` 只选择格式，不开启说话人分离，也不强制生成时间戳。消费其他字段前，先看[客户端响应契约](CLIENTS.md#response-formats)：

- **示例 `server.py`：** `segments` 只来自模型返回的 `sentence_info`，否则为 `segments=[]`。`duration` 是 `generate()` 调用周围的耗时秒数，不含初次模型加载，不是录音时长。`model` 是解析后的请求别名；`language` 回显提交的提示或 `auto`，不是检测出的语言。
- **打包 `funasr-server`：** `duration` 是音频时长秒数，fallback 无法读取音频元数据时可能为 0。它可能返回按文本生成的粗粒度片段，不是强制对齐。verbose 响应有 `task` 和片段 `id`/`words`，但没有顶层 `model`；语言可使用后端检测结果。对非原生说话人模型，`spk=true` 请求独立说话人流程，仍依赖其模型和环境。示例服务没有 `spk` 表单字段。

片段 `start`/`end` 单位为秒，不是 SDK 的毫秒坐标。`speaker` 字段可能缺失、为 null、数字或字符串；标签不标识真实身份。非空片段或 `verbose_json` 都不保证准确字幕对齐。HTTP 展示文本会剥离 SenseVoice 富标签，不等于 SDK 原始标签结果，也不是独立的情绪/事件响应。SDK 字段/选项如 `timestamp`、`timestamps`、`ctc_timestamps`、`use_itn`、hotwords 和原始数组不是额外表单字段；原始 SDK 时间戳不会自动转成 HTTP segments。

以下是没有 `sentence_info` 的示例服务响应；`0.42` 是处理耗时，不是音频时长：

```json
{"text": "recognized speech", "segments": [], "language": "auto", "duration": 0.42, "model": "sensevoice"}
```

以下是 3.2 秒文件对应的打包服务响应示意，含粗粒度 fallback 片段，未开启说话人选项。这些示例说明 schema，不是新模型测量：

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

## Dify 自定义工具或 HTTP 节点

当 Dify 应用接收上传音频文件，或收到内部音频存储 URL 时，可以使用下面两种模式。

### 直接上传文件

在 HTTP request 节点或自定义工具中配置：

- Method: `POST`
- URL: `http://<funasr-host>:8000/v1/audio/transcriptions`
- Body: `multipart/form-data`
- File part: `file`，绑定到上传音频变量
- Text parts: `model=sensevoice`、`response_format=verbose_json`
- Output variable: 把 `text` 映射为转写文本；使用时间戳或说话人标签前检查 `segments` 是否可用及其来源

### 音频 URL 转写

有些工作流工具只能传文件 URL，而不能直接传 multipart 二进制。multipart `file` 字段中的 URL 字符串不是音频上传。优先直接上传二进制，或传受控存储对象 ID 并由经过审查的存储客户端解析。

下面的 sketch 仅用于运维人员批准的可信存储 URL。目标 allowlist、私网访问策略、重定向校验、下载字节上限与鉴权均**未实现**。`requests.get` 会跟随重定向并将整个响应缓存在内存中；其 timeout 不是字节限制，也不是完整的端到端截止时限。不要把用户提供的 URL 传给这个 helper。接受这些 URL 前，必须使用经过审查的下载边界执行全部控制，包括阻止非预期私网/元数据目标并检查每次重定向。位于可信内网并不能防止 SSRF。

对于这个可信输入示意：

1. 运维人员向 worker 提供已批准的音频 URL 和元数据。
2. worker 从可信存储下载音频。
3. worker 使用 multipart 请求调用 FunASR。
4. worker 返回服务 JSON，由下游检查可选字段。日志不得暴露签名 URL、凭据或私有转写。

在同一已激活的客户端环境安装独立 HTTP 依赖：

```bash
python -m pip install requests
```

按已准备的服务设置 `FUNASR_URL`；默认值用于同主机 worker。工作流可导入以下函数定义，但它们不创建 HTTP 监听器，也不实现入站鉴权/上传限制。

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

请把此示意限制在已批准输入内；仅校验主机名不是完整的安全下载策略。

## n8n HTTP Request 节点

一个常见 n8n 流程是：触发器 -> 二进制音频数据 -> HTTP Request -> 转写结果消费节点。

推荐 HTTP Request 配置：

- **Method:** `POST`
- **URL:** `http://<funasr-host>:8000/v1/audio/transcriptions`
- **Send Body:** enabled
- **Body Content Type:** `Form-Data` / multipart
- **Binary file field:** `file`
- **Additional form fields:** `model=sensevoice`、`response_format=verbose_json`
- **Response Format:** JSON
- **Timeout:** 长录音场景需要调大。

请求之后，使用 `{{$json.text}}` 作为转写文本。先检查 `{{$json.segments}}` 存在且适合任务，再传给后续节点；空片段或粗粒度片段不能作为已验证字幕时刻或说话人分离结果。节点标签和二进制属性配置随所安装的 n8n 版本变化；`file` 是发出的 multipart 字段名，不一定是传入二进制属性的名字。

### n8n OpenAI Audio 节点

对于发送 `model=whisper-1` 的 OpenAI Audio > Transcribe 节点版本，FunASR 会把该兼容别名映射到服务启动时选择的模型，而不是选择 Whisper checkpoint。Base URL 使用可达服务地址并带 `/v1`。非空占位 key 仅适用于未保护的本地端点，访问鉴权网关时应提供真实凭据。请核验所安装节点版本的请求行为，不要假定所有版本相同。此配方用于纯文本转写；需要显式 `response_format` 或服务支持的说话人选项时使用 HTTP Request 节点，仍受上述响应边界限制。

## Webhook worker 模式

当工作流引擎不能稳定发送 multipart 文件，或音频需要预处理时，可以使用这个函数。此 POSIX 临时文件示例使用同一个 `requests` 依赖，并关闭上传句柄。它接受已在内存中的 bytes，应在缓冲之前限制上传大小；它是函数，不是受保护的 webhook 服务。

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

这里未实现音频转码、文件大小检查、请求 ID、入站/上游鉴权和重试策略。共享前在相应边界执行这些控制；重试可能重复执行昂贵的转写工作。

## 生产环境护栏

- 在跨团队共享 FunASR 服务前，先加好鉴权、TLS、上传大小限制和限流；代理和网关模式见 [安全与网关指南](SECURITY_zh.md)。
- 使用 `/health` 做工作流 readiness check，使用 `/v1/models` 校验模型别名。
- 记录 request id、音频时长、模型别名、响应格式、设备、延迟和错误类型。
- 按最长音频时长设置工作流超时；超长录音建议先切分，再交给低代码工具处理。
- 私有音频放在可信存储中，避免把签名 URL、凭据或转写文本写入公开日志。
- 上生产前，至少用一个公开 smoke 样例和一个真实业务样例完整跑通同一条工作流。

## 故障排查

- **工作流能访问 `/health`，但转写失败:** 确认请求是 `multipart/form-data`，且二进制字段名是 `file`。
- **Dify 或 n8n 访问 `localhost` 失败:** 换成工作流运行时可访问的主机名、Compose service name 或 Kubernetes service name。
- **响应中没有可用 `segments`:** 检查格式和已部署 schema，再检查模型的 `sentence_info` 与说话人配置；仅设置 `verbose_json` 不能创建时间戳或标签。
- **请求超时:** 调大 HTTP timeout，或先切分长录音。
- **第一次请求很慢:** 使用 `--model sensevoice` 预加载模型，并用 `/health` 做 readiness check。
- **模型别名未知:** 调用 `/v1/models`，使用返回列表中的别名。
