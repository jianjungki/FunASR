# FunASR Agent 集成

[English](agent_integration.md)

按应用需要选择接口：HTTP 文件转写、本地 MCP 工具、桌面录音或本地字幕流水线。
这些路径的模型、选项和输出字段并不完全相同。直接在进程内推理请使用
[Python SDK](python_api_zh.md)。

## HTTP 服务

以下源码安装起点包含本页后续用到的示例脚本，命令使用 POSIX shell。
使用新目录和虚拟环境；仅安装
PyPI 包不会安装这些仓库示例。

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

这只固定源码，不会锁定所有依赖和模型权重。按照[安装指南](installation/installation_zh.md)
准备 CPU/GPU 环境，记录实际依赖版本和模型版本，再验证真实请求。
`pip check` 不能代替 CUDA、音频解码或全新环境安装测试。

在该环境中选择以下**一条**命令运行。CPU 示例显式选择 SenseVoice；CUDA 方案需要
可用的 GPU 环境。保持服务终端运行，在另一个已准备好的终端执行客户端命令。

```bash
funasr-server --host 127.0.0.1 --device cpu --model sensevoice --port 8000
# 备选：使用相同端口前先停止 CPU 服务。
funasr-server --host 127.0.0.1 --device cuda --model sensevoice --port 8000
```

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/models
```

上传文件使用 `/v1/audio/transcriptions`，运行中服务的 schema 位于 `/openapi.json`，
Swagger UI 位于 `/docs`。这个服务的 `/docs` 不是 FunASR 官网文档目录。
健康检查或模型列表返回成功，不能代替目标模型的真实转写验收。

打包的 `funasr-server` 与[示例 HTTP 服务](../examples/openai_api/README_zh.md#api-contract)
具有不同的默认值、别名和响应结构。启动和请求时都应显式指定 `model`。
`paraformer-en` 是示例服务的注册别名，不是打包服务内置别名。
SenseVoice 的 HTTP 展示文本已清除富标签，不是专用的情感或事件输出 API。
Nano 与 MLT-Nano 的语种和时间戳能力应按[模型选择指南](model_selection_zh.md)
及实际运行路径区分，不能从 HTTP 接口名称推断。打包服务的自定义模型应通过
`--model-path` 配合正确的 `--hub` 加载，并在请求中指定 `model=custom`；
任意模型 ID 不会自动成为内置 `--model` 别名。

[MOSS-Transcribe-Diarize](moss_transcribe_diarize_zh.md) 是 OpenMOSS 的第三方模型，
有独立部署要求。其原生匿名说话人标签不需要外接 VAD 或说话人模型，不要叠加这些阶段，
也不要假设所有客户端都能呈现其全部输出。

本地服务不会认证下方 SDK 的占位 key。对外提供网络访问前，按
[安全指南](../examples/openai_api/SECURITY_zh.md) 配置 TLS、鉴权、上传大小及速率限制。
CORS 不是身份认证。

## SDK 与 curl

在客户端环境单独安装 OpenAI HTTP 客户端：

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

`verbose_json` 只选择格式，不会开启说话人分离、恢复富标签或保证词级对齐。
示例服务把已有 `sentence_info` 转为 segments，没有时返回空列表；打包服务可能生成
粗粒度回退分段。二者的分段时间均为秒，但 `duration` 字段语义不同。
使用时间戳前请阅读[客户端输出契约](../examples/openai_api/CLIENTS.md#response-formats)。
`json` 和 `text` 是更简单的响应格式。`spk=true` 的说话人处理属于打包 API，
不属于示例服务的请求 schema；另见[说话人标签与身份边界](speaker_emotion_zh.md)。

## 工作流集成

HTTP 节点使用 `POST` 转写端点和 multipart 请求体：二进制文件字段为 `file`，
文本字段为 `model` 与 `response_format`。把音频 URL 写入 `file` 字段不等于上传音频字节。
当 Dify/n8n 运行在容器中时，`localhost` 指该容器而非 FunASR 主机，
应配置经过预期网关、工作流实际可达的服务地址。

- [Dify、n8n 与 webhook worker](../examples/openai_api/WORKFLOWS_zh.md) 提供请求连接示例。
- [JavaScript 和 TypeScript](../examples/openai_api/JAVASCRIPT_zh.md) 提供 SDK 和 multipart 客户端。
- [Postman](../examples/openai_api/POSTMAN_zh.md) 与[冒烟测试](../examples/openai_api/smoke_test.py) 检查已部署端点。
- [Gradio](../examples/openai_api/GRADIO_zh.md) 提供浏览器上传及麦克风示例。
- [OpenAPI](../examples/openai_api/OPENAPI_zh.md) 区分仓库内示例 schema 与已部署打包服务的 schema。

在宿主框架中按这些请求和输出边界注册转写工具。URL worker 示例不是完整的安全下载器；
接受不可信 URL 前，应补充目标白名单、私网阻断、重定向校验、大小限制和超时。
响应字段以上方客户端契约为准，不要假设工作流字段表适用于两种服务实现。
这些示例不代表所有框架版本均已完成
集成验证，也不代表任意不可信下载 URL 都是安全的。

## MCP 服务

在已准备好的仓库根目录和环境中运行：

```bash
python examples/mcp_server/funasr_mcp.py
```

执行转写前，应按安装指南准备 PyTorch 和兼容的音频特征后端。
安装工具包或完成 MCP 握手，都不等于模型执行已通过验证；此脚本不需要额外安装 MCP SDK。
MCP 客户端通过 stdio 启动此脚本，它不是 HTTP 监听服务。
配置时使用已准备好的 Python 环境与仓库绝对路径：

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

`transcribe_audio` 接受服务端可见、已存在的本地 `audio_path`，也可以是容器中
只读挂载的路径，不接受 URL 或实时流。首次调用可能下载并加载权重。
语种提示为 `auto`、`zh`、`yue`、`en`、`ja`、`ko`；设置 `FUNASR_MODEL` 不会改变
工具 schema，也不能保证另一模型兼容该工具的 VAD 路径。

结果被格式化为 MCP `content` 中的 `type=text`，可包含分段，而不是 HTTP 响应对象。
顶层转写文本会清除富标签；可选的分段文本来自模型输出。
`FUNASR_DEVICE` 默认为 `cpu`，`FUNASR_MODEL` 默认为 `iic/SenseVoiceSmall`。
[MCP 源码与容器说明](../examples/mcp_server/README.md) 提供客户端配置和文件挂载方法。
控制助手及服务端可访问的文件；本地工具本身不是文件系统权限隔离机制。

## 桌面语音输入

保持 HTTP 服务运行，在已准备好的仓库内打开另一个终端：

```bash
python -m pip install sounddevice numpy pyperclip openai pynput
python examples/voice_input/funasr_input.py --server http://localhost:8000/v1 --model sensevoice
```

脚本切换录音状态，将 WAV 上传至 HTTP 服务，再复制转写结果供粘贴。
需要麦克风权限和音频设备支持；macOS 还可能需要辅助功能权限，Linux 自动粘贴使用
`xdotool`，剪贴板及粘贴行为随桌面会话而异。当前 `--lang` 虽然被解析，却没有传入
转写请求，因此在此路径中不是有效的语种控制项。

远程 `--server` 会把录音发送给该端点，不能无条件宣称完全离线、音频不离开本机或
达到固定延迟。部署前请阅读[配置选项](../examples/voice_input/README.md#配置选项)
及[实现](../examples/voice_input/funasr_input.py)。

## 字幕生成

这是本地 `AutoModel` 流水线，不是 HTTP 或 MCP 客户端。
在已准备好的仓库中，使用本地输入文件及适合的推理环境：

```bash
python examples/subtitle/generate_subtitle.py video.mp4
python examples/subtitle/generate_subtitle.py meeting.wav --spk
python examples/subtitle/generate_subtitle.py podcast.mp3 --format vtt
python examples/subtitle/generate_subtitle.py audio.wav --device cpu
```

默认设备为 CUDA，最后一条命令显式选择 CPU。默认模型为 SenseVoiceSmall，并使用
VAD 和标点模型；这套固定流水线不是任意模型的通用配方。`--spk` 添加 CAM++ 匿名标签，
不验证真实身份。`--format` 选择 SRT/VTT，`--output` 指定输出路径，已有输出文件会被覆盖；
需要保留旧字幕时应指定新路径。`--lang` 将非 auto
语种提示传给推理。`--max-single-segment-time` 的单位是毫秒，当前默认 `60000`。

`--segment-mode readable` 对展示字幕分组，不改写识别文本或标点；`sentence` 保留
原始模型句段分组。两种模式都不修复标点错误，也不保证音素级边界。
应检查实际时间戳是否可用，并对照原音频回放；缺少时间信息时可能回退到零时长 `(0, 0)`
区间，这不是经过验证的字幕。输入解码、模型与依赖加载、GPU 容量
仍需针对环境验证。输出语义见[字幕选项](../examples/subtitle/README.md#options)
及[说话人指南](speaker_emotion_zh.md)。
