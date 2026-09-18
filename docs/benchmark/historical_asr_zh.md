# 历史 ASR 评测

[English](historical_asr.md)

这是一份**来源不完整的历史记录**，用于帮助读者理解早期 FunASR 对比结果。
它不是新测量、通用排行榜，也不是对当前 checkpoint、机器或部署的保证。
开展新的评测请先阅读[性能评测方法](rtf_reproducibility.md)。

## 历史概览

下表保留原报告的措辞与数字。“最佳”等标签仅指该份报告，不能推广到所有模型或硬件。

| 指标 | 结果 |
| --- | --- |
| 数据集 | 184 条中文长音频，总时长 11,539 秒，约 192.3 分钟。 |
| GPU | NVIDIA H100 80GB HBM3. |
| 最佳 GPU 速度 | SenseVoice-Small: 169.6x realtime in the full benchmark, 211.8x in the initial run. |
| 最佳 CPU 速度 | SenseVoice-Small: 17.2x realtime; Paraformer-Large: 15.6x realtime. |
| 基线 | OpenAI Whisper-large-v3：GPU 上 13.4 倍实时。 |

**完整运行的 169.6x 与初次运行的 211.8x 是两个独立报告的结果**。
原页面没有披露测量日期。**2026-09-07 是本次来源快照核对日期，不是测量日期**。

## 历史结果

下表全部数值和说明都是原报告的历史表述，**不是当前 API 能力保证**。
模型原始输出包含标签，不代表 HTTP 接口一定返回这些标签；旧时间戳限制也不能代替
当前的[模型选型说明](../model_selection_zh.md)。

| 模型 | 设备 | RTF | 速度 | CER | 说明 |
| --- | --- | --- | --- | --- | --- |
| SenseVoice-Small | GPU | 0.005896 | 169.6x | 7.81% | ASR + 语种 / 情感 / 事件标签；CER 已去除标签后计算。 |
| Paraformer-Large | GPU | 0.008359 | 119.6x | 10.18% | 高速非自回归中文 ASR，适合 VAD/标点生产流水线。 |
| Fun-ASR-Nano | GPU | 0.058803 | 17.0x | 8.06% | LLM-based 中/英/日 ASR，另覆盖 7 类中文方言和 26 种地域口音，支持热词；不提供可靠的 checkpoint 原生时间戳（[#106](https://github.com/QwenAudio/Fun-ASR/issues/106)）。 |
| GLM-ASR-Nano | GPU | 0.026974 | 37.1x | 31.07% | LLM-based 多语种 ASR。 |
| Whisper-large-v3-turbo (OpenAI) | GPU | 0.021708 | 46.1x | 21.71% | OpenAI Whisper 实现。 |
| Whisper-large-v3 (OpenAI) | GPU | 0.074694 | 13.4x | 20.02% | 基线 for large Whisper quality. |
| SenseVoice-Small | CPU | 0.057988 | 17.2x | 7.81% | CPU 结果来自 remaining benchmark 脚本。 |
| Paraformer-Large | CPU | 0.064056 | 15.6x | 10.18% | CPU 上可用于批量任务。 |
| Fun-ASR-Nano | CPU | 0.274318 | 3.6x | 8.06% | LLM-based 模型更重，但仍高于实时。 |

CPU/GPU 行重复出现相同 CER，不能证明曾分别独立评分。审计材料中没有原始预测、
参考文本或评分程序。“去除标签后计算”保留为历史说法，不是本次验证过的评分输出。
原始精度以及经过舍入的速度/RTF 数值对均原样保留，不重新计算。

## 来源与限制

[原中文 HTML](https://github.com/modelscope/FunASR/blob/67d63b80a246dc33749e43904c294e0409cd9183/zh/benchmark.html)
固定到历史 GitHub Pages 提交；本次核对时，该文件与旧公网快照逐字节一致。
这能确认表格出处，但不能证明原始测量正确或可复现。

原报告将 RTF 定义为总推理时间除以总音频时长，速度为其倒数，后者也称 RTFx：

```text
RTF  = total inference time / total audio duration
RTFx = total audio duration / total inference time = 1 / RTF
```

以下命令仅是**历史文本，不能直接执行**：在本次审计的 FunASR 源码版本
`386f6f9106684ba5a114e796147db4396a09eab5` 中，三个文件都不存在。
本页没有提供替代脚本或复现数据。

```text
python benchmark/run_full_benchmark.py
python benchmark/run_remaining.py
python benchmark/fix_sensevoice_cer.py
```

审计的原报告未披露 CPU 型号/线程数、数据成员与参考文本清单、精确 checkpoint
revision、软件/驱动版本、逐文件预测和计时日志，以及是否包含预热、I/O、预处理等
完整计时范围。缺少这些材料，旧表无法直接复现，“CPU 对比 GPU”的标题也不能视作
面向所有生产环境的保证。

这份记录的 **11,539 秒**必须与 [vLLM 评测方法](rtf_reproducibility.md) 中的
**11,541 秒**分开引用。两者都提到 184 个文件，并不能证明数据成员完全一致；
不要合并两份表格的结果，也不要自行消除两秒差异。

## 当前选型

下面是**原报告的建议表，仅保留为历史上下文**，不是新验证的推荐或性能排名。

| 需求 | 推荐模型 |
| --- | --- |
| 最快生产转写 | SenseVoice-Small 或 Paraformer-Large。 |
| CPU 批量转写 | 优先 SenseVoice-Small；中文生产流水线可选 Paraformer-Large。 |
| 中/英/日及中文方言、口音的 LLM-style 识别 | Fun-ASR-Nano；需要 31 语种时使用独立的 [Fun-ASR-MLT-Nano](https://huggingface.co/FunAudioLLM/Fun-ASR-MLT-Nano-2512) checkpoint，并使用 [vLLM](../vllm_guide_zh.md) 提升 LLM 解码吞吐。 |
| OpenAI 兼容本地服务 | 使用 [funasr-server](../agent_integration_zh.md)，模型别名为 `sensevoice`、`paraformer` 或 `fun-asr-nano`。 |

当前决策请参考[模型与能力说明](../model_selection_zh.md)、
[Agent 接口契约](../agent_integration_zh.md)和 [vLLM 部署说明](../vllm_guide_zh.md)。
独立 MLT checkpoint 的语种覆盖不能归到 Fun-ASR-Nano；选型前请使用自己的音频、
运行时与端到端延迟要求进行评估。

新的测量按[性能评测方法](rtf_reproducibility.md)记录；并发实时服务参考
[WebSocket 压测说明](realtime_ws_benchmark.md)。当前的
[迁移计时工具](../../examples/migration/benchmark_funasr.py)只测量 FunASR 在自有音频
上的表现，**不计算 CER/WER**、不运行 Whisper，也不复现缺失的历史脚本。
请分别记录计时范围、失败文件和质量评估。
