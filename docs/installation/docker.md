([简体中文](./docker_zh.md) | English)

# Docker and runtime images

Choose the execution path before pulling an image. The Python `AutoModel` SDK, a C++ runtime server, and a development environment are different products of the repository. Installing a newer Python package inside a published runtime image does not rebuild its C++ executable or add every Python model to that server.

## 1. Verify Docker on the host

Install Docker using the [Docker Engine instructions](https://docs.docker.com/engine/install/) for Linux or Docker Desktop for macOS/Windows ([Windows reference](https://docs.docker.com/desktop/install/windows-install/)). Avoid piping an unreviewed installation script into a privileged shell.

```sh
docker version
docker info
```

GPU containers additionally need a compatible host driver and container GPU setup. `--gpus all` requests access; it does not install the driver or make a CPU image GPU-capable. Check image architecture against the host before using it.

## 2. Select a runtime or development path

These exact image references are documented in this checkout. They are repository evidence, not a claim that registry availability, security updates, or inference were checked during this documentation review.

| Path | Repository-documented image or build | Where to continue |
| --- | --- | --- |
| Offline C++ CPU service | `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-cpu-0.4.7` | [CPU service guide](../../runtime/docs/SDK_advanced_guide_offline.md) |
| Offline C++ GPU service | `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-gpu-0.2.1` | [GPU service guide](../../runtime/docs/SDK_advanced_guide_offline_gpu.md) |
| Online/two-pass C++ CPU service | `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-online-cpu-0.1.13` | [Online service guide](../../runtime/docs/SDK_advanced_guide_online.md) |
| Rebuild online CPU runtime from this checkout | [Dockerfile.online.cpu](../../runtime/dockerfile/Dockerfile.online.cpu), with a digest-pinned base | Same online guide; rebuilds the C++ server and installs this source tree |
| Python SDK development | A separately selected, validated Python/PyTorch environment | [Source installation](./installation.md); record the base image digest and package versions |

The maintained source-build path above is distinct from the historical development image advertised by older versions of this page:

`registry.cn-hangzhou.aliyuncs.com/modelscope-repo/modelscope:ubuntu20.04-py38-torch1.11.0-tf1.15.5-1.8.1`

That ModelScope development image is retained here as a historical reference, not a recommended current FunASR runtime or a guarantee of compatibility with new model dependencies. The former CPU tag `funasr-runtime-sdk-cpu-0.4.1` is likewise historical; see the [runtime release history](../../runtime/readme.md).

## 3. Inspect a published image without exposing a service

For example, prepare an offline CPU runtime shell. Run these commands in a POSIX shell, in a directory where you want a dedicated model folder:

```sh
IMAGE=registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-cpu-0.4.7
docker pull "$IMAGE"
docker image inspect "$IMAGE" --format '{{.Os}}/{{.Architecture}} {{json .RepoDigests}}'
mkdir -p ./funasr-models
docker run --rm -it --name funasr-runtime-shell \
  --mount "type=bind,src=$(pwd)/funasr-models,dst=/workspace/models" \
  --entrypoint /bin/bash "$IMAGE"
```

This starts a shell, not a configured transcription service. `exit` removes this temporary container; the bind-mounted model files persist. To inspect or stop it from another terminal:

```sh
docker ps --filter name=funasr-runtime-shell
docker stop funasr-runtime-shell
```

Continue with the matching service guide for model selection, executable options, protocol, and clients. When publishing a test service, bind to loopback (for example `-p 127.0.0.1:10095:10095`) until access controls and transport security are configured. Avoid `--privileged`, host-root mounts, credentials baked into images, and unreviewed public port exposure. Some historical guide commands use broader permissions; assess requirements rather than copying them blindly.

## 4. Build the online CPU runtime from source

From the repository root, after reviewing its Dockerfile and build context:

```sh
docker build -f runtime/dockerfile/Dockerfile.online.cpu \
  -t funasr-online-cpu:local .
```

`funasr-online-cpu:local` is a locally chosen build tag, not a published registry release. The Dockerfile copies the checkout, installs it in editable mode, and compiles `runtime/websocket`. A completed build alone is not a model-inference test. Follow the [online runtime guide](../../runtime/docs/SDK_advanced_guide_online.md) for startup and validation; do not assume it includes later commits without rebuilding.

For SDK development, install the checkout into a reviewed Python/PyTorch container using the [installation guide](./installation.md), then run the [SDK tutorial](../tutorial/README.md). This page does not invent a universal development-image tag or model compatibility matrix.

Model caches, offline preparation, remote-code trust, and separate software/model licenses still apply inside a container; see [installation and security](./installation.md). Keep exact image digests, source commits, and model revisions with your test results. More runtime choices: [runtime overview](../../runtime/readme.md) and [quick start](../../runtime/quick_start.md).
