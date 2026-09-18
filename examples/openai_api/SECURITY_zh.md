# FunASR OpenAI 兼容 API 安全与网关指南

当你准备把 OpenAI 兼容 API 提供给团队、工作流引擎、浏览器 UI 或笔记本之外的服务时，请先看这份指南。示例 `server.py` 和打包命令 `funasr-server` 均未实现网关鉴权或应用级上传总大小限制。它们默认监听 `0.0.0.0`；在前面加代理不会改变后端监听。可直连的后端端口可能绕过网关。这是需要验证的部署边界，不是声称某个实际运行的服务已经暴露。

## 推荐拓扑

```text
OpenAI SDK / Dify / n8n / 浏览器 UI
        |
        v
TLS + 鉴权 + 上传限制 + 日志
(反向代理、API 网关、Ingress 或 Service Mesh)
        |
        v
FunASR OpenAI 兼容 API
(私有主机、虚机、容器或 Kubernetes ClusterIP)
```

只要条件允许，就让 FunASR 保持在私有网络中。公网 TLS、身份认证、请求限制和审计日志应放在团队已有的边界组件上。

代理与后端位于同一主机时，先按 [README 准备源码 checkout 和隔离 Python 环境](README_zh.md#快速开始)。以下命令假定已完成安装，从该 checkout 根目录启动一个 loopback 示例服务：

```bash
cd examples/openai_api
source ../../.venv/bin/activate
python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000
```

- 同主机部署打包命令也需要显式 `--host 127.0.0.1`。不要让两个服务同时占用 8000 端口。启动模型、设备选择和安装要求仍以所链接的 README 为准。
- 容器内部可能需要监听 `0.0.0.0` 才能被访问，但这不同于宿主机端口发布：现有 Compose 默认在所有宿主机接口发布 8000。同主机场景可使用 `FUNASR_HOST_PORT=127.0.0.1:8000 docker compose up --build`，或在自己的 Docker 命令中显式发布 `127.0.0.1:8000:8000`。应从 `examples/openai_api` 目录运行 Compose，作为替代启动方式，不要与已占用 8000 的宿主机服务并用。本指南不修改部署 manifest。
- 代理位于另一容器或主机时，其 `127.0.0.1` 并不是后端。应配置私有服务地址和仅允许代理、不允许不可信客户端的网络/防火墙规则。`ClusterIP` 不是鉴权或 namespace 隔离；需要实际生效的 `NetworkPolicy`，并验证真实网络路径。
- 从不可信客户端测试无法直连后端。443 端口上的 TLS 和鉴权不能保护另一个可直连的 8000 端口。CORS 是浏览器策略，不是鉴权或网络访问边界。

## 对团队开放前的最低控制项

| 控制项 | 为什么重要 | 建议在哪里实现 |
|---|---|---|
| TLS | 音频通常包含隐私信息。 | 反向代理、API 网关或 Ingress。 |
| 鉴权 | FunASR 不校验本地 SDK `api_key` 占位符。 | 选择相互匹配的 Basic、Bearer、OAuth/OIDC 或内部 SSO 网关与客户端。 |
| 上传大小限制 | 避免误传超大文件导致内存和磁盘压力。 | 网关 request body limit 和应用侧检查。 |
| 超时 | 长音频需要更长 HTTP timeout，但异常客户端不能无限挂住。 | 客户端、代理和服务进程管理器。 |
| 限流 | 防止突发请求打满 GPU/CPU。 | 网关、Ingress controller 或队列 worker。 |
| 私有运维路由 | `/health`、`/v1/models` 和 schema/UI 暴露服务元数据。 | 在共享监听入口拒绝，另行设计私有监控访问。 |
| 日志与留存 | 请求元数据有价值，但原始音频可能敏感。 | 集中日志策略和存储生命周期。 |

以下示例只允许精确的 `POST /v1/audio/transcriptions`。其他方法或路径均拒绝，包括 `/health`、`/v1/models`、`/openapi.json`、`/docs`、`/redoc` 和打包服务的 `/asr` 端点。末尾增加斜杠不属于允许路径。不要为了让 SDK 或监控探针通过，就增加通配转发到上游的规则。

这些示例**未实现**速率/并发限制、模型准入、队列预算和上游响应脱敏。预加载一个模型不代表示例 handler 只接受该 alias：请求可能加载另一个已配置模型。共享 CPU/GPU 必须单独设置准入策略。两个 handler 都会把上传内容读入内存，示例服务还会写临时音频文件。压缩文件的上传字节数不等于解码后的时长或内存占用。

## NGINX 反向代理示例

这是面向 NGINX 1.24 的 Basic auth 起点，不是完整生产策略。先在下面的明确路径放置证书链与私钥。使用运维管理的 `htpasswd` 工具，通过交互式密码提示创建 `/etc/nginx/funasr.htpasswd`，并按服务需要限制文件权限。仅首次创建文件时使用 `htpasswd -c /etc/nginx/funasr.htpasswd team_user`；更新时去掉 `-c`，避免覆盖其他用户。不要把明文密码写入配置或命令参数。缺少凭据、密码文件不可读或缺失时，都不得放行。

`200m` 和 `600s` 是容量评估示例值，不是普遍安全的上限或完整请求截止时间。尤其不能把代理 timeout 当作取消已启动模型计算的承诺。启动监听前，请用实际安装的 NGINX 版本验证配置。

```nginx
server {
    listen 443 ssl http2;
    server_name funasr.example.com;
    ssl_certificate /etc/nginx/tls/fullchain.pem;
    ssl_certificate_key /etc/nginx/tls/privkey.pem;

    client_max_body_size 200m;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;

    location = /v1/audio/transcriptions {
        limit_except POST {
            deny all;
        }
        auth_basic "FunASR gateway";
        auth_basic_user_file /etc/nginx/funasr.htpasswd;
        proxy_request_buffering on;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Authorization "";
    }

    location / {
        return 404;
    }
}
```

## Caddy 反向代理示例

此示例面向 Caddy 2.11 的 `basic_auth` 指令。使用 `caddy hash-password` 交互式生成密码 hash，通过服务环境变量 `FUNASR_BASIC_PASSWORD_HASH` 提供，不使用明文或提交到仓库的 secret。先准备以下 TLS 文件并限制权限。启动前，在相同环境下执行 `caddy adapt` 和 `caddy validate`；hash 缺失或无效不得导致回退为无鉴权转发。

显式 `route` 保证鉴权位于 `request_body` 和 `reverse_proxy` 之前。`200MiB` 用于与 NGINX `200m` 二进制单位示例对齐，须用选定的 Caddy 版本验证。body 限额可能在流式转发过程中执行，因此最终返回 413 **不能**证明上游收到零字节。请在实际代理上测试该边界，不要在没有证据时宣称已完整缓存或在完整上传准入后才转发。这些静态证书配方不代表已验证公网 DNS 或自动 ACME 签发。

```caddyfile
funasr.example.com {
    tls /etc/caddy/tls/fullchain.pem /etc/caddy/tls/privkey.pem

    @transcribe {
        path /v1/audio/transcriptions
        method POST
    }

    handle @transcribe {
        route {
            basic_auth {
                team_user {$FUNASR_BASIC_PASSWORD_HASH}
            }
            request_body {
                max_size 200MiB
            }
            reverse_proxy 127.0.0.1:8000 {
                header_up -Authorization
                transport http {
                    read_timeout 600s
                    write_timeout 600s
                }
            }
        }
    }

    handle {
        respond "Not found" 404
    }
}
```

两个示例均在转发前移除 `Authorization`：FunASR 不需要网关的 Basic 凭据。不要把透传身份头当作完成鉴权。生产团队优先使用已有 SSO/OIDC 网关，而不是共享密码，并明确匹配的客户端配置与路由策略。

## Kubernetes 注意事项

Kubernetes 模板使用 `ClusterIP`，而非公开 `LoadBalancer`。这本身不能阻止其他 pod 或可达主机调用服务。在增加 Ingress 或 LoadBalancer 前，请先完成：

- 使用 Ingress controller 或 API 网关强制 TLS、鉴权、上传大小限制和限流。
- 模型缓存卷只暴露给拥有该服务的 namespace 或 node pool。
- 使用 `NetworkPolicy` 限制可调用服务的 namespace。
- 第一次验证先用 `kubectl port-forward` 加 `smoke_test.py`，再开放路由。
- 如果增加 GPU，固定调度规则，并在部署说明中记录镜像 tag、CUDA runtime 和模型 alias。

## 客户端配置

**上面的 Basic 网关：**使用支持 Basic 的客户端。以下命令交互式提示输入 `team_user` 的密码，上传已有本地文件；不会把密码放入命令行，也不跟随重定向或关闭证书校验。从包含 `meeting.wav` 的目录运行，并将域名替换为已配置 TLS 的网关。命令只输出 HTTP 状态，不输出转写内容或上游错误正文；应核对预期状态，而不是把所有 curl 退出码都当作推理成功。

```bash
curl --user team_user --fail --show-error --silent \
  --max-time 600 --output /dev/null --write-out 'HTTP %{http_code}\n' \
  -F 'file=@meeting.wav' -F 'model=sensevoice' \
  -F 'response_format=verbose_json' \
  https://funasr.example.com/v1/audio/transcriptions
```

**仅适用于 Bearer 网关：**OpenAI SDK 通常要求传入 API key 字符串，即使本地 FunASR 不检查它。以下客户端初始化假设另有接受 `Authorization: Bearer` token 的网关。Basic 密码或密码 hash 不是 Bearer token；此 SDK 配置不能通过上面的 Basic 示例认证。OIDC 浏览器 session、mTLS 证书或任意 SSO 凭据也不会自动成为 SDK key。请匹配实际网关/客户端认证方式，而不是修改 FunASR 的占位 key。在客户端环境通过 `python -m pip install openai` 安装独立客户端依赖。

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="https://funasr.example.com/v1",
    api_key=os.environ["FUNASR_API_KEY"],
    timeout=600.0,
    max_retries=0,
)
```

内部 HTTP worker 应从环境变量或密钥系统读取 token。不要把 token 提交到工作流定义、notebook、截图或 Postman 导出文件里。

## 数据处理清单

- 先决定原始音频是否允许存储、保存多久、谁可以访问。
- 日志建议记录 request ID、音频时长、模型 alias、状态、延迟和错误类型；除非策略允许，不要记录原始转写文本。
- 如果转写文本可能包含个人信息，请在接入用户前写清留存和删除规则。
- 写 benchmark 报告时，把公开样例和客户/员工私有音频分开。
- 打开 GitHub issue 前，先脱敏 header、token、文件名和说话人姓名。
- 示例会把临时音频写入磁盘，并在正常处理结束后 unlink。这不代表无落盘或安全擦除保证；需明确处理崩溃残留、代理缓冲、磁盘权限和存储留存。
- 示例会记录异常文本，并把它作为 HTTP error detail 返回。两份代理示例均不会自动脱敏上游响应或应用日志。应规定哪些人可以查看，并在分享前脱敏；删除音频文件不会删除其转写和日志。

## 上线检查清单

以下是需要在实际部署执行的验收检查，不是声称你的网关或公开服务已经通过：

1. **本地诊断：**在同一已准备好的 checkout/环境中，使用无鉴权本地 loopback 端点执行 `python smoke_test.py meeting.wav --base-url http://127.0.0.1:8000 --model sensevoice`。仓库自带 Python/Bash smoke 工具不发送网关凭据。音频路径不存在时可能下载公开中文样例；输出包含转写内容，Python 工具还会输出上游错误详情。诊断应保持私有，不要收集到共享自动化日志。
2. **认证上传：**通过已配置的 TLS 网关，正确 Basic 凭据和允许的小文件应仅到达指定转写路由并返回预期结果。在受控上游验证文件名、字节、模型以及不存在网关 `Authorization` 头，不记录真实凭据/音频。
3. **未认证请求：**允许的小型 POST 缺少或使用错误凭据时，必须返回 401 且不触发推理。这不规定同时超限或格式错误的请求应优先返回哪个错误。NGINX 凭据文件缺失/不可读、Caddy hash 缺失/无效均须失败关闭，不得回退到无鉴权代理。
4. **其他路由/方法：**`/health`、`/v1/models`、`/openapi.json`、`/docs`、`/redoc`、`/asr`、末尾带斜杠的变体和无关路径必须保持拒绝（这些兜底 handler 返回 404）。精确推理路径上的非 POST 也被拒绝；NGINX 可能返回 403，Caddy 使用兜底 404。不要为了让本地 smoke 脚本穿过公网网关而开放元数据路由；私有监控需要单独的策略。
5. **大小/容量：**检查小文件、允许的大文件与超限请求（预期 413）。单独观察上游影响；特别是流式限制时，413 本身不代表上游零字节。评估解码后时长、并发和模型准入，不把 200m/200MiB 当作容量保证。
6. **超时：**测试慢上传、慢上游和长推理。客户端/代理超时不代表已经取消模型计算，这些示例未实现完整推理调度/截止时间策略。
7. **绕过与记录：**从不可信网络确认后端不可直连。记录实际模型 alias、设备、镜像/FunASR/代理版本、证书准备过程和网关策略。不要由小型受控 HTTP fixture 推断全新环境安装、声学准确率或生产就绪。

相关文档：[OpenAI API README](README_zh.md)、[客户端配方](CLIENTS.md)、[工作流配方](WORKFLOWS_zh.md)、[Gradio 浏览器 Demo](GRADIO_zh.md)、[Kubernetes 模板](kubernetes/README_zh.md) 和仓库 [安全策略](../../SECURITY.md)。
