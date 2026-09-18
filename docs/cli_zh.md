<span id="command-line-interface"></span>

# 命令行接口

[English](cli.md) | [Python SDK](python_api_zh.md) | [模型选择](model_selection_zh.md)

使用 `funasr` 转写本地音频、保存结构化结果或生成字幕。本指南依据
[`funasr/cli.py`](../funasr/cli.py) 的参数解析器与格式化逻辑；这里的命令不是
HTTP 服务，也不是 Hydra CLI。

<span id="basic-usage"></span>

## 基本用法

用默认的 `sensevoice` 模型转写一个文件，或选择 CLI 支持的模型别名：

```bash
funasr audio.wav
funasr audio.wav --model paraformer
funasr audio.wav --device cpu
```

按任务继续阅读：[结构化 JSON](#json)、[多个文件](#advanced-examples)、
[字幕](#srt)或[说话人与热词](#speakers-and-hotwords)。
输入必须是已存在的本地文件。远程音频需先自行下载；CLI 的位置参数不接受音频 URL。

<span id="installation"></span>

## 安装与前提

在选定的 Python 环境中安装 FunASR，并按[安装指南](installation/installation_zh.md)
准备前提条件与模型所需的可选依赖。下列是使用命令，不代表全新环境安装验证：

```bash
python -m pip install funasr
funasr --help
funasr --version
```

首次使用可能下载所选模型以及 VAD、标点、说话人组件。需要可用的模型源访问权限
或完整缓存、足够内存，以及对应检查点要求的依赖。默认 `--hub ms` 使用 ModelScope，
`--hub hf` 选择 Hugging Face。PyTorch 报告 CUDA 可用时自动选择 `cuda:0`，否则选择
`cpu`；可用 `--device` 覆盖。这个可用性检查不保证显存充足或模型环境兼容。

<span id="output-formats"></span>

## 输出格式

<span id="text-default"></span>

### 纯文本（默认）

每个输入文件产生一份纯转写文本。模型的 `<|...|>` 富文本标签会被移除，因此它不是
情感或声音事件标签输出接口。

```bash
funasr audio.wav -f text -o ./transcripts
```

未指定 `-o` 时，CLI 将结果打印到标准输出。`--verbose` 将 CLI 的加载与计时信息写到
标准错误；模型或依赖仍可能向标准输出打印日志。需要独立结果载荷的自动化应使用输出文件。

<span id="json"></span>

### 结构化结果

```bash
funasr audio.wav --timestamps -f json -o ./results
jq '.text' ./results/audio.json
```

以下是**格式化器的示意测试数据**，不是实测识别结果、性能数据，也不保证每个模型都
返回这些可选字段：

```json
{
  "text": "Example.",
  "segments": [
    {"start": 0, "end": 1200, "text": "Example.", "timestamp": [[0, 1200]]}
  ],
  "timestamps": [[0, 1200]],
  "file": "audio.wav",
  "model": "sensevoice",
  "language": "auto",
  "audio_duration_s": 1.2,
  "processing_s": 0.01
}
```

| 字段 | 含义 |
|------|------|
| `text` | 清理标签后的识别文本。 |
| `segments` | 仅当非空 `sentence_info` 生成分段时包含。`start`/`end` 直接复制 SDK 值（句子契约使用毫秒），文本会清理标签。分段内 `timestamp` 可以为 null。 |
| `timestamps` | `--timestamps` 保留的可选顶层模型时间戳。CLI 不将其统一为通用词级结构。示例中的数值对数组使用毫秒；部分模型的字典时间戳表示可能使用秒。 |
| `file` | 输入文件名，不含完整路径。 |
| `model` | 所选 CLI 别名，不是不可变的检查点修订号。 |
| `language` | 用户传入的提示，省略时为 `auto`；不是检测出的语言。 |
| `audio_duration_s` | 音频元数据时长，单位为秒，保留三位小数；`soundfile.info` 无法读取时为 null。 |
| `processing_s` | 每个文件生成调用周围的耗时，单位为秒，保留三位小数。不含初次模型加载和输出格式化、写盘时间，不是端到端延迟。 |

`--timestamps` 只保留模型已经返回的时间戳，**不会请求对齐，也不保证词级时间戳**。
JSON 未指定该参数时省略顶层时间戳，但分段内部的时间戳仍可能存在。纯文本格式不显示
时间戳。模型相关的结果差异见 [SDK 输出契约](python_api_zh.md)。

<span id="advanced-examples"></span>

## 进阶用法

### 多个文件

```bash
funasr first.wav second.wav -f json -o ./results
funasr ./*.wav -f srt -o ./subs
```

模型只实例化一次，多个文件依次处理，每次生成使用 `batch_size=1`。通配符由 shell
展开，这不是并行批推理。输出文件名使用输入文件去掉扩展名后的名称，再加 `.txt`、
`.json`、`.srt` 或 `.tsv`；输出目录不存在时会创建。同名文件可能互相覆盖，也可能覆盖
上一次运行的结果，即使输入来自不同目录。

不指定 `-o` 时，多份 JSON 会作为独立的多行对象逐个打印，**不是 JSON 数组或 JSONL**。
遇到不存在的文件会以退出码 1 停止，之前写出的文件保留。CLI 没有断点续跑或事务式批处理选项。

<span id="srt"></span>

### 字幕

```bash
funasr audio.wav -f srt -o ./subs
funasr audio.wav -f srt --subtitle-segment-mode sentence -o ./raw-subs
```

SRT 使用 `HH:MM:SS,mmm` 时间格式。SRT 和 TSV 都向 SDK 请求
`sentence_timestamp`、`output_timestamp` 和 `return_time_stamps`。默认的 SenseVoice
字幕路径还会增加 `ct-punc`；结果仍取决于模型是否返回可用的 `sentence_info` 和时间信息。

默认 `readable` 模式会合并符合条件的相邻字幕：间隔不超过 500 毫秒，合并后时长不超过
8 秒，文字不超过 42 个字符，且不跨越已知的说话人变化。长字幕只有在已有时间戳能够
支持文本对齐时才会拆分。这些是分组目标，不能保证每条字幕都满足：无法对齐或不可再拆分
的文本可能超限。CLI 不会编造均匀分布的词级时间戳。`sentence` 模式保留模型原始句子边界。
JSON 和 TSV 不执行这种分组。

没有句子分段时，SRT 回退为单条字幕，先使用可用的时间戳范围，再尝试音频时长。
两者都不可用时，回退字幕可能是零时长；发布字幕前应检查时间信息。

<span id="tsv"></span>

### 表格

```bash
funasr audio.wav -f tsv -o ./tables
```

TSV 包含 `start`、`end`、`text` 三列，将句子起止时间从毫秒换算成秒，保留三位小数。
没有分段时仅输出一行文本，起止时间均为 `0.000`，不代表推导出的对齐时间。

<span id="speakers-and-hotwords"></span>

### 说话人与热词

```bash
funasr meeting.wav --model paraformer --spk --timestamps -f json -o ./meetings
funasr audio.wav --model paraformer --language zh --hotwords "FunASR,达摩院"
funasr audio.wav --hub hf --model fun-asr-nano
```

`--spk` 增加 `cam++` 说话人模型。仅当 SDK 的 `sentence_info` 中含 `spk` 时，JSON
分段才包含 `speaker`。这不是实名身份识别，也不保证所有模型组合都能进行说话人分离。
SRT 分组会遵守已有的说话人边界，但 CLI 的纯文本、SRT、TSV 格式化器不输出说话人标签。

热词使用逗号分隔，去除前后空白并丢弃空项。`paraformer` 别名向 SDK 传入以空格连接的
`hotword` 字符串；其他别名传入 `hotwords` 列表。是否生效取决于模型，而不只是解析器
接受了该参数。`--language` 也属于模型相关提示：解析器接受任意字符串，不校验模型语言覆盖。

## 使用边界

- 这是本地文件 SDK 包装命令，不是流式推理、网络服务或原生 vLLM 服务。其他路径见
  [部署矩阵](deployment_matrix_zh.md)。
- 下表的四个别名就是 `--model` 的全部选项。不能在这里传任意模型源 ID、本地模型目录
  或后端选择参数。
- `moss-transcribe-diarize` **不是 CLI 模型选项**。请按 [MOSS 指南](moss_transcribe_diarize_zh.md)
  使用独立的 `AutoModel` 适配器或 `funasr-server` 路径，并遵守其依赖与限制；不要将它传给 `--model`。
- 模型加载先于逐文件存在性检查，错误输入也可能触发加载或下载。推理或依赖异常不会被
  转成稳定的 JSON 错误对象。
- 速度、内存、语言覆盖、对齐和说话人质量依赖检查点、硬件、环境和音频。本指南不作速度
  或生产容量承诺。

<span id="options"></span>

## 参数参考

`audio` 为一个或多个本地文件路径。下表 `None` 是解析器的真实默认值，不是应在命令行输入的字符串。

| 参数 | 短参数 | 解析器默认值 | 含义 / 可选值 |
|------|--------|--------------|---------------|
| `--model` | `-m` | `sensevoice` | `sensevoice`、`paraformer`、`paraformer-en`、`fun-asr-nano`。 |
| `--hub` | `-H` | `ms` | `ms`（ModelScope）或 `hf`（Hugging Face）。 |
| `--language` | `-l` | `None` | 省略时不向模型传语言参数。`zh`、`en`、`ja`、`ko`、`yue`、`auto` 等显式提示是否支持取决于模型。 |
| `--device` | | `None` | CUDA 可用时自动选择 `cuda:0`，否则 `cpu`；显式设备字符串覆盖自动选择。 |
| `--output-format` | `-f` | `text` | `text`、`json`、`srt`、`tsv`。 |
| `--subtitle-segment-mode` | | `readable` | `readable` 或 `sentence`，仅影响 SRT。 |
| `--output-dir` | `-o` | `None` | 省略时输出到 stdout，否则按输入文件分别写到指定目录。 |
| `--timestamps` | | `False` | 保留已有顶层时间戳，不请求对齐。 |
| `--spk` | | `False` | 增加说话人模型，JSON 说话人字段取决于 SDK 返回结果。 |
| `--hotwords` | | `None` | 逗号分隔的提示词，按模型别名转发。 |
| `--verbose` | `-v` | `False` | 将 CLI 加载和计时信息写到 stderr。 |
| `--version` | | 不适用 | 打印已安装的 FunASR 包版本并退出，不是模型修订号。 |
| `--help` | `-h` | 不适用 | 打印解析器帮助并退出。 |

<span id="models"></span>

## 模型别名

| CLI 别名 | ASR 模型映射 | 范围 |
|----------|--------------|------|
| `sensevoice` | `iic/SenseVoiceSmall` | 中文、英语、日语、韩语、粤语；CLI 文本移除富文本标签。 |
| `paraformer` | `paraformer-zh` | 中文识别，带 VAD 和标点。 |
| `paraformer-en` | `paraformer-en` | 英语识别，CLI 还会增加标点模型。 |
| `fun-asr-nano` | `FunAudioLLM/Fun-ASR-Nano-2512` | 中文、英语、日语及中文方言/口音；需要额外模型依赖。 |

四种配置均包含 `fsmn-vad`；说话人和标点组件按上文选项逻辑添加。这些映射没有固定模型源
修订号。`fun-asr-nano` 别名不选择独立的 Fun-ASR-MLT-Nano 检查点。
其他检查点请使用 [Python SDK](python_api_zh.md)并参考[模型选择指南](model_selection_zh.md)。

<span id="legacy-cli"></span>

## 旧版 CLI

原有的 Hydra 入口仍为 `funasr-hydra`：

```bash
funasr-hydra ++model=paraformer-zh ++input=audio.wav
```

其 `++key=value` 配置与本指南的 argparse 参数分属两套语法，不要混用。
