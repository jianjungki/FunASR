# FunASR OpenAI 兼容 API Kubernetes 部署

为集群内部的 Agent、Web 后端、工作流引擎或批处理 worker 部署语音接口。先使用 SenseVoice CPU 模板；下方独立的 MOSS GPU 配方提供转写与说话人分离。

**所有命令都从 FunASR 仓库根目录执行**，包括新开终端中的命令。需要 Docker、可推送的镜像仓库、已指向目标集群的 `kubectl`、在 `speech` 中创建资源的权限，以及供缓存 PVC 使用的默认 StorageClass。构建前替换示例镜像仓库地址。本地 smoke 客户端需要 Python 3.10 或更高版本，不需要第三方 Python 包。

**ClusterIP 不是鉴权。** 两套清单都没有提供 NetworkPolicy、鉴权网关、TLS 或请求限制。允许不可信客户端访问前，请阅读[服务安全指南](../SECURITY_zh.md)。以下配方使用本地 port-forward，不是公网入口。

模板默认比较保守：

- 默认使用 `ClusterIP`，不直接暴露公网 `LoadBalancer`。
- 默认 `FUNASR_DEVICE=cpu`，与便携 Dockerfile 匹配。
- 在 `/root/.cache` 挂载持久化缓存卷，避免 Pod 重启后重复下载模型。
- 使用 `/health` 做 startup、readiness 和 liveness probe。
- 挂载内存型 `/dev/shm`，便于 PyTorch 和音频预处理使用。

## 1. 构建并推送镜像

保持 shell 位于仓库根目录，CPU 镜像使用 API 目录作为构建上下文：

```bash
docker build -f examples/openai_api/Dockerfile -t registry.example.com/speech/funasr-api:cpu-latest examples/openai_api
docker push registry.example.com/speech/funasr-api:cpu-latest
```

将 `examples/openai_api/kubernetes/kustomization.yaml` 的 `images` 配置改为已推送的镜像。需要可复现部署时，把示例可变 tag 换成镜像仓库的不可变 digest。每次 rollout 前记录镜像 digest 与清单，方便恢复。CPU Dockerfile 复制 example `server.py`，但从 PyPI 安装 FunASR，不安装当前 checkout 的 FunASR 包；依赖环境也未锁定。

## 2. 部署

```bash
kubectl create namespace speech --dry-run=client -o yaml | kubectl apply -f -
kubectl -n speech apply -k examples/openai_api/kubernetes
kubectl -n speech rollout status deploy/funasr-api --timeout=15m
```

CPU 服务在启动 HTTP 前预加载配置的模型，下载和首次加载可能需要几分钟。startup probe 的失败预算约为 10 分钟（周期 `10s`、失败阈值 `60`），不包括拉取镜像、调度或 PVC 绑定时间。`/health` 成功不代表推理验收：接入流量前，还要完成下面的音频请求。

## 3. Smoke test

建议先保持服务内网私有，通过 `port-forward` 验证：

```bash
kubectl -n speech port-forward --address 127.0.0.1 svc/funasr-api 8000:8000
```

保持 port-forward 运行。在另一个终端的同一仓库根目录执行：

```bash
python3 examples/openai_api/smoke_test.py --base-url http://127.0.0.1:8000 --model sensevoice --response-format verbose_json
```

集群内客户端可以使用 `http://funasr-api.speech.svc.cluster.local:8000` 作为直接 HTTP base URL，使用 `http://funasr-api.speech.svc.cluster.local:8000/v1` 作为 OpenAI SDK base URL。

smoke 客户端仅在当前目录不存在 `sample.wav` 时下载公开中文样本，已有文件会被复用。它打印 health、模型 metadata 和完整转写 JSON；请自行核对文本与时间戳，退出码为零并不验证识别准确率、说话人标签、内存容量或并发能力。避免保留敏感音频或未脱敏输出。客户端不发送 Authorization；安全指南的仅转写网关会主动拒绝 metadata 路由，因此这套 smoke 应通过本地 port-forward 运行，不要直接指向该网关。

## 4. 根据集群调整配置

| 配置 | 默认值 | 什么时候调整 |
|---|---|---|
| `FUNASR_MODEL` | `sensevoice` | 先检查目标模型的依赖与硬件要求；`/v1/models` 列出别名，不证明每个模型都已就绪。 |
| `FUNASR_DEVICE` | `cpu` | 只有在镜像已适配 CUDA 且集群 GPU 调度已配置后才改成 `cuda`。 |
| PVC 大小 | `20Gi` | 缓存多个模型或较大模型版本时增大。 |
| 内存 request | `8Gi` | 根据启动过程和真实音频负载观测结果调整。 |
| Startup probe | 约 10 分钟 | 按模型初始化情况调整；镜像拉取、调度和 PVC 绑定需分别排查。 |

### MOSS GPU 替代方案

MOSS-Transcribe-Diarize 是 OpenMOSS-Team 的模型，由 FunASR 集成。这套清单运行 packaged FunASR HTTP 适配器，使用 `verbose_json`，不是原生 vLLM 或其 `diarized_json` 接口。分离标签不是经过验证的说话人身份。模型要求、输出、不依赖外部 VAD 的行为和其他服务后端，见 [MOSS 部署指南](../../../docs/moss_transcribe_diarize_zh.md)。

`kustomization.yaml` 不包含 MOSS 清单。MOSS 模板请求一张 NVIDIA GPU、24Gi 内存、40Gi 缓存 PVC，并配置 8Gi 内存型 `/dev/shm`；这些是模板设置，不是实测容量保证。先配置集群的 GPU device plugin 和调度。与 CPU 镜像不同，`Dockerfile.moss` 复制并安装整个 checkout，因此构建上下文必须是仓库根目录；请使用干净的 checkout，不要把凭据或私有数据放入构建上下文。

```bash
docker build -f examples/openai_api/Dockerfile.moss -t registry.example.com/speech/funasr-api:moss-local .
docker push registry.example.com/speech/funasr-api:moss-local
```

应用前，将 `examples/openai_api/kubernetes/funasr-moss-api.yaml` 中的 `funasr-moss-api:local` 替换成已推送镜像的不可变 digest。如果跳过了 CPU 部署，先按第 2 步创建 `speech` namespace。保存镜像 digest 和修改后的清单作为回滚记录。

```bash
kubectl -n speech apply -f examples/openai_api/kubernetes/funasr-moss-api.yaml
kubectl -n speech rollout status deploy/funasr-moss-api --timeout=15m
kubectl -n speech port-forward --address 127.0.0.1 svc/funasr-moss-api 8001:8000
```

在另一个终端的仓库根目录中使用本地端口 8001，与 CPU 示例端口区分：

```bash
python3 examples/openai_api/smoke_test.py --base-url http://127.0.0.1:8001 --model moss-transcribe-diarize --response-format verbose_json
```

MOSS 模板有 startup 和 readiness probe，没有 liveness probe；其 `/health` 不测试转写。请对照音频检查返回的文本与分离结果；这套配方不认证具体 GPU、实时性能或生产负载。

## GPU 说明

普通 Dockerfile 默认面向 CPU，单独设置 `FUNASR_DEVICE=cuda` 不会使它成为受支持的 GPU 镜像。其他 GPU 模型需要适配依赖与调度。下面只是字段示意：`resources` 属于 container，`nodeSelector` 属于 Pod spec，不是可以整体粘贴的同层完整清单：

```yaml
resources:
  limits:
    nvidia.com/gpu: "1"
nodeSelector:
  nvidia.com/gpu.present: "true"
```

不同 Kubernetes 发行版的 GPU label、runtime class 和 device plugin 配置并不相同。服务对外开放前，请先补齐鉴权、TLS、上传大小限制和限流。

## 运维检查

- 修改探针预算前，先检查 PVC 绑定、镜像拉取、Pod events 和模型加载日志，再检查 `/health`、`/v1/models` 和真实音频响应。
- 记录模型别名、设备、音频时长、响应格式、延迟和错误文本。
- 由于缓存 PVC 是 `ReadWriteOnce`，建议先从 1 个副本开始；横向扩容前先评估镜像、每 Pod 缓存或共享只读模型缓存方案。
- 为预期客户端实施鉴权和 NetworkPolicy；namespace 本身不是网络隔离边界。
- Dify、n8n 或 Web 后端在同一集群内访问时，应使用 Kubernetes service name，不要使用 `localhost`。
