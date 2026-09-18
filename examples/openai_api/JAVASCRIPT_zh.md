# FunASR OpenAI 兼容 API JavaScript/TypeScript 接入配方

这些 multipart HTTP 配方适用于 Node.js、TypeScript 服务和原生 Web API 转发函数。仓库示例 `server.py` 与打包 `funasr-server` 是不同实现，不能互换默认值，也不是完整 OpenAI API 兼容保证。

示例服务**没有内置鉴权或上传大小限制**。本地检查只使用 loopback。共享前按[安全指南](SECURITY_zh.md)配置 TLS、网关鉴权、上传/时限/速率限制、health/model/schema 私有访问和音频/转写保留策略。占位 API key 不提供鉴权。

## 预检查

先按[示例 README](README_zh.md#快速开始)准备 checkout 和 Python 环境。其中源码 revision 不是依赖或权重锁定，也不是全新安装成功声明。从该 checkout 根目录开始，假定 `.venv` 已准备好，启动一个本地示例服务：

```bash
cd examples/openai_api
source ../../.venv/bin/activate
python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000
```

如果服务已经运行，跳过启动。准备好 CUDA 依赖后，可将 CPU 命令替换为 `python server.py --host 127.0.0.1 --model sensevoice --device cuda --port 8000`，不要重复占用同一端口。另一条打包服务路线及默认值见 [Agent 集成指南](../../docs/agent_integration_zh.md)。

处理离线多人音频时，先按 [MOSS 部署指南](../../docs/moss_transcribe_diarize_zh.md)准备独立第三方服务，包括 GPU/文件时长边界与私有监听。然后为 JS 客户端设置 `FUNASR_MODEL=moss-transcribe-diarize` 并请求 `verbose_json`。MOSS 提供原生、录音内匿名标签，不是已验证身份；不要添加外部 VAD 或 `spk=true`。仅设置客户端别名不会完成环境准备。

在同一主机的第二个终端进入同一 checkout 的 `examples/openai_api` 目录，激活同一环境。等待模型加载后检查本地服务：

```bash
source ../../.venv/bin/activate
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/v1/models
curl -fsS http://127.0.0.1:8000/openapi.json
python smoke_test.py --base-url http://127.0.0.1:8000 --model sensevoice
```

这个可选 smoke 脚本会在缺少 `sample.wav` 时下载公开中文样例。它不是多语言准确率基准，health/schema 检查本身也不验证转写。Python 脚本读取 `MODEL`/`BASE_URL` 或显式参数，不读取 `FUNASR_MODEL`。检查 MOSS 时，也要修改脚本的 `--model` 并指向已准备好的 MOSS 服务。

SDK base URL 需要包含 `/v1`，直接健康检查不需要：

```text
OpenAI SDK baseURL: http://127.0.0.1:8000/v1
健康检查:            http://127.0.0.1:8000/health
转写接口:            http://127.0.0.1:8000/v1/audio/transcriptions
```

始终显式传入模型。检查已部署的 `/v1/models` 与 `/openapi.json`，例如 `paraformer-en` 是示例服务别名，不是打包服务内置别名。打包服务通过 `--model-path` 和 `--hub` 配置自定义 checkpoint 后，请求使用 `model="custom"`；任意 checkpoint ID 不是示例服务别名。`whisper-1` 是启动模型的兼容别名，不是 Whisper checkpoint。参见[客户端响应契约](CLIENTS.md#response-formats)：

- `verbose_json` 选择格式，不生成时间戳或开启说话人分离。示例只转换 `sentence_info`，否则为 `segments=[]`；打包服务可能提供基于文本的粗粒度区间。片段时间单位是秒，不是 SDK 毫秒。标签可缺失/为 null、字符串或数字，不是说话人身份或已验证对齐。
- 示例的 `duration` 是 `generate()` 耗时，不含初次加载，不是音频时长；`language` 是提交的提示或 `auto`，并含 `model`。打包 verbose 响应使用音频时长（元数据读取失败时可能为 0），可采用后端语言检测，含 `task`/片段 `id`/`words`，没有顶层 `model`。
- HTTP 展示文本会剥离 SenseVoice 富标签，没有独立情绪/事件字段。SDK 的 `timestamp`、`timestamps`、`ctc_timestamps`、`use_itn`、hotwords 和原始数组不是额外示例 HTTP 表单字段。`spk=true` 仅属于打包服务的非原生说话人流程，依赖相关环境，这些示例没有开启它。基础 Nano 不代表独立 MLT checkpoint 的语言覆盖。

## OpenAI JavaScript SDK

这些配方使用 Node.js 22，将独立 HTTP 客户端固定为 `openai@7.10.0`。此依赖选择不代表所有 Node/SDK/框架版本均兼容，也不代表已验证声学模型。请在自己的可写 Node 客户端项目目录安装 SDK，与 Python 服务 checkout 分开：

```bash
npm install openai@7.10.0
```

在该客户端目录创建 `transcribe.mjs`。运行时提供已有 WAV 文件 `meeting.wav`（或绝对路径）。`.mjs` 选择 ESM 并允许顶层 await；客户端不会创建或下载音频文件。

```javascript
import OpenAI, { toStreamingFile } from "openai";
import { open } from "node:fs/promises";
import { basename } from "node:path";
import { finished } from "node:stream/promises";

const audioPath = process.argv[2] ?? "sample.wav";

const client = new OpenAI({
  baseURL: process.env.FUNASR_OPENAI_BASE_URL ?? "http://127.0.0.1:8000/v1",
  apiKey: process.env.OPENAI_API_KEY ?? "local-development",
  timeout: 120_000,
  maxRetries: 0,
});

try {
  const handle = await open(audioPath, "r");
  try {
    const file = handle.createReadStream();
    // Observe stream errors even if the SDK rejects before consuming the file.
    const closed = finished(file).catch(() => {});
    try {
      const result = await client.audio.transcriptions.create({
        model: process.env.FUNASR_MODEL ?? "sensevoice",
        file: toStreamingFile(file, basename(audioPath)),
        response_format: "verbose_json",
      });

      console.log(result.text);
      for (const segment of result.segments ?? []) {
        console.log(`${segment.start}s-${segment.end}s`, segment.text);
      }
    } finally {
      file.destroy();
      await closed;
    }
  } finally {
    await handle.close();
  }
} catch {
  console.error("FunASR transcription failed");
  process.exitCode = 1;
}
```

运行：

```bash
node transcribe.mjs meeting.wav
```

即使本地 FunASR 不校验密钥，SDK 仍需要 API key 值。占位值仅用于未保护的本地端点；共享时通过服务端配置提供真实网关凭据。示例关闭 SDK 重试，避免重复执行昂贵请求。按允许的音频时长选择超时；不要把含转写内容的 CLI stdout 收集到公开日志。

两个 SDK 示例均先打开文件，再从同一个句柄构造上传流；即使 SDK 在读取前拒绝，也会关闭句柄。`toStreamingFile` 为惰性 multipart 编码保留 basename，无需把整个文件缓存在内存。`finished` 的拒绝处理器用于观察清理期间的流错误，不会把失败的 SDK 请求变成成功转写。

## 不依赖 SDK 的内置 fetch 写法

同一 Node.js 22 环境提供 `fetch`、`FormData` 和 `Blob`，此替代方案不需要 OpenAI SDK。在客户端目录保存为 `transcribe-fetch.mjs`。WAV 示例会将整个本地文件读入内存，用于共享 worker 前应先做大小/准入限制。不要手动设置 multipart `Content-Type` header，由 FormData 提供 boundary。

```javascript
import { readFile } from "node:fs/promises";
import { basename } from "node:path";

const baseUrl = (process.env.FUNASR_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");
const audioPath = process.argv[2] ?? "sample.wav";
const signal = AbortSignal.timeout(120_000);

try {
  const audio = await readFile(audioPath);
  const form = new FormData();
  form.append("file", new Blob([audio], { type: "audio/wav" }), basename(audioPath));
  form.append("model", process.env.FUNASR_MODEL ?? "sensevoice");
  form.append("response_format", "verbose_json");
  const headers = new Headers();
  if (process.env.FUNASR_API_KEY) {
    headers.set("Authorization", `Bearer ${process.env.FUNASR_API_KEY}`);
  }
  const response = await fetch(`${baseUrl}/v1/audio/transcriptions`, {
    method: "POST",
    headers,
    body: form,
    redirect: "error",
    signal,
  });
  if (!response.ok) {
    await response.body?.cancel();
    console.error(`FunASR HTTP error ${response.status}`);
    process.exitCode = 1;
  } else {
    const result = await response.json();
    if (!result || typeof result.text !== "string") throw new Error("Invalid response");
    console.log(result.text);
  }
} catch {
  console.error(signal.aborted ? "FunASR request timed out" : "FunASR request failed");
  process.exitCode = 1;
}
```

从客户端目录运行：

```bash
node transcribe-fetch.mjs meeting.wav
```

`FUNASR_BASE_URL` 不带 `/v1`，与 SDK 的 `FUNASR_OPENAI_BASE_URL` 不同。`FUNASR_API_KEY` 是可选网关 bearer 凭据，不是 FunASR 内置鉴权。固定 120 秒 fetch 信号持续作用到 `response.json()` 完成，但不是上传/下载字节限制。重定向会被拒绝，不跟随到其他主机。错误仅打印通用消息/状态，不打印原始上游响应体；这不是生产日志或重试策略。

## TypeScript helper

- 在已配置 TypeScript 且使用同一 OpenAI 依赖的项目中，将 helper 放入 `funasr-client.ts`。不要把 `.ts` 当作独立 `.mjs` 命令运行。
- 编译器依赖选择为 `typescript@5.9.3` 和 `@types/node@22.18.6`，配合 Node.js 22.13.1。按项目配置 Node 模块解析（`module`/`moduleResolution` 为 `NodeNext`）、ES2022 target 与 `ES2022`/`DOM` libraries。这些设置不认证 Next.js build 或部署。
- 这个由应用维护的小型字段子集不是运行时校验，末尾类型断言不会验证服务端 JSON，也不证明精确对齐。使用前要检查可选字段，包括缺失/为 null 的说话人标签。

```typescript
import OpenAI, { toStreamingFile } from "openai";
import { open } from "node:fs/promises";
import { basename } from "node:path";
import { finished } from "node:stream/promises";

export interface FunASRTranscript {
  text: string;
  segments?: Array<{ start: number; end: number; text: string; speaker?: string | number | null }>;
  language?: string;
  duration?: number;
  model?: string;
}

const client = new OpenAI({
  baseURL: process.env.FUNASR_OPENAI_BASE_URL ?? "http://127.0.0.1:8000/v1",
  apiKey: process.env.OPENAI_API_KEY ?? "local-development",
  timeout: 120_000,
  maxRetries: 0,
});

export async function transcribeWithFunASR(audioPath: string): Promise<FunASRTranscript> {
  const handle = await open(audioPath, "r");
  try {
    const file = handle.createReadStream();
    // Observe stream errors even if the SDK rejects before consuming the file.
    const closed = finished(file).catch(() => {});
    try {
      const result = await client.audio.transcriptions.create({
        model: process.env.FUNASR_MODEL ?? "sensevoice",
        file: toStreamingFile(file, basename(audioPath)),
        response_format: "verbose_json",
      });

      return result as FunASRTranscript;
    } finally {
      file.destroy();
      await closed;
    }
  } finally {
    await handle.close();
  }
}
```

建议在应用侧维护小而稳定的返回类型。调用方必须处理 rejection，不向用户暴露 SDK 错误详情。接口可不包含应用未使用的字段，但字段含义仍由实际部署端点决定。

## Next.js route handler

- **放置位置与范围：** 对于已有 Next.js App Router 应用，使用 `app/api/transcribe/route.ts`。函数使用原生 `Request`/`Response` 并声明 Node runtime；独立 TypeScript/Web API 检查不是 Next.js 项目 build 或部署认证。
- **缺失控制：** 鉴权、上传字节限制、限流与隐私/审计策略均**未实现**。应在 `request.formData()` 缓冲请求前通过入口限制上传，并在共享前保护路由。代理不是鉴权层，这里不包含 Next.js 安装或认证框架。
- **超时范围：** 120 秒上游超时不限制入站上传解析或 payload 大小。
- **固定配置：** 通过仅服务端可用的环境配置，把 `FUNASR_UPSTREAM_URL` 设为运维人员控制的转写端点，`FUNASR_MODEL` 设为对应别名。同主机默认值为 loopback，容器需明确配置可达的私有服务/网关。可选 `FUNASR_API_KEY` 提供 bearer 凭据。不要使用 `NEXT_PUBLIC_` 变量，也不要从上传表单接收 target/model/credential。

```typescript
export const runtime = "nodejs";

const UPSTREAM_URL = process.env.FUNASR_UPSTREAM_URL ?? "http://127.0.0.1:8000/v1/audio/transcriptions";
const UPSTREAM_MODEL = process.env.FUNASR_MODEL ?? "sensevoice";
const API_KEY = process.env.FUNASR_API_KEY;

export async function POST(request: Request) {
  let incoming: FormData;
  try {
    incoming = await request.formData();
  } catch {
    return Response.json({ error: "Invalid multipart upload" }, { status: 400 });
  }
  const file = incoming.get("file");

  if (!(file instanceof File)) {
    return Response.json({ error: "missing file" }, { status: 400 });
  }

  const upstream = new FormData();
  upstream.append("file", file, file.name || "audio.wav");
  upstream.append("model", UPSTREAM_MODEL);
  upstream.append("response_format", "verbose_json");
  const headers = new Headers();
  if (API_KEY) headers.set("Authorization", `Bearer ${API_KEY}`);
  const signal = AbortSignal.timeout(120_000);

  try {
    const response = await fetch(UPSTREAM_URL, {
      method: "POST",
      headers,
      body: upstream,
      redirect: "error",
      signal,
    });
    if (!response.ok) {
      await response.body?.cancel();
      const status = response.status >= 400 && response.status <= 599 ? response.status : 502;
      return Response.json({ error: "Upstream transcription failed" }, { status });
    }
    if (!(response.headers.get("content-type") ?? "").toLowerCase().includes("application/json")) {
      await response.body?.cancel();
      return Response.json({ error: "Invalid upstream response" }, { status: 502 });
    }
    const body = await response.json();
    if (!body || typeof body.text !== "string") {
      return Response.json({ error: "Invalid upstream response" }, { status: 502 });
    }
    return Response.json(body);
  } catch {
    return Response.json(
      { error: signal.aborted ? "Upstream timed out" : "Upstream request failed" },
      { status: signal.aborted ? 504 : 502 },
    );
  }
}
```

此 handler 对格式错误上传返回 400，拒绝重定向，超时覆盖 JSON 响应体读取。上游 400–599 错误保留状态但使用通用响应体；其他非预期状态/非 JSON 响应转为 502，超时为 504，有效转写 JSON 以 200 返回。不暴露上游 HTML/错误文本。它仍是转发 sketch，不是完整 schema 校验器、有界响应下载器或加固的生产服务。

## 生产检查清单

- 在 API 前增加 TLS、鉴权、上传大小限制和限流。
- 根据最大音频时长设置请求超时；长录音需要更长的 HTTP timeout。
- 只记录经批准的运行元数据，如模型别名、响应格式、延迟和错误类别。区分音频时长与处理耗时，不默认记录原始上游响应体、凭据、音频或转写。
- 接收用户上传前，先用 `GET /health` 和 `GET /v1/models` 做就绪检查。
- 浏览器应用应把音频上传处理留在服务端。
- 生产服务固定 `openai` 包版本，并在 SDK 升级后重新测试。

## 故障排查

- **SDK 提示缺少 API key:** 本地开发传入任意占位 `apiKey`。仅适用于未保护的本地端点，共享时应配置真实网关凭据。
- **SDK 调用返回 404:** SDK 使用 `baseURL=http://localhost:8000/v1`；直接端点调用使用 `http://localhost:8000`。上面的本地配方使用显式 loopback 地址 `127.0.0.1`。
- **`unknown model`:** 调用 `/v1/models`，使用返回的模型别名。同时检查实际运行的服务实现。
- **浏览器上传遇到 CORS 或鉴权错误:** 先上传到自己的后端，再由后端代理到 FunASR。应保护后端并核验真实网关凭据和网络路由，不要通过关闭防护解决问题。
- **请求超时:** 增加 SDK 或 fetch 超时，或切分超长音频。重新评估允许的音频时长并修改实际超时配置，不要只在文字中声称增加时限。
