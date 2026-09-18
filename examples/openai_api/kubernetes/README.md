# Kubernetes Deployment for the FunASR OpenAI-Compatible API

Deploy an internal speech endpoint for agents, web backends, workflow engines, or batch workers. Start with the SenseVoice CPU template; the separate MOSS GPU recipe below adds transcription with speaker diarization.

Run **every command from the FunASR repository root**, including commands in additional terminals. You need Docker, a writable image registry, `kubectl` configured for the intended cluster, permission to create resources in `speech`, and a default StorageClass for the cache PVCs. Replace the example registry before building. The local smoke client requires Python 3.10 or newer, with no third-party Python packages.

**ClusterIP is not authentication.** Neither manifest supplies a NetworkPolicy, authentication gateway, TLS, or request limits. Review the [service security guide](../SECURITY.md) before allowing untrusted clients. The recipes below use a local port-forward, not a public ingress.

The manifest is intentionally conservative:

- `ClusterIP` service by default, not a public `LoadBalancer`.
- `FUNASR_DEVICE=cpu` by default so the image matches the portable Dockerfile.
- A persistent cache volume mounted at `/root/.cache` so model downloads survive pod restarts.
- `/health` startup, readiness, and liveness probes.
- A memory-backed `/dev/shm` volume for PyTorch and audio preprocessing.

## 1. Build and push the image

Use the API directory as the CPU build context, while keeping your shell at the repository root:

```bash
docker build -f examples/openai_api/Dockerfile -t registry.example.com/speech/funasr-api:cpu-latest examples/openai_api
docker push registry.example.com/speech/funasr-api:cpu-latest
```

Set `images` in `examples/openai_api/kubernetes/kustomization.yaml` to the pushed image. For reproducible deployments, replace the example mutable tag with your registry's immutable digest. Record the image digest and manifest before each rollout so you can restore them. This CPU Dockerfile copies the example `server.py` but installs FunASR from PyPI; it does not install the checkout's FunASR package. Its dependencies are not a locked environment.

## 2. Deploy

```bash
kubectl create namespace speech --dry-run=client -o yaml | kubectl apply -f -
kubectl -n speech apply -k examples/openai_api/kubernetes
kubectl -n speech rollout status deploy/funasr-api --timeout=15m
```

The CPU server preloads its configured model before starting HTTP. Model download and first load can take several minutes. The startup probe has an approximately 10-minute failure budget (`10s` period, `60` failures); this does not include image pulls, scheduling, or PVC binding. A successful `/health` response is not an inference check: complete the audio request below before admitting traffic.

## 3. Smoke test

Keep the service private and verify it through `port-forward` first:

```bash
kubectl -n speech port-forward --address 127.0.0.1 svc/funasr-api 8000:8000
```

Leave port-forward running. In another terminal at the same repository root:

```bash
python3 examples/openai_api/smoke_test.py --base-url http://127.0.0.1:8000 --model sensevoice --response-format verbose_json
```

For in-cluster clients, use `http://funasr-api.speech.svc.cluster.local:8000` as the direct HTTP base URL and `http://funasr-api.speech.svc.cluster.local:8000/v1` as the OpenAI SDK base URL.

The smoke client downloads a public Chinese sample only if `sample.wav` is missing in the current directory; an existing file is reused. It prints health, model metadata, and the full transcription JSON. Inspect the text and timestamps yourself: exit status zero does not validate recognition accuracy, speaker labels, memory capacity, or concurrency. Avoid retaining sensitive audio or unredacted output. The client does not send Authorization; the security guide's transcription-only gateway intentionally denies metadata routes, so use this smoke recipe through the local port-forward, not that gateway.

## 4. Tune for your cluster

| Setting | Default | When to change it |
|---|---|---|
| `FUNASR_MODEL` | `sensevoice` | Check the model's dependencies and hardware requirements first; `/v1/models` lists aliases, not proof that each model is ready. |
| `FUNASR_DEVICE` | `cpu` | Set to `cuda` only after building a CUDA-capable image and configuring GPU scheduling. |
| PVC size | `20Gi` | Increase when caching multiple models or large model revisions. |
| Memory request | `8Gi` | Tune after observing startup and real audio workloads. |
| Startup probe | About 10 minutes | Tune for model initialization; diagnose image pulls, scheduling, and PVC binding separately. |

### MOSS GPU alternative

MOSS-Transcribe-Diarize is an OpenMOSS-Team model integrated into FunASR. This manifest runs the packaged FunASR HTTP adapter with `verbose_json`, not native vLLM or its `diarized_json` contract. Diarization labels are not verified speaker identity. For model requirements, outputs, no-external-VAD behavior, and other serving backends, use the [MOSS deployment guide](../../../docs/moss_transcribe_diarize.md).

The MOSS manifest is not included in `kustomization.yaml`. It requests one NVIDIA GPU, 24Gi memory, a 40Gi cache PVC, and an 8Gi memory-backed `/dev/shm`; these are template settings, not measured capacity guarantees. Configure the cluster's GPU device plugin and scheduling first. Unlike the CPU image, `Dockerfile.moss` copies and installs the whole checkout, so its build context must be the repository root. Use a clean checkout without credentials or private data in the build context.

```bash
docker build -f examples/openai_api/Dockerfile.moss -t registry.example.com/speech/funasr-api:moss-local .
docker push registry.example.com/speech/funasr-api:moss-local
```

Before applying, replace `funasr-moss-api:local` in `examples/openai_api/kubernetes/funasr-moss-api.yaml` with the pushed image's immutable digest. Create the `speech` namespace as in step 2 if you skipped the CPU deployment. Save the image digest and edited manifest as your rollback record.

```bash
kubectl -n speech apply -f examples/openai_api/kubernetes/funasr-moss-api.yaml
kubectl -n speech rollout status deploy/funasr-moss-api --timeout=15m
kubectl -n speech port-forward --address 127.0.0.1 svc/funasr-moss-api 8001:8000
```

In another terminal at the repository root, use local port 8001 to keep this endpoint separate from the CPU example:

```bash
python3 examples/openai_api/smoke_test.py --base-url http://127.0.0.1:8001 --model moss-transcribe-diarize --response-format verbose_json
```

The MOSS template has startup and readiness probes, but no liveness probe. Its `/health` response does not test transcription. Review the returned text and diarization against your audio; this recipe does not certify a particular GPU, real-time performance, or production load.

## GPU notes

The ordinary Dockerfile is CPU-first. Setting `FUNASR_DEVICE=cuda` alone does not make it a supported GPU image. For other GPU models, adapt the dependencies and scheduling. In the following field sketch, `resources` belongs to the container while `nodeSelector` belongs to the Pod spec; they are not a complete same-level manifest:

```yaml
resources:
  limits:
    nvidia.com/gpu: "1"
nodeSelector:
  nvidia.com/gpu.present: "true"
```

Exact GPU labels, runtime classes, and device plugin configuration vary by Kubernetes distribution. Keep the service private until authentication, TLS, upload-size limits, and rate limits are in place.

## Operational checks

- Check PVC binding, image pulls, Pod events, and model-loading logs before changing probe budgets. Then inspect `/health`, `/v1/models`, and a real audio response.
- Log model alias, device, audio duration, response format, latency, and error text.
- Start with one replica because the cache PVC is `ReadWriteOnce`; scale horizontally with a registry image, per-pod cache, or a shared read-only model cache after measuring memory and startup time.
- Enforce authentication and NetworkPolicy for the intended clients; a namespace alone is not a network isolation boundary.
- For Dify, n8n, or web backends inside the same cluster, point them at the Kubernetes service name instead of `localhost`.
