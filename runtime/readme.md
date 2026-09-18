# FunASR Runtime Deployment Guide

[简体中文](./readme_cn.md) | English

Select a model and protocol before selecting a container or binary. Start at the
[deployment matrix](../docs/deployment_matrix.md) for versioned commands,
tested hardware and known limits. Older release notes are preserved in
[release history](./release-history.md); they are not a current capacity promise.

## Choose a serving path

| Need | Entry point | Boundary |
| --- | --- | --- |
| Python HTTP transcription | [OpenAI-compatible server](../examples/openai_api/README.md) | Application API compatibility is separate from model accuracy or realtime support. |
| Fun-ASR-Nano decoder acceleration | [vLLM guide](../docs/vllm_guide.md) | Native vLLM and FunASR split-engine have different checkpoint/layout and API contracts. |
| Local portable GGUF inference | [llama.cpp](./llama.cpp/README.md) | Use the platform/backend package and matching GGUF model; build success is not every-device validation. |
| Native ONNX CPU inference | [ONNX Runtime](./onnxruntime/readme.md) | See the [JSONL/timestamp output contract](./docs/onnxruntime_binary_output.md). |
| Offline unified transcription and diarization | [MOSS-Transcribe-Diarize](../docs/moss_transcribe_diarize.md) | Third-party OpenMOSS model; offline anonymous speaker labels, not realtime or known-person identity. |
| Long-lived streaming or two-pass sessions | [C++ WebSocket protocol](./docs/websocket_protocol.md) | Do not send OpenAI HTTP requests or another runtime's WebSocket messages to this endpoint. |
| Cluster-managed private HTTP service | [Kubernetes templates](../examples/openai_api/kubernetes/README.md) | Configure resources, persistent cache, probes, upload limits and gateway policy for the target cluster. |

## File Transcription Service, Mandarin (GPU)

Follow the [GPU development guide](./docs/SDK_advanced_guide_offline_gpu.md).
The guide covers the native runtime stack; it is not an installation recipe for
every model in the Model Zoo. Benchmark your exact image, weights and GPU.

## File Transcription Service, English (CPU)

Use the [English tutorial](./docs/SDK_tutorial_en.md) and
[advanced configuration](./docs/SDK_advanced_guide_offline_en.md).
Select the English checkpoint rather than inferring language coverage from the
container name alone.

## Real-time Transcription Service, Mandarin (CPU)

Use the [streaming tutorial](./docs/SDK_tutorial_online.md), then verify the
[protocol](./docs/websocket_protocol.md) and
[matching multi-client example](./python/websocket/README.md).
Validate sample rate, chunking, finalization, reconnect behavior and session
isolation with actual audio. C++ two-pass and Fun-ASR-Nano Python streaming are
different implementations. The separate [Nano realtime benchmark](../docs/benchmark/realtime_ws_benchmark.md)
uses Nano's `START`/`STOP` protocol and must not be used against the C++ endpoint.

## File Transcription Service, Mandarin (CPU)

Use the [offline tutorial](./docs/SDK_tutorial.md) and
[advanced configuration](./docs/SDK_advanced_guide_offline.md).
[Model selection](../docs/model_selection.md) explains when Paraformer,
SenseVoice or a different recognizer fits the workload.

## Client and platform adapters

- [Python WebSocket](./python/websocket/README.md), [Python HTTP](./python/http/README.md), [Java](./java/readme.md), [Go](./golang/websocket/readme.md).
- [Browser client](./html5/readme.md), [gRPC](./grpc/Readme.md), [Triton](./triton_gpu/README.md).
- [Android](./android/readme.md) and [iOS](./ios/Readme.md) are separate porting guides, not a guarantee that each desktop release supports those devices.

Follow each adapter's protocol and dependency instructions. An SDK example is
not automatically a supported production package for every target platform.

## Production checklist

1. Record the exact commit/image digest, model revision, configuration and target hardware.
2. Run a known-audio transcription and inspect the raw output, not only a health endpoint.
3. Measure representative quality, latency, concurrency, memory and failure behavior.
4. Add authentication, TLS, request limits and privacy controls using the
   [security guide](../examples/openai_api/SECURITY.md).
5. Preserve the previous model/artifact/configuration and exercise rollback.
6. Report unresolved failures with the [troubleshooting checklist](../docs/troubleshooting.md);
   published code is not proof that a reporter's hardware issue is resolved.

## Historical releases

The [full release history](./release-history.md) preserves earlier Docker tags,
dates and benchmark references. For a new deployment, use a current
[deployment manual](https://www.funasr.com/en/deploy/) and its explicit test boundary.
