# Security and Gateway Guide for the FunASR OpenAI-Compatible API

Use this guide before sharing the OpenAI-compatible API with a team, workflow engine, browser UI, or service outside your laptop. Neither the example `server.py` nor packaged `funasr-server` implements gateway authentication or an application-level total-upload-size limit. Their default listener is `0.0.0.0`; putting a proxy in front does not change it. A reachable backend port can bypass the gateway. This is a deployment boundary to verify, not a claim that a particular running service is exposed.

## Recommended topology

```text
OpenAI SDK / Dify / n8n / browser UI
        |
        v
TLS + auth + upload limits + logs
(reverse proxy, API gateway, ingress, or service mesh)
        |
        v
FunASR OpenAI-compatible API
(private host, VM, container, or Kubernetes ClusterIP)
```

Keep FunASR on a private network whenever possible. Put public TLS, identity, request limits, and audit logging at the boundary that your team already operates.

For a proxy and backend on the same host, use the [prepared checkout and isolated Python environment](README.md#quick-start). From that checkout root, start only this loopback example; the command assumes installation is already complete:

```bash
cd examples/openai_api
source ../../.venv/bin/activate
python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000
```

- The packaged command also needs an explicit `--host 127.0.0.1` for same-host use. Do not run both servers on port 8000. Startup model/device choices and installation requirements remain those of the linked README.
- A container may need internal `0.0.0.0` for reachability. That is different from publishing its host port: the existing Compose default publishes port 8000 on all host interfaces. On the same host, use `FUNASR_HOST_PORT=127.0.0.1:8000 docker compose up --build`, or explicitly publish `127.0.0.1:8000:8000` in your own Docker command. Run Compose from `examples/openai_api` as an alternative startup method, not alongside a host server already using port 8000. This guide does not change the manifests.
- If the proxy is in another container/host, its `127.0.0.1` is not the backend. Configure a private service address and network/firewall rules that admit the proxy, not untrusted clients. `ClusterIP` is not authentication or namespace isolation; use an enforced `NetworkPolicy` and verify the actual network path.
- Test that an untrusted client cannot reach the backend directly. TLS and authentication on port 443 cannot protect a separately reachable port 8000. CORS is a browser policy, not an authentication or network-access boundary.

## Minimum controls before sharing

| Control | Why it matters | Where to enforce it |
|---|---|---|
| TLS | Audio often contains private data. | Reverse proxy, API gateway, or ingress. |
| Authentication | A local SDK `api_key` placeholder is not checked by FunASR. | Choose a matching Basic, Bearer, OAuth/OIDC, or internal SSO gateway/client pair. |
| Upload-size limits | Prevent accidental multi-GB uploads and memory pressure. | Gateway request-body limit and app-level checks. |
| Timeouts | Long recordings need longer HTTP timeouts, but stuck clients should not hang forever. | Client, proxy, and server process manager. |
| Rate limits | Protect GPU/CPU capacity from bursts. | Gateway, ingress controller, or queue worker. |
| Private operational routes | `/health`, `/v1/models` and schema/UI expose service metadata. | Deny them on the shared listener; design private monitoring access separately. |
| Logs and retention | Request metadata is useful; raw audio may be sensitive. | Central logging policy and storage lifecycle. |

The following sketches admit only exact `POST /v1/audio/transcriptions`. All other methods or paths are denied, including `/health`, `/v1/models`, `/openapi.json`, `/docs`, `/redoc` and the packaged `/asr` endpoint. A trailing slash is not the allowed path. Do not add a catch-all upstream location to make an SDK or monitoring probe work.

Rate/concurrency limits, model admission, queue budgets and upstream response redaction are **not implemented** by these sketches. Preloading one model does not restrict the example handler to that alias: a request can load another configured model. Set admission policy for shared CPU/GPU capacity. Both handlers read the upload into memory; the example also writes a temporary audio file. A compressed upload's byte size is not its decoded duration or memory cost.

## NGINX reverse proxy sketch

This is a Basic-auth starting point for NGINX 1.24, not a complete production policy. Provision the certificate chain and private key at the explicit paths below. Create `/etc/nginx/funasr.htpasswd` with an operator-managed `htpasswd` utility and an interactive password prompt, then restrict its permissions to the service's needs. Use `htpasswd -c /etc/nginx/funasr.htpasswd team_user` only when creating a new file; omit `-c` when updating it to avoid replacing other users. Never put the plaintext password in the configuration or command arguments. Missing credentials or an unreadable/missing password file must not grant access.

`200m` and `600s` are capacity-planning examples, not universally safe limits or a complete request deadline. In particular, proxy timeouts do not promise to cancel model work already running. Validate the actual configuration with your installed NGINX version before starting the listener.

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

## Caddy reverse proxy sketch

This sketch targets Caddy 2.11's `basic_auth` directive. Generate a password hash interactively with `caddy hash-password` and provide it as the service environment variable `FUNASR_BASIC_PASSWORD_HASH`, not as plaintext or a checked-in secret. Provision the TLS files below and restrict their permissions. Run `caddy adapt` and `caddy validate` with that environment before starting; a missing/invalid hash must not result in an unauthenticated fallback.

The explicit `route` keeps authentication before `request_body` and `reverse_proxy`. `200MiB` is intended to match the NGINX `200m` binary-unit example; validate it with the selected Caddy version. A body limit may be enforced while streaming, so an eventual 413 does **not** prove the upstream received zero bytes. Test this boundary with your actual proxy; do not claim buffering or complete-upload admission without evidence. These static-certificate recipes do not establish public DNS or automatic ACME issuance.

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

Both sketches remove `Authorization` before forwarding: FunASR does not need the gateway's Basic credentials. Do not mistake header forwarding for authentication. For production teams, prefer your standard SSO/OIDC gateway over shared passwords, with an explicitly matching client configuration and route policy.

## Kubernetes notes

The Kubernetes template uses `ClusterIP`, not a public `LoadBalancer`. This alone does not prevent other pods or reachable hosts from calling it. Before adding an ingress or load balancer:

- Add an ingress controller or API gateway that enforces TLS, authentication, upload-size limits, and rate limits.
- Keep model cache volumes private to the namespace or node pool that owns the service.
- Use `NetworkPolicy` to restrict which namespaces can call the service.
- Use `kubectl port-forward` plus `smoke_test.py` for first validation before exposing a route.
- If you add GPUs, pin scheduling rules and record the image tag, CUDA runtime, and model alias in deployment notes.

## Client configuration

**Basic gateways above:** use a Basic-capable client. This command prompts for `team_user`'s password and uploads an existing local file; it does not put the password in the command line, follow redirects or disable certificate verification. Run from a directory containing `meeting.wav`, and replace the hostname with your configured TLS gateway. It prints only the HTTP status, not the transcript or an upstream error body; verify the expected status rather than treating every curl exit code as inference success.

```bash
curl --user team_user --fail --show-error --silent \
  --max-time 600 --output /dev/null --write-out 'HTTP %{http_code}\n' \
  -F 'file=@meeting.wav' -F 'model=sensevoice' \
  -F 'response_format=verbose_json' \
  https://funasr.example.com/v1/audio/transcriptions
```

**Bearer gateways only:** OpenAI SDKs usually require an API key string even when FunASR does not check it locally. The following client initialization assumes a separate gateway that accepts an `Authorization: Bearer` token. A Basic password or password hash is not a Bearer token; this SDK configuration does not authenticate to the Basic sketches above. An OIDC browser session, mTLS certificate or arbitrary SSO credential is not automatically an SDK key either. Configure the actual gateway/client scheme rather than changing FunASR's placeholder key. Install the separate client with `python -m pip install openai` in your client environment.

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

For internal HTTP workers, read tokens from environment variables or your secret manager. Do not commit tokens to workflow definitions, notebooks, screenshots, or Postman exports.

## Data handling checklist

- Decide whether raw audio can be stored, for how long, and who can access it.
- Log request IDs, duration, model alias, status, latency, and error class; avoid logging raw transcript text unless your policy allows it.
- If transcripts may contain personal data, document retention and deletion rules before onboarding users.
- Keep public samples separate from private customer or employee audio when writing benchmark reports.
- Redact headers, tokens, file names, and speaker names before opening GitHub issues.
- The example writes temporary audio to disk and normally unlinks it after processing. That is not a no-disk or secure-erasure guarantee; handle crash leftovers, proxy buffers, disk permissions and storage retention explicitly.
- The example logs exception text and returns it as HTTP error detail. Upstream responses and application logs are not automatically redacted by either proxy sketch. Define who may see them and sanitize them before sharing; deleting an audio file does not delete its transcript or logs.

## Rollout checklist

These are acceptance checks to perform on your deployment, not a claim that your gateway or public service has passed them:

1. **Local diagnostic:** from the same prepared checkout/environment, use the unauthenticated local loopback endpoint with `python smoke_test.py meeting.wav --base-url http://127.0.0.1:8000 --model sensevoice`. The bundled Python/Bash smoke tool does not send gateway credentials. A missing audio path may download the public Chinese sample; output includes transcription and, for the Python tool, upstream error details. Keep that diagnostic private, not in shared automated logs.
2. **Authenticated upload:** through the configured TLS gateway, valid Basic credentials plus an allowed small file should reach only the intended transcription route and return the expected result. Verify filename, bytes, model and absence of the gateway `Authorization` header at a controlled upstream, without logging real credentials/audio.
3. **Unauthorized request:** a small allowed POST with missing/wrong credentials must return 401 without invoking inference. This does not prescribe which error wins when a request also exceeds a limit or is malformed. Missing/unreadable NGINX credentials or missing/invalid Caddy hash must fail closed, not fall back to unauthenticated proxying.
4. **Other routes/methods:** `/health`, `/v1/models`, `/openapi.json`, `/docs`, `/redoc`, `/asr`, trailing-slash variants and unrelated paths must remain denied (404 in these catch-all handlers). A non-POST on the exact inference path is denied too; NGINX may return 403 while Caddy uses the fallback 404. Do not open metadata routes to make a local smoke script pass through the public gateway; private monitoring needs a separate policy.
5. **Size/capacity:** check a small file, a large allowed file and an over-limit request (expected 413). Observe upstream effects separately; especially with streaming enforcement, 413 alone does not imply zero upstream bytes. Assess decoded duration, concurrency and model admission rather than treating 200m/200MiB as a capacity guarantee.
6. **Timeouts:** test slow upload, slow upstream and long inference. A client/proxy timeout is not proof that model computation was cancelled, and the sketches do not implement a complete inference scheduling/deadline policy.
7. **Bypass and recording:** from an untrusted network verify direct backend access is blocked. Record the actual model alias, device, image/FunASR/proxy versions, certificate provisioning and gateway policy. Do not infer a fresh installation, acoustic accuracy or production readiness from a small controlled HTTP fixture.

Related guides: [OpenAI API README](README.md), [client recipes](CLIENTS.md), [workflow recipes](WORKFLOWS.md), [Gradio browser demo](GRADIO.md), [Kubernetes template](kubernetes/README.md), and the repository [security policy](../../SECURITY.md).
