# FunASR 运行时部署指南

简体中文 | [English](./readme.md)

先确定模型和协议，再选择容器或二进制包。[部署矩阵](../docs/deployment_matrix_zh.md)
给出固定版本命令、验证硬件和已知限制。旧发布说明保留在
[历史记录](./release-history_zh.md)，不能直接作为当前服务容量承诺。

## 选择服务路径

| 需求 | 入口 | 边界 |
| --- | --- | --- |
| Python HTTP 转写 | [OpenAI 兼容服务](../examples/openai_api/README_zh.md) | API 兼容、模型质量和实时能力是不同问题。 |
| Fun-ASR-Nano 解码加速 | [vLLM 指南](../docs/vllm_guide_zh.md) | 原生 vLLM 与 FunASR split-engine 的权重布局和接口契约不同。 |
| 本地便携 GGUF 推理 | [llama.cpp](./llama.cpp/README.md) | 使用匹配的平台/后端包和 GGUF 模型；构建成功不等于所有设备验证通过。 |
| 原生 ONNX CPU 推理 | [ONNX Runtime](./onnxruntime/readme.md) | 输出字段见 [JSONL 与时间戳契约](./docs/onnxruntime_binary_output_zh.md)。 |
| 统一离线转写与说话人分离 | [MOSS-Transcribe-Diarize](../docs/moss_transcribe_diarize_zh.md) | OpenMOSS 第三方模型，输出匿名说话人标签，不是实时或已知人物身份识别。 |
| 长连接流式 / 双遍会话 | [C++ WebSocket 协议](./docs/websocket_protocol_zh.md) | 不能向该端点发送 OpenAI HTTP 请求或其他实现的 WebSocket 消息。 |
| 集群内私有 HTTP 服务 | [Kubernetes 模板](../examples/openai_api/kubernetes/README_zh.md) | 按目标集群配置资源、持久缓存、探针、上传限制和网关策略。 |

## 中文离线文件转写服务（GPU版本）

按 [GPU 部署开发指南](./docs/SDK_advanced_guide_offline_gpu_zh.md)配置原生运行时。
它不是 Model Zoo 中每个模型的通用安装方法；需要用实际镜像、权重和 GPU 复测。

## 英文离线文件转写服务（CPU版本）

参见[英文服务教程](./docs/SDK_tutorial_en.md)和
[高级配置](./docs/SDK_advanced_guide_offline_en.md)。
显式选择英文权重，不要只凭容器名推断语言覆盖。

## 中文实时语音听写服务（CPU版本）

先运行[流式教程](./docs/SDK_tutorial_online_zh.md)，再按
[协议](./docs/websocket_protocol_zh.md)与
[对应的多客户端示例](./python/websocket/README.md)验证。
重点检查采样率、音频分块、结束消息、重连和不同会话之间的状态隔离。
C++ 双遍服务与 Fun-ASR-Nano Python 流式服务是不同实现。
另一个 [Nano 实时压测工具](../docs/benchmark/realtime_ws_benchmark.md)使用
Nano 的 `START`/`STOP` 协议，不能对 C++ 服务使用。

## 中文离线文件转写服务（CPU版本）

参见[离线教程](./docs/SDK_tutorial_zh.md)和
[高级配置](./docs/SDK_advanced_guide_offline_zh.md)。
Paraformer、SenseVoice 等模型的选择边界见[模型选择](../docs/model_selection_zh.md)。

## 客户端与平台适配

- [Python WebSocket](./python/websocket/README.md)、[Python HTTP](./python/http/README.md)、[Java](./java/readme.md)、[Go](./golang/websocket/readme.md)。
- [浏览器客户端](./html5/readme_zh.md)、[gRPC](./grpc/Readme.md)、[Triton](./triton_gpu/README.md)。
- [Android](./android/readme.md) 与 [iOS](./ios/Readme.md) 是独立移植指南，
  不代表每个桌面发布包都验证过这些设备。

不同适配器的协议和依赖以各自文档为准，示例代码不自动等于所有目标平台的生产支持。

## 上线检查清单

1. 固定代码 commit / 镜像 digest、模型 revision、配置与目标硬件。
2. 用已知音频检查真实转写和原始返回值，不只检查 health 端点。
3. 分别评测业务音频质量、延迟、并发、内存与失败行为。
4. 依据[安全指南](../examples/openai_api/SECURITY_zh.md)配置认证、TLS、请求限制和隐私控制。
5. 保留上一版模型、产物和配置，并实际演练回滚。
6. 按[排障清单](../docs/troubleshooting_zh.md)提交未解决问题；
   代码发布不能证明用户报告的硬件问题已经解决。

## 历史发布记录

[完整历史记录](./release-history_zh.md)保留早期 Docker 标签、日期和性能评测引用。
新部署以当前[部署手册](https://www.funasr.com/deploy/)和明确的验证边界为准。
