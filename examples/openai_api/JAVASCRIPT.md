# JavaScript and TypeScript Recipes for the FunASR OpenAI-Compatible API

Use these multipart HTTP recipes for Node.js, TypeScript services and a native Web API forwarding function. The repository's example `server.py` and packaged `funasr-server` are different implementations, not interchangeable defaults or full OpenAI API compatibility guarantees.

The example has **no built-in authentication or upload limit**. Keep local checks on loopback. Before sharing, configure TLS, gateway authentication, upload/time/rate limits, private health/model/schema access and audio/transcript retention using the [security guide](SECURITY.md). A placeholder API key is not authentication.

## Preflight

Prepare the checkout and Python environment using the [example README](README.md#quick-start). Its source revision is not a lock for dependencies or weights, nor a clean-install claim. From that checkout's root, with `.venv` already prepared, start one local example server:

```bash
cd examples/openai_api
source ../../.venv/bin/activate
python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000
```

If already running, skip startup. After preparing CUDA dependencies, replace the CPU command with `python server.py --host 127.0.0.1 --model sensevoice --device cuda --port 8000`; do not occupy the same port twice. The separate packaged route and its defaults are covered by [Agent integration](../../docs/agent_integration.md).

For offline multi-speaker files, first prepare the isolated third-party service in the [MOSS deployment guide](../../docs/moss_transcribe_diarize.md), including its GPU/file-duration limits and private binding. Then set `FUNASR_MODEL=moss-transcribe-diarize` for the JS clients and request `verbose_json`. MOSS provides native anonymous recording-local labels, not verified identities; do not add external VAD or `spk=true`. A client alias alone does not prepare that environment.

In a second terminal on the same host, enter the same checkout's `examples/openai_api` directory and activate the same environment. Wait for model loading before checking the local service:

```bash
source ../../.venv/bin/activate
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/v1/models
curl -fsS http://127.0.0.1:8000/openapi.json
python smoke_test.py --base-url http://127.0.0.1:8000 --model sensevoice
```

This optional smoke script downloads a public Chinese `sample.wav` if missing. It is not a multilingual accuracy benchmark; health/schema checks alone do not verify transcription. The Python script reads `MODEL`/`BASE_URL` or explicit flags, not `FUNASR_MODEL`. To check MOSS, change its `--model` as well, against the prepared MOSS service.

SDK base URLs include `/v1`; direct health checks do not:

```text
OpenAI SDK baseURL: http://127.0.0.1:8000/v1
Health endpoint:     http://127.0.0.1:8000/health
Transcription URL:   http://127.0.0.1:8000/v1/audio/transcriptions
```

Always send an explicit model. Check the deployed `/v1/models` and `/openapi.json`: for example, `paraformer-en` is an example-server alias, not a built-in packaged alias. For a packaged custom checkpoint configured by `--model-path` and `--hub`, request `model="custom"`; an arbitrary checkpoint ID is not an example-server alias. `whisper-1` is a compatibility alias for the startup model, not a Whisper checkpoint. See the [client response contract](CLIENTS.md#response-formats):

- `verbose_json` selects a format, not timestamp generation or diarization. The example only converts `sentence_info`, otherwise `segments=[]`; the packaged service can supply coarse text-based intervals. Segment times are seconds, not SDK milliseconds. Labels may be missing/null, strings or numbers, not speaker identities or verified alignment.
- The example's `duration` is elapsed `generate()` time, excluding initial loading, not audio duration; `language` is the submitted hint or `auto`, and it includes `model`. The packaged verbose response uses audio duration (possibly 0 on metadata failure), can use backend language detection, includes `task`/segment `id`/`words`, and omits top-level `model`.
- HTTP display text strips SenseVoice rich tags, without dedicated emotion/event fields. SDK `timestamp`, `timestamps`, `ctc_timestamps`, `use_itn`, hotwords and raw arrays are not extra example HTTP form fields. `spk=true` is packaged-only for non-native speaker processing, subject to dependencies; it is not enabled by these snippets. Base Nano does not imply the separate MLT checkpoint's language coverage.

## OpenAI JavaScript SDK

Use Node.js 22 for these recipes and pin the separate HTTP client to `openai@7.10.0`. This dependency selection is not a claim that every Node/SDK/framework version works or that an acoustic model was validated. In your own writable Node client project directory, separate from the Python server checkout, install the SDK:

```bash
npm install openai@7.10.0
```

Create `transcribe.mjs` in that client directory. Supply an existing WAV file as `meeting.wav` (or an absolute path) when running it. `.mjs` selects ESM and permits top-level await; the client does not create/download the audio file.

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

Run it:

```bash
node transcribe.mjs meeting.wav
```

The SDK needs an API key value even when local FunASR does not check it. A placeholder is only for an unprotected local endpoint; use real gateway credentials via server-side configuration when shared. The examples disable SDK retries to avoid repeating expensive requests. Choose timeouts for your admitted audio duration, and do not send CLI stdout (which contains the transcript) to public logs.

Both SDK examples open the file before constructing the upload, stream from that same handle, and close it even if the SDK rejects before reading. `toStreamingFile` preserves the basename for lazy multipart encoding without buffering the entire file. The `finished` rejection handler observes stream errors during cleanup; it does not turn a failed SDK request into a successful transcription.

## Built-in fetch without an SDK

The same Node.js 22 environment supplies `fetch`, `FormData` and `Blob`; this alternative needs no OpenAI SDK. Save it as `transcribe-fetch.mjs` in the client directory. The WAV example buffers the whole local file, so apply size/admission limits before using it in a shared worker. Do not set a multipart `Content-Type` header manually: FormData supplies the boundary.

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

Run from the client directory:

```bash
node transcribe-fetch.mjs meeting.wav
```

Use `FUNASR_BASE_URL` without `/v1`, unlike the SDK's `FUNASR_OPENAI_BASE_URL`. `FUNASR_API_KEY` is an optional bearer credential for your gateway, not built-in FunASR authentication. The fixed 120-second fetch signal stays active through `response.json()`; it is not an upload/download byte limit. Redirects are rejected rather than followed to another host. Errors print only a generic message/status, not raw upstream bodies; this is not a production logging or retry policy.

## TypeScript helper

- Place this helper in `funasr-client.ts` in an existing TypeScript project with the same OpenAI dependency. Do not run a `.ts` file as if it were the standalone `.mjs` command.
- The compiler dependency selection is `typescript@5.9.3` and `@types/node@22.18.6`, with Node.js 22.13.1. Configure Node module resolution (`module`/`moduleResolution`: `NodeNext`), an ES2022 target and `ES2022`/`DOM` libraries as appropriate for your project. These settings do not certify a Next.js build or deployment.
- This small application-owned subset is not runtime validation; the final cast does not validate server JSON or establish precise alignment. Optional fields must be checked before use, including absent/null speaker labels.

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

Keep the return type small and application-owned. The caller must handle rejection without exposing SDK error details to users. Fields not used by the application may be omitted from this interface; their service semantics remain those of the deployed endpoint.

## Next.js route handler

- **Placement and scope:** In an existing Next.js App Router application, use `app/api/transcribe/route.ts`. This function uses native `Request`/`Response` and declares the Node runtime; standalone TypeScript/Web API checks are not a Next.js project build or deployment certification.
- **Missing controls:** Authentication, upload byte limits, rate limits and privacy/audit policy are **not implemented**. Enforce ingress limits before `request.formData()` buffers the request, and protect the route before sharing. A proxy is not an authentication layer; no Next.js installation or authentication framework is included here.
- **Timeout scope:** The 120-second upstream timeout does not bound incoming upload parsing or payload size.
- **Fixed configuration:** Set `FUNASR_UPSTREAM_URL` to the operator-controlled transcription endpoint and `FUNASR_MODEL` to its alias in server-only environment configuration. The same-host default is loopback; containers need an intentionally reachable private service/gateway. Optional `FUNASR_API_KEY` supplies a bearer credential. Do not use `NEXT_PUBLIC_` variables or accept a target/model/credential from the uploaded form.

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

The handler rejects malformed uploads with 400, rejects redirects, and keeps the timeout active through JSON body reading. Upstream 400–599 errors retain their status but use a generic body; other unexpected statuses/non-JSON responses become 502, timeout becomes 504, and valid transcript JSON is returned as 200. It does not expose upstream HTML/error text. This is still a forwarding sketch, not a complete schema validator, bounded-response downloader or hardened production service.

## Production checklist

- Put TLS, authentication, upload-size limits, and rate limits in front of the API.
- Set request timeouts based on maximum audio duration; long recordings need longer HTTP timeouts.
- Log approved operational metadata such as model alias, response format, latency and error category. Distinguish audio duration from processing time; do not log raw upstream bodies, credentials, audio or transcripts by default.
- Run `GET /health` and `GET /v1/models` during readiness checks before accepting user uploads.
- Keep audio upload handling on the server side for browser applications.
- Pin `openai` package versions in production services and retest after SDK upgrades.

## Troubleshooting

- **SDK reports a missing API key:** Pass any placeholder `apiKey` for local development. This applies only to an unprotected local endpoint; configure real gateway credentials when shared.
- **404 from SDK calls:** Use `baseURL=http://localhost:8000/v1`; direct endpoint calls use `http://localhost:8000`. The local recipes above use the explicit loopback address `127.0.0.1`.
- **`unknown model`:** Call `/v1/models` and use one of the returned aliases. Also check which server implementation is running.
- **Browser upload fails with CORS or auth errors:** Send uploads to your backend first, then proxy to FunASR. Protect that backend and check actual gateway credentials and network routing rather than disabling protection.
- **Request times out:** Increase SDK or fetch timeouts, or split very long audio. Reassess admitted audio duration and update the actual timeout configuration; do not merely claim a larger limit in prose.
