# FunASR OpenAI 兼容 API Gradio 浏览器 Demo

这个可选浏览器 UI 用于向已准备好的 FunASR、原生 vLLM 或原生 SGLang Omni 转写服务上传文件或录制音频。Gradio app 是 HTTP 客户端，不加载模型，也不安装服务端的声学依赖。录音完成后按完整文件提交；这不是流式识别或实时唤醒服务。

两个服务都应保持私有。此 demo 不是鉴权网关：没有配置 UI 鉴权，也不向后端发送 `Authorization` 凭据。API base URL 可以编辑，请求由 **Gradio 进程**发起，而不是浏览器直接发起。不要把这个操作界面分享给不可信用户。首次启动前请阅读[安全与网关指南](SECURITY_zh.md)；其中的 Basic 网关不能直接接收此客户端的无鉴权请求。

## 1. 启动 API 服务

使用仓库的 example API 时，先按 [HTTP 服务指南](README_zh.md#快速开始)准备同一份 checkout。在已安装 Python 3.11 的 POSIX shell 中执行：

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

这里只固定源码，不固定依赖、模型权重、解码器或 CUDA。这是安装配方，不是全新安装或声学验证结果。模型加载完成后再检查服务。准备好 GPU 依赖后，可改用 HTTP 指南中的 CUDA 替代命令，不要在 8000 端口再启动第二个服务。

MOSS 需要按 [MOSS 部署指南](../../docs/moss_transcribe_diarize_zh.md)准备专用环境以及固定的服务端和模型 revision。先选择其中的 FunASR 服务、原生 vLLM 或原生 SGLang Omni 路径；UI profile 不会启动、转换或重新配置后端。MOSS 联合完成离线转写和说话人分离，无需外部 VAD 或说话人模型。不要把其 GPU 环境安装到下文的轻量 Gradio 环境中。

Docker 和 Kubernetes 是后端的替代部署方式。容器 8000 端口只发布到主机 loopback，或使用私有 `kubectl port-forward`；容器内部监听 `0.0.0.0` 与主机端口暴露是不同边界。`ClusterIP` 本身不是网络隔离。只有 Gradio 进程能解析并访问集群 DNS 时才能使用该地址。在笔记本上应使用本地转发地址，而不是无法解析的 `*.svc.cluster.local` URL。参见 [Docker 部署](README_zh.md#docker-部署)和 [Kubernetes 部署](kubernetes/README_zh.md)。

## 2. 安装并启动浏览器 UI

打开**新终端**，从包含 `FunASR-api` 的目录开始。使用独立的 Python 3.12 环境 `.venv-gradio`，不要使用服务端 `.venv` 或原生后端环境。客户端配方选择 Gradio 6.26.0；仅固定版本不代表已成功安装，也不代表兼容所有后端发布版。

```bash
cd FunASR-api
python3.12 -m venv .venv-gradio
source .venv-gradio/bin/activate
python -m pip install "gradio==6.26.0"
python -m pip check
cd examples/openai_api
python gradio_app.py --backend funasr --model sensevoice --base-url http://127.0.0.1:8000 --host 127.0.0.1 --port 7860
```

Gradio 客户端本身不需要 FunASR、Torch、CUDA 或下载模型。独立运行的后端仍需要准备自己的依赖和模型。以后打开客户端终端时，先在 checkout 根目录激活 `.venv-gradio`，再进入 `examples/openai_api` 运行下列命令。

打开命令行输出的本地 URL，只在需要时允许麦克风访问，上传或录制音频，选择 **Model alias** 和 **Response format**，再点击 **Transcribe**。CLI 默认 backend 为 `funasr`，model 为 `sensevoice`，格式为 `verbose_json`。UI 使用 7860 端口，与后端端口分开。浏览器麦克风依赖权限和安全上下文；远程普通 HTTP UI 不是可通用的麦克风配方。

以下启动方式是**替代选项**，都在同一已激活的客户端环境和目录中执行。复用 7860 端口前先停止旧 UI，并另行启动匹配的后端。`--backend` 显式选择客户端 profile，不会探测或切换运行中的服务。服务 base URL **不带 `/v1`**，这与 OpenAI SDK 的 base URL 不同。客户端会追加 `/v1/audio/transcriptions`。

连接已为 MOSS 准备好的 FunASR example 或 packaged 服务：

```bash
python gradio_app.py --backend funasr --model moss-transcribe-diarize --base-url http://127.0.0.1:8000 --host 127.0.0.1 --port 7860
```

连接固定 revision 的原生 vLLM 配方，后端使用 `--served-model-name moss-transcribe-diarize`：

```bash
python gradio_app.py --backend vllm --model moss-transcribe-diarize --base-url http://127.0.0.1:8898 --host 127.0.0.1 --port 7860
```

连接使用完整模型 ID 的原生 SGLang Omni 配方时，下拉框显示较短的标签 `MOSS-Transcribe-Diarize`，请求仍发送完整 ID：

```bash
python gradio_app.py --backend sglang-omni --model OpenMOSS-Team/MOSS-Transcribe-Diarize --base-url http://127.0.0.1:8898 --host 127.0.0.1 --port 7860
```

显式 `--model` 是操作人员配置的覆盖值，会加入选项并作为请求的 `model` 原样发送，不会注册服务端 alias 或更换 checkpoint。例如，只有先把 vLLM 服务配置为接受 served name `meeting-asr` 后，才使用：

```bash
python gradio_app.py --backend vllm --model meeting-asr --base-url http://127.0.0.1:8898 --host 127.0.0.1 --port 7860
```

不要用完整 Hugging Face ID 替换 FunASR 请求 alias。example API 校验其五个 alias；packaged 服务的 `--model-path`/`--hub` 部署使用请求模型 `custom`。UI 的覆盖值不会绕过任何一类服务的模型校验。发送音频前检查当前 profile、model 和格式。

## 3. 先验证后端服务

**Check service** 请求 `/health` 和 `/v1/models`。这是 metadata 检查，不是声学测试，也不代表模型就绪。不同服务的 schema 和路由策略不同：原生服务或网关可能拒绝某个 metadata 路由，但允许转写。不要为了让按钮成功而公开私有 metadata 或移除鉴权。

对于无鉴权、仅监听 loopback 的 FunASR example 服务，在已激活的客户端环境及 `examples/openai_api` 目录中执行：

```bash
curl --fail --silent --show-error http://127.0.0.1:8000/health
curl --fail --silent --show-error http://127.0.0.1:8000/v1/models
python smoke_test.py --base-url http://127.0.0.1:8000 --model sensevoice
```

前两条命令只检查 metadata。可选的 `smoke_test.py` 命令不同：若默认的 `sample.wav` 不存在，它会下载公开中文样本，写入当前目录，执行转写并打印结果。它不是多语言准确率 benchmark，也不是仅检查 metadata。请使用受控音频并保护诊断输出。smoke 脚本的模型也必须与已准备的服务匹配；这条命令不验证 MOSS/native 部署。

UI timeout 默认为 300 秒，并传给 HTTP 客户端。它不是整个任务的截止时间；客户端超时不会取消后端推理，也不能确定安全并发上限。

## 模型别名

`funasr` profile 提供下列五个请求 alias。列出 alias 不代表 checkpoint 已加载、已缓存或被当前安装的依赖支持；选择其他模型可能触发 example API 按需加载。

- `sensevoice`：通过 FunASR 进行 SenseVoice 转写。HTTP text 已移除语言、情绪和事件标签；UI 的原始响应不是 SDK 的原始标签输出。
- `paraformer`：通过已配置的 FunASR pipeline 进行中文转写，不保证吞吐或生产容量。
- `paraformer-en`：通过已配置的 FunASR pipeline 进行英文转写。
- `fun-asr-nano`：基础 Fun-ASR-Nano 模型，不是独立的 31 语言 Fun-ASR-MLT-Nano checkpoint，不应假定支持韩语。在 example `server.py` 中选择此 alias 不会启动原生 vLLM。
- `moss-transcribe-diarize`：第三方 OpenMOSS，在专用环境中联合完成离线转写和说话人分离。录音内的匿名说话人标签不是身份认定；它不是实时麦克风模型。使用 `verbose_json` 检查 FunASR 服务的 segments。

不同 backend profile 有意采用不同默认值和格式：

**funasr** 默认 `sensevoice` 和 `verbose_json`，也可选 `json`。example API 的 `json` 包含 `text`；其 `verbose_json` 将 `sentence_info` 映射为 `segments`，`start`/`end` 单位为秒，`speaker` 取决于模型。segments 可以为空；请求 verbose 输出不会创建说话人分离能力。example 的 `duration` 是推理耗时，packaged FunASR 则报告音频时长。参见 [API 边界](README_zh.md#api-contract)。

**vllm** 默认 `moss-transcribe-diarize` 和 `diarized_json`，也可选 `json`。在固定 revision 的 MOSS 部署路径中，`diarized_json` 包含结构化说话人片段；`json` 保留紧凑标签文本。这不是对任意 vLLM 模型或发布版的承诺。不要向 FunASR profile 发送 `diarized_json` 并期待同样的结果。

**sglang-omni** 默认 `OpenMOSS-Team/MOSS-Transcribe-Diarize`，仅提供 `verbose_json`。在文档记录的原生契约中，`[Sxx]` 保留于 `segments[].text`，不是独立的 `speaker` 字段。Gradio 客户端展示返回的 `text` 和 JSON，不剥离标签、不生成说话人标签，也不归一化这些后端差异。协议、版本限制和长音频控制参见固定 revision 的 [MOSS 部署指南](../../docs/moss_transcribe_diarize_zh.md)；此 UI 没有暴露后端特定的 token 预算参数。

更完整的对比见[模型选择指南](../../docs/model_selection_zh.md)。

## 生产注意事项

- 把它当作私有操作 demo，而不是公网生产前端。敏感音频不要启用 `--share`。UI 监听 loopback 不会让另行暴露的后端变成私有服务。
- 可编辑 API URL 控制服务端请求。应用没有目标 allowlist 或重定向限制，HTTP 客户端可以跟随重定向。应限制 UI 使用者和 Gradio 进程的网络访问范围，不要把密码或访问 token 放进 URL。
- demo 没有配置 Basic、Bearer、OIDC 或 mTLS 后端凭据。TLS、鉴权、上传及响应大小限制、限流、并发准入和网络隔离都需要另行设计部署。OpenAI SDK 的 `api_key` 示例不会为此 Gradio 客户端增加鉴权。
- 音频从浏览器传到 Gradio，再传到 API。Gradio 使用文件路径输入，multipart builder 会将整文件读入内存，example API 也会缓冲并写入临时文件。不能承诺无落盘、立即删除或安全地无限上传。需核验所选 Gradio 版本的缓存和保留行为，准备私有临时存储、请求大小和时长限制。
- UI 显示服务端响应，也可能显示上游错误正文、URL 或异常详情。分享诊断信息前先脱敏，不要默认记录原始错误文本、音频或转写正文。为两类服务制定访问、保留和删除规则。
- 用受控文件和真实网关策略验证准确的客户端及后端 revision。成功显示 JSON 不能证明说话人分离准确率、身份识别、吞吐、取消能力、公网隔离或兼容所有原生服务版本。
