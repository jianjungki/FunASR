简体中文 | [English](streaming_vad.md)

# 流式语音活动检测

使用 FSMN VAD，按顺序输入同一条录音的音频块，接收语音起点与终点事件。
VAD 不负责转写、说话人身份识别或语言学断句。首次离线 VAD 调用见
[SDK 教程](tutorial/README_zh.md)；流式 ASR 请使用独立的
[Paraformer 缓存示例](python_api_zh.md)，不要混用两者的协议。

## 准备模型与音频

先完成[安装检查](installation/installation_zh.md)，准备
`iic/speech_fsmn_vad_zh-cn-16k-common-pytorch` 的完整本地快照，
包括配置、前端文件与权重，记录实际模型 revision 并阅读模型自己的许可证。
本例针对该 16 kHz 检查点，不适用于任意 VAD 或流式 ASR 模型。

输入必须为非空、单声道、16 kHz WAV。下方完整程序的两个命令行位置参数
依次是本地模型目录和音频路径。它一次读取文件，再模拟按序到达的音频块；
不是麦克风采集或 WebSocket 服务，整段文件仍会占用内存。

## 理解边界事件

返回的每个字典包含 `value` 列表。每一对边界的单位都是**毫秒**，
相对于**本条流的起点**，不是当前音频块的起点，不要再叠加块偏移量。

| 事件 | 含义 |
| --- | --- |
| `[]` | 没有新边界；之前的语音段仍可能未结束。 |
| `[[start, -1]]` | 检测到起点，保存它，等待后续调用给出终点。 |
| `[[-1, end]]` | 之前开始的语音段结束。 |
| `[[start, end]]` | 本次已经获得完整起止边界。 |

一次调用可以返回多对边界。`-1` 是缺少边界的标记，不能拿它直接切音频。
每条流独立保存待配对的起点。下面的严格示例遇到异常事件顺序会报错，
不会凭空补起点或悄悄覆盖尚未结束的语音段。

## 按序输入音频块

两个辅助函数属于应用示例，不是新增的 FunASR API。将 `is_final=True`
放在最后一个**非空**音频块上；音频长度恰好整除块长度时也遵守这一规则。

```python
import argparse
from pathlib import Path
import soundfile as sf
from funasr import AutoModel


def chunk_ranges(length, stride):
    if length <= 0 or stride <= 0:
        raise ValueError("Audio length and chunk stride must be positive")
    for start in range(0, length, stride):
        end = min(start + stride, length)
        yield start, end, end == length


def consume_events(events, pending_start):
    spans = []
    for start_ms, end_ms in events:
        if start_ms < 0 and end_ms < 0:
            raise ValueError("An event must provide a boundary")
        if start_ms >= 0:
            if pending_start is not None:
                raise ValueError("New start before the previous speech span ended")
            pending_start = start_ms
        if end_ms >= 0:
            if pending_start is None or end_ms < pending_start:
                raise ValueError("End without a matching earlier start")
            spans.append((pending_start, end_ms))
            pending_start = None
    return pending_start, spans


parser = argparse.ArgumentParser()
parser.add_argument("model_dir")
parser.add_argument("audio")
args = parser.parse_args()
model_dir = Path(args.model_dir).expanduser().resolve(strict=True)
if not model_dir.is_dir():
    raise ValueError("Expected a complete local FSMN VAD model directory")
speech, sample_rate = sf.read(args.audio, dtype="float32")
if sample_rate != 16000 or speech.ndim != 1 or len(speech) == 0:
    raise ValueError("Expected nonempty mono 16 kHz audio")

model = AutoModel(
    model=str(model_dir), device="cpu", ncpu=4,
    disable_update=True, trust_remote_code=False,
)
chunk_ms = 200
stride = sample_rate * chunk_ms // 1000
cache = {}
pending_start = None
for start, end, final in chunk_ranges(len(speech), stride):
    results = model.generate(
        input=speech[start:end], fs=sample_rate, cache=cache,
        chunk_size=chunk_ms, is_streaming_input=True, is_final=final,
        batch_size=1, dynamic_silence=False,
    )
    for item in results:
        pending_start, spans = consume_events(item.get("value", []), pending_start)
        for start_ms, end_ms in spans:
            print(start_ms, end_ms)
if pending_start is not None:
    print("Unclosed speech start (ms):", pending_start)
# End this session; never share its cache with another recording.
cache = {}
```

16 kHz 下，`chunk_size=200` 代表 200 毫秒，即 3200 个输入采样点。
FSMN VAD 的这个参数是单个时长数值，不是 Paraformer 流式模型的三元素列表。
同一条流保持同一个缓存字典和固定块设置，使用 `batch_size=1`。
不同录音、用户或取消后的新会话必须使用新缓存。当前实现会在非空最终调用后
重新初始化缓存；应用结束会话时仍应丢弃旧缓存。

不要另加一次空输入来刷新本例的尾部：[当前推理实现](../funasr/models/fsmn_vad_streaming/model.py)
会在空输入时提前返回，尚未走到正常的收尾路径。实时输入若事先不知道何时结束，
可保留最新一个非空块。下一个块到达时，以 `is_final=False` 发送保留块，
再保留新到达的块；只有收到结束信号时，才以 `is_final=True` 发送保留块。
这种方式增加一个输入块的缓冲延迟，不能重复发送已经消费过的音频块。
如果是取消会话，则丢弃保留的音频和缓存。

## 测量之后再调参

本例显式设置 `is_streaming_input=True`，避免流式模式默认值随
`chunk_size` 改变。同时设置 `dynamic_silence=False`，使用检查点或配置的
结束静音设置，而不是当前的动态策略。这是便于复现的选择，不是推荐阈值，
也不保证检测延迟。调参前检查 `max_end_silence_time`、
`max_single_segment_time` 和模型配置，它们的时长单位都是毫秒。
音频块时长不等于整体检测延迟，也不代表音素边界精度。

排查截断问题时保留原始边界事件、模型与 SDK revision、配置及原音频。
边界缺失或偏晚，不代表给所有段全局增加 padding 就能解决。
最终仍有未闭合起点时应报告这一状态，不要擅自把录音长度当作终点。

## SDK 与部署边界

- 本例只产生语音边界，不输出转写或字幕。组合 VAD、ASR、标点和说话人时，
  应遵循另外的 [SDK 流水线契约](python_api_zh.md)。
- Python 缓存事件不是 C++ 服务网络协议；连接对应服务请看
  [WebSocket 协议](../runtime/docs/websocket_protocol_zh.md)。
- 第三方 OpenMOSS 的 [MOSS-Transcribe-Diarize](moss_transcribe_diarize_zh.md)
  有自己的联合转写与说话人分离路径，不要假定它必须增加本例的外部 VAD。
- 实现依据：[原始示例](../examples/industrial_data_pretraining/fsmn_vad_streaming/demo.py)、
  [模型源码](../funasr/models/fsmn_vad_streaming/model.py)、
  [缓冲测试](../tests/test_fsmn_vad_streaming_buffers.py)、
  [动态静音测试](../tests/test_dynamic_streaming_vad.py)。
  [本文示例测试](../tests/test_streaming_vad_docs.py) 无需下载权重，只执行分块计算
  和事件配对；不构成声学准确率、实时麦克风或部署性能测试。
