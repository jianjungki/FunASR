简体中文 | [English](keyword_spotting.md)

# 关键词检测

使用 KWS 检查点判断一句音频中是否出现配置的关键词。本任务不输出通用转写、
说话人身份或唤醒词时间戳。**当前 SANM 流式 Python 接口在一句音频结束时返回结果，
不是每收到一个音频包就产生唤醒事件。**

## 选择对应路径

| 任务 | 指南 |
| --- | --- |
| 检测完整录音中的关键词 | [FSMN KWS 示例](../examples/industrial_data_pretraining/fsmn_kws) |
| 按顺序输入音频包，句末检测 | 下方 SANM 示例 |
| 连续转写一般语音 | [流式 ASR SDK](python_api_zh.md#流式-cache-生命周期) |
| 定位语音活动 | [流式 VAD](streaming_vad_zh.md) |

FSMN 使用对应检查点的 tokenizer 和关键词词表，不要套用流式 SANM 的缓存参数。
下方 SANM 示例使用在线检查点和关键词 `小云小云`。
ASR 文本及热词不是 KWS 检测器；VAD 检测语音边界，不判断关键词是否出现。

修改 `keywords` 是配置解码候选，不是为任意短语或语言训练新模型。
应使用检查点支持的 token，阅读模型卡与许可证，并用目标音频评测每个关键词。
参数使用非空字符串，多个关键词以英文逗号分隔，不是 Python 列表或 ASR 的
`hotword` 参数。结果不保证列出所有关键词的每次出现。离线 FSMN 示例使用
`iic/speech_charctc_kws_phone-xiaoyun`，不要自行改成不存在的 `fsmn-kws` 别名。
其他架构请查阅 [Model Zoo](../model_zoo/readme_zh.md) 和对应训练示例，不要假定接口通用。

## 固定源码版本

此示例要求包含 [#3655](https://github.com/modelscope/FunASR/pull/3655) 和
[#3656](https://github.com/modelscope/FunASR/pull/3656) 的修复。
**PyPI `funasr==1.4.14` 尚未包含这些修复。** 完成
[环境检查](installation/installation_zh.md) 后，在隔离环境中安装已测试的确切源码：

```sh
python -m pip uninstall -y funasr
python -m pip install "funasr @ git+https://github.com/modelscope/FunASR.git@403555289a6d4f79f5c4a48e5beb00f521c5e172"
```

先卸载是为了替换已安装的同版本旧包；只指定 Git 地址或增加 `--upgrade`
仍可能保留旧包。请在隔离环境运行，不要直接修改共享生产工作进程的环境。

源码安装仍可能显示包版本 `1.4.14`，因此必须同时记录 Git commit 和实际导入模块路径。
只有明确包含这两项修复的后续发布才能用对应 wheel 替代。本指南不代表发布了新 PyPI 包。

准备 `iic/speech_sanm_kws_phone-xiaoyun-commands-online` 的完整本地快照，
包括配置、tokenizer、前端/CMVN 文件和权重。记录解析后的版本或文件校验清单；
可变的 `master` 标签不等于不可变版本。音频使用非空、单声道、16 kHz WAV。
示例内部不下载模型。
外部数组应为归一化的一维 `float32` 波形，而非整数 PCM。
先对完整信号统一采样率再切包；逐包独立重采样不在连续性保证范围内。

## 运行文件或顺序音频包

程序接收 `model_dir`、`audio` 和可选的 `--mode file`，默认模式为 `stream`。
流式模式先读取完整 WAV，再模拟每包 960 个采样点；不是麦克风采集程序，
整段文件仍保留在内存中。`detect_stream` 是应用侧辅助函数，不是新的 SDK 方法。

```python
import argparse
from pathlib import Path
import soundfile as sf
from funasr import AutoModel


def detect_stream(model, speech, sample_rate, packet_samples=960):
    if packet_samples <= 0 or len(speech) == 0:
        raise ValueError("Audio length and packet size must be positive")
    cache = {}
    final_results = []
    for start in range(0, len(speech), packet_samples):
        end = min(start + packet_samples, len(speech))
        final_results = model.generate(
            input=speech[start:end], fs=sample_rate, cache=cache,
            chunk_size=[4, 8, 4], batch_size=1, is_final=end == len(speech),
        )
    return final_results


parser = argparse.ArgumentParser()
parser.add_argument("model_dir")
parser.add_argument("audio")
parser.add_argument("--mode", choices=["file", "stream"], default="stream")
args = parser.parse_args()
model_dir = Path(args.model_dir).expanduser().resolve(strict=True)
if not model_dir.is_dir():
    raise ValueError("Expected a complete local SANM KWS model directory")
speech, sample_rate = sf.read(args.audio, dtype="float32")
if sample_rate != 16000 or speech.ndim != 1 or len(speech) == 0:
    raise ValueError("Expected nonempty mono 16 kHz audio")

model = AutoModel(
    model=str(model_dir), keywords="小云小云", device="cpu", ncpu=1,
    chunk_size=[4, 8, 4], encoder_chunk_look_back=0,
    decoder_chunk_look_back=0, disable_update=True, trust_remote_code=False,
)
if args.mode == "file":
    results = model.generate(
        input=args.audio, fs=sample_rate, cache={}, chunk_size=[4, 8, 4],
        batch_size=1, is_final=True,
    )
else:
    results = detect_stream(model, speech, sample_rate)
for item in results:
    print(item["text"])
```

## 结果与会话管理

- 非末包调用公开的 `AutoModel.generate` 返回 `[]`，含义是尚无最终结果，
  不是关键词被拒绝。最终结果包含 `key` 和 `text`，文本为
  `detected <keyword> <score>` 或 `rejected`。分数不是校准后的概率或通用阈值，
  结果中没有关键词时间区间或说话人身份。
  若整句音频都没有有效特征帧，最终结果也可能为 `[]`；没有结果不等于检测拒绝。
  空 EOS 仍会解码此前音频包已经累计的输出。
- `chunk_size=[4, 8, 4]` 指左侧、当前、右侧的**前端特征帧数**，
  不是毫秒或调用者的音频包长。16 kHz 下 960 个采样点等于 60 ms；
  这是输入包时长，不是实测唤醒延迟。会话内固定模型、关键词、分块设置和采样率。
- 同一句音频的有序调用共用同一个字典，使用 `batch_size=1`。
  新录音或取消会话后创建新缓存。独立缓存不代表同一个 `AutoModel` 可以线程安全地
  并发调用；应串行调用或隔离模型工作进程。
- 本例最后一个非空包携带 `is_final=True`，整包倍数长度也一样。
  固定版本的 SANM 修复也支持：先输入非末包音频，再用一次空**数组**末包刷新状态。
  不要重发已消费音频，不要在终结后追加第二次 EOS，也不要将此行为推广到其他模型。
  文件/URL 输入会按完整一句自动终结，不能重复传文件路径来模拟连续音频包。
- 终结会原地重置模型缓存字段，不保证字典变空。应用侧仍应在会话边界丢弃状态。
  编码输出会一直积累到 EOS，必须明确限制句长，不能无限保持常开会话。
  使用 VAD 或超时来划分句子是应用策略，会改变检测器接收到的音频。
- 现在省略 `output_dir` 可直接返回结果，不创建结果写入器。如需文件，
  显式配置可写的 `output_dir`；结果文件是可选项，多次调用可能追加写入。
  文件不是推理前提，也不是唤醒事件分发系统。

## 验证证据与部署边界

源码修复已在 CPU 上使用官方检查点、一条官方正样本和合成静音验证。
在单线程、前端 `dither=0` 的条件下，完整文件、完整数组、960 点分包、
不规则分包加空 EOS 的正样本最终编码帧一致。修复前后均检出了关键词，静音均被拒绝。
这只是连续性回归验证，**不是**准确率提升、自然负样本误唤醒率评测，
也不是麦克风或 GPU 验证。上方示例保留检查点前端配置；逐位一致性比较
需要使用该验证记录中的相同确定性设置。

此 Python 示例不能证明转写 HTTP 服务、原生 vLLM、llama.cpp 或 C++ WebSocket
协议已支持 KWS。构建服务前查阅独立的[部署矩阵](deployment_matrix_zh.md)与
对应运行时模型契约，不要把 KWS 结果字符串当成 OpenAI 转写文本，
也不要宣传实现尚未输出的即时唤醒事件。

报告问题时保留原音频、模型文件清单、源码 commit、分包长度与顺序、末包标志和
结果字符串。宣称部署准确率前，应包含自然负样本、误唤醒与漏检评测方法。
不要公开密钥或私人音频。

源码契约：[流式实现](../funasr/models/sanm_kws_streaming/model.py)、
[可选输出测试](../tests/test_kws_optional_output.py)、
[连续性测试](../tests/test_kws_streaming_continuity.py)、
[指南可运行测试](../tests/test_kws_docs.py)。指南测试使用记录调用的 SDK 替身
执行完整示例入口，不加载模型权重。
