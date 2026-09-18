(简体中文 | [English](./docker.md))

# Docker 与运行时镜像

拉取镜像前先选择执行路径。Python `AutoModel` SDK、C++ 运行时服务和开发环境是不同的使用方式。在已发布运行时镜像里升级 Python 包，不会重新编译 C++ 可执行文件，也不会让服务自动支持所有 Python 模型。

## 1. 检查宿主机 Docker

Linux 请按 [Docker Engine 安装说明](https://docs.docker.com/engine/install/)操作，macOS/Windows 使用 Docker Desktop（[Windows 参考](https://docs.docker.com/desktop/install/windows-install/)）。不要将未经审查的安装脚本通过管道交给高权限 shell 执行。

```sh
docker version
docker info
```

GPU 容器还需要兼容的宿主机驱动和容器 GPU 配置。`--gpus all` 只是请求设备访问权限，不会安装驱动，也不会把 CPU 镜像变成 GPU 镜像。使用前请确认镜像与宿主机架构匹配。

## 2. 选择运行时或开发路径

下列精确镜像引用来自当前工作区文档，仅表示仓库中有据可查，不表示本次文档审查已验证镜像仓库可用性、安全更新或模型推理。

| 路径 | 仓库记录的镜像或构建入口 | 后续指南 |
| --- | --- | --- |
| 离线 C++ CPU 服务 | `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-cpu-0.4.7` | [CPU 服务指南](../../runtime/docs/SDK_advanced_guide_offline_zh.md) |
| 离线 C++ GPU 服务 | `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-gpu-0.2.1` | [GPU 服务指南](../../runtime/docs/SDK_advanced_guide_offline_gpu_zh.md) |
| 在线/两遍 C++ CPU 服务 | `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-online-cpu-0.1.13` | [在线服务指南](../../runtime/docs/SDK_advanced_guide_online_zh.md) |
| 从当前源码重建在线 CPU 运行时 | [Dockerfile.online.cpu](../../runtime/dockerfile/Dockerfile.online.cpu)，使用 digest 锁定的基础镜像 | 同上；会重编译 C++ 服务并安装当前源码 |
| Python SDK 开发 | 单独选择并验证的 Python/PyTorch 环境 | [源码安装](./installation_zh.md)；记录基础镜像 digest 和依赖版本 |

上述持续维护的源码构建路径与本页旧版本推荐的历史开发镜像不同：

`registry.cn-hangzhou.aliyuncs.com/modelscope-repo/modelscope:ubuntu20.04-py38-torch1.11.0-tf1.15.5-1.8.1`

保留该 ModelScope 开发镜像仅供历史查阅，不将它作为当前 FunASR 运行时推荐，也不保证与新模型依赖兼容。旧 CPU 标签 `funasr-runtime-sdk-cpu-0.4.1` 同属历史记录，参见[运行时版本历史](../../runtime/readme_cn.md)。

## 3. 先检查镜像，不对外暴露服务

以进入离线 CPU 运行时 shell 为例。在 POSIX shell 中，切换到希望存放独立模型目录的位置后执行：

```sh
IMAGE=registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-cpu-0.4.7
docker pull "$IMAGE"
docker image inspect "$IMAGE" --format '{{.Os}}/{{.Architecture}} {{json .RepoDigests}}'
mkdir -p ./funasr-models
docker run --rm -it --name funasr-runtime-shell \
  --mount "type=bind,src=$(pwd)/funasr-models,dst=/workspace/models" \
  --entrypoint /bin/bash "$IMAGE"
```

这仅启动 shell，不是已经配置好的转写服务。输入 `exit` 后临时容器会被删除，挂载目录中的模型文件会保留。可从另一终端查看或停止容器：

```sh
docker ps --filter name=funasr-runtime-shell
docker stop funasr-runtime-shell
```

模型选择、可执行文件参数、协议与客户端请看对应服务指南。发布测试端口时，先绑定回环地址（例如 `-p 127.0.0.1:10095:10095`），再配置访问控制与传输安全。避免 `--privileged`、挂载宿主机根目录、将凭据烘焙进镜像，以及未经审查地开放公网端口。部分历史指南的命令权限较宽，应按实际需求评估，不要直接照搬。

## 4. 从源码构建在线 CPU 运行时

审查 Dockerfile 与构建上下文后，在仓库根目录执行：

```sh
docker build -f runtime/dockerfile/Dockerfile.online.cpu \
  -t funasr-online-cpu:local .
```

`funasr-online-cpu:local` 是本地构建标签，不是镜像仓库发行版本。Dockerfile 会复制当前工作区、执行可编辑安装，并编译 `runtime/websocket`。构建成功不等于模型推理通过。启动与验证请按[在线运行时指南](../../runtime/docs/SDK_advanced_guide_online_zh.md)执行；源码更新后，已有镜像不会自动包含新提交，需要重建。

开发 Python SDK 时，请在审查过的 Python/PyTorch 容器中按[安装指南](./installation_zh.md)安装源码，再运行 [SDK 教程](../tutorial/README_zh.md)。本页不提供未经仓库验证的通用开发镜像标签或模型兼容矩阵。

容器内仍需遵守模型缓存、离线准备、远程代码信任和软件/模型分别许可的要求，参见[安装与安全说明](./installation_zh.md)。测试记录应包含精确镜像 digest、源码 commit 和模型 revision。更多运行时路径：[概览](../../runtime/readme_cn.md)与[快速开始](../../runtime/quick_start_zh.md)。
