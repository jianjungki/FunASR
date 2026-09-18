简体中文 | [English](speaker_emotion.md)

# 说话人与情感标签

先确定需要的结果，再选择模型。声纹向量、匿名聚类编号、已注册人员身份与情感标签
是四类不同输出，不能互相替代。

## 按任务选择

| 任务 | 路径 |
| --- | --- |
| 从选定语音提取一个说话人向量 | CAMPPlus 或 ERes2NetV2；见下方示例 |
| 为转写片段分配匿名说话人 | [ASR/VAD/说话人流水线](python_api_zh.md#vad时间戳与说话人) |
| 保留转写、情感和音频事件标签 | SenseVoiceSmall；见下方示例 |
| 联合转写与匿名说话人分离 | 第三方 [OpenMOSS MOSS 指南](moss_transcribe_diarize_zh.md) |

CAMPPlus 与 ERes2NetV2 返回 `spk_embedding` Tensor，不返回人的姓名、匹配结论
或通用 ASR `text` 字段。单条输入通常对应一行，向量维度由检查点配置决定，
不是接口保证永远只有 192 维。本例使用 `batch_size=1`；部分批处理路径会在一个
字典内返回多行向量，而非每个输入对应一个带 `key` 的结果。

向量本身不等于身份确认。注册、匹配、阈值校准、授权及面向目标人群的评测需要
应用单独设计。`spk=0` 或 MOSS 的 `S01` 是录音内的匿名标签，不是跨录音稳定的人员 ID。
`spk_embedding_center` 是聚类均值，不表示已经完成身份注册。

## 准备本地检查点

完成[安装检查](installation/installation_zh.md)，准备包含配置、前端、适用时的
tokenizer 及权重的完整本地快照。阅读各模型许可证，记录解析后的 revision 或文件哈希、
SDK 版本、实际导入模块路径与源码 commit。本指南对应文末链接的实现，不保证所有旧版
wheel、导出后端或模型变体接口一致。

- **CAMPPlus（`embedding`）：** `iic/speech_campplus_sv_zh-cn_16k-common`。
  ModelScope 别名为 `cam++`。
- **ERes2NetV2（`embedding`）：** `iic/speech_eres2netv2_sv_zh-cn_16k-common`。
- **SenseVoice（`sensevoice`）：** `iic/SenseVoiceSmall`。

`embedding` 和 `sensevoice` 选项只属于下方示例程序，不是新增的 FunASR 模型别名或 CLI 子命令。
不要把 ASR 检查点传给 `embedding`，也不要将 ERes2NetV2 的行为推广到所有 ERes2Net 变体。
其他模型请查看 [Model Zoo](../model_zoo/readme_zh.md)。

音频使用非空、单声道、16 kHz WAV。程序读取归一化 `float32` 波形，拒绝立体声、空音频
或其他采样率，不隐式转换。提取声纹时使用选定的单人有效语音；混合说话人、静音或极短
片段不能提供可靠身份依据。下方校验仅检查格式，不是语音质量检测器。

## 保存结果并保留原始标签

独立程序接收 `task`、`model_dir`、`audio` 和新的 JSON 输出路径。例如在脚本名后传入
`embedding /models/campplus speaker.wav vector.json`，或
`sensevoice /models/sensevoice utterance.wav tags.json`。
两个模式都在 CPU 上处理完整片段，不添加 VAD、标点、配套说话人模型或流式缓存，
程序内部不下载模型。

```python
import argparse
import json
import os
from pathlib import Path
import soundfile as sf
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess


def embedding_record(results):
    if not results:
        raise ValueError("No result from the speaker model")
    if len(results) != 1:
        raise ValueError("Expected one speaker result for one input")
    vector = results[0]["spk_embedding"]
    if vector.ndim != 2 or vector.shape[0] != 1 or vector.shape[1] == 0:
        raise ValueError("Expected a nonempty single-row speaker embedding")
    return {"spk_embedding": vector.detach().cpu().tolist()}


def tagged_records(results):
    if not results:
        raise ValueError("No result from SenseVoice")
    records = []
    for item in results:
        raw = item["text"]
        if not isinstance(raw, str):
            raise ValueError("Expected SenseVoice text with its original tags")
        records.append({
            "key": item.get("key"), "raw_tagged_text": raw,
            "display_text": rich_transcription_postprocess(raw),
        })
    return records


def write_result(path, record):
    payload = json.dumps(record, ensure_ascii=False, allow_nan=False, indent=2)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(payload + "\n")


parser = argparse.ArgumentParser()
parser.add_argument("task", choices=["embedding", "sensevoice"])
parser.add_argument("model_dir")
parser.add_argument("audio")
parser.add_argument("output")
args = parser.parse_args()
model_dir = Path(args.model_dir).expanduser().resolve(strict=True)
if not model_dir.is_dir():
    raise ValueError("Expected a complete local model directory")
speech, sample_rate = sf.read(args.audio, dtype="float32")
if sample_rate != 16000 or speech.ndim != 1 or len(speech) == 0:
    raise ValueError("Expected nonempty mono 16 kHz audio")
model = AutoModel(
    model=str(model_dir), device="cpu", ncpu=1, disable_update=True,
    trust_remote_code=False, vad_model=None, punc_model=None, spk_model=None,
)
if args.task == "embedding":
    results = model.generate(input=speech, fs=sample_rate, batch_size=1)
    result = embedding_record(results)
else:
    results = model.generate(
        input=speech, fs=sample_rate, batch_size=1,
        language="auto", use_itn=True, output_timestamp=False,
    )
    result = tagged_records(results)
write_result(args.output, {
    "task": args.task, "model_dir": str(model_dir),
    "sample_rate": sample_rate, "result": result,
})
```

外层 JSON、`raw_tagged_text` 和 `display_text` 是示例应用创建的字段，不是 SDK 新增返回字段。
向量先显式 detach、移到 CPU，再转换为嵌套列表。非有限数值会在创建文件前被拒绝。
程序不会覆盖已有输出，每次运行使用新路径。POSIX 上以仅所有者可访问的模式创建文件；
仍需配置目录权限及对应平台 ACL。声纹向量和转写可能涉及敏感信息，应按需保留，
不要公开私人音频或结果。

## 正确读取 SenseVoice 标签

原始带标签字符串通常在 `result["text"]`，不能假设存在 `raw_text`、`emotion` 或
`emotion_score`。标签区分大小写，例如 `<|zh|>`、`<|HAPPY|>`、`<|Speech|>`、
`<|withitn|>`；是否出现及其含义取决于检查点。展示映射表不保证所有模型都会输出其中全部标签。

`rich_transcription_postprocess` 是有损展示函数：删除标签、按出现次数选择展示情感、
合并重复展示标记，还会做文本替换。它不是结构化标签解析器或概率计算器，必须先保留原文。
不要从展示符号或模型标签推导置信概率、真实心理状态或诊断结论。静音、短片段和噪声音频
不能提供可靠情感依据。`emotion2vec` 是另一类模型及接口，不是 SenseVoice 标签的别名。

本例显式选择 `language="auto"`、`use_itn=True`、`output_timestamp=False`，并非这些参数
都必填。SenseVoice 语言提示使用 `auto/zh/en/yue/ja/ko`。
`use_itn` 控制逆文本规范化，不是情感识别开关，显式 `text_norm` 的优先级更高。
每次调用重复传入需要固定的选项。本例是完整片段推理，不是 KWS 的 EOS 协议或实时情绪监控。

## VAD、说话人分离与服务边界

独立声纹提取和短片段 SenseVoice 推理不要求 VAD。通用 AutoModel 说话人聚类则位于
VAD 流水线中，只设置 `spk_model` 或 `return_spk_res=True` 不会给直接推理增加说话人分离。
VAD 边界不保证对应说话人切换；长音频分段也会改变情感标签所依据的上下文。
组合兼容的 ASR/VAD/标点/说话人模型时，遵循独立的
[SDK 流水线](python_api_zh.md#vad时间戳与说话人)。
`sentence_info[].spk` 是匿名编号，SDK `start/end` 单位为毫秒；
NumPy 聚类中心数组也需要像 Tensor 一样显式序列化。

第三方 OpenMOSS MOSS-Transcribe-Diarize 有自己的联合转写与分离路径，不需要外部
`vad_model` 或 `spk_model`。后端、显存和返回格式复用现有
[MOSS 指南](moss_transcribe_diarize_zh.md)，不要叠加第二套聚类或宣称已识别已知人员身份。

当前内置 [HTTP 转写服务](../examples/openai_api/README_zh.md) 的 SenseVoice 配置附带 VAD，
fallback 会剥离顶层及分段文本中的富标签，不会补建情感分数字段。
其 `spk=true` 属于服务自己的流水线，HTTP 分段 `start/end` 单位为秒。
把此 SDK 示例换成 `/v1/audio/transcriptions` 不代表仍能读取同样的标签或使用同样的参数。
请查阅[部署矩阵](deployment_matrix_zh.md)，不要假设 vLLM、llama.cpp、ONNX 或 WebSocket
导出路径都保留 Python 返回内容。

## 源码与验证

契约来源：[CAMPPlus](../funasr/models/campplus/model.py)、
[ERes2NetV2](../funasr/models/eres2net/model.py)、
[SenseVoice](../funasr/models/sense_voice/model.py)、
[后处理](../funasr/utils/postprocess_utils.py)、
[AutoModel](../funasr/auto/auto_model.py) 与 [HTTP 适配](../funasr/bin/_server_app.py)。
[指南测试](../tests/test_speaker_emotion_docs.py) 使用记录调用的 SDK 替身和真实展示函数执行
公开程序，验证字段保留、序列化和错误输入，不代表声学质量、身份匹配、不同人群表现或情感准确率评测。
