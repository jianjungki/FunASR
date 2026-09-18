# 训练与适配

[English](training.md) | [文档](tutorial/README_zh.md) | [模型注册](model_registration_zh.md) | [模型选择](model_selection.md)

本指南把仓库中的训练脚本与数据集、训练器实现对应起来。命令默认从仓库根目录执行，环境需安装当前 checkout 及所选 recipe 的依赖。命令是针对自有数据和已审查模型资产的模板，不表示已验证完整训练、收敛、显存需求或导出。

## 先确定任务

| 任务 | 改变什么 | 入口 |
| --- | --- | --- |
| 推理 | 不修改权重，识别已有音频 | [推理教程](tutorial/README_zh.md) |
| 适配 | 从预训练权重开始，微调部分参数、全部参数或受支持的 LoRA 适配器 | 下表中的 recipe；先记录独立留出集基线 |
| 从头训练 | 不加载预训练权重，准备架构配置、分词器、特征及训练计划 | [AISHELL Paraformer 脚本](../examples/aishell/paraformer/demo_train_or_finetune.sh)及其[配置](../examples/aishell/paraformer/conf/paraformer_conformer_12e_6d_2048_256.yaml) |

全参数微调不等于从头训练。历史 AISHELL 脚本包含作者本机路径，且传入了 `init_param`；必须替换路径并明确配置初始化方式，才能用于从头训练。目录名 `industrial_data_pretraining` 不表示公开脚本可复现原始工业预训练数据和流程。

| 模型系列 | 实际 recipe 与说明 | 使用边界 |
| --- | --- | --- |
| SenseVoice | [finetune.sh](../examples/industrial_data_pretraining/sense_voice/finetune.sh)、[中文说明](../examples/industrial_data_pretraining/sense_voice/README_zh.md)、[持续适配](../examples/industrial_data_pretraining/sense_voice/CONTINUAL_FINETUNING_zh.md) | 需要正确的富标签与特殊 token。脚本使用用户准备的 `data/train_example.jsonl`、`data/val_example.jsonl`，不会自动创建这些文件。 |
| FunASRNano | [finetune.sh](../examples/industrial_data_pretraining/fun_asr_nano/finetune.sh)、[LoRA 脚本](../examples/industrial_data_pretraining/fun_asr_nano/lora_finetune.sh)、[微调指南](../examples/industrial_data_pretraining/fun_asr_nano/docs/finetune_zh.md) | 默认冻结音频编码器和适配模块、解冻 LLM，并非全参数方案。纯 LoRA 另设 `llm_conf.use_lora=true`、`lora_only=true`、`llm_conf.freeze=true`。应检查实际可训练参数，包括可能存在的 CTC 组件。 |
| Paraformer | [finetune.sh](../examples/industrial_data_pretraining/paraformer/finetune.sh)、[中文说明](../examples/industrial_data_pretraining/paraformer/README_zh.md)、[LoRA 指南](../examples/industrial_data_pretraining/paraformer/README_LoRA_zh.md) | 工业数据微调脚本显式使用 `AudioDataset` / `IndexDSJsonl`。Paraformer LoRA 是独立 recipe，不能套用 Nano 的适配器配置。 |
| MOSS-Transcribe-Diarize | [FunASR 适配器源码](../funasr/models/moss_transcribe_diarize/model.py) | 属于第三方 OpenMOSS 模型。该适配器的 `forward` 明确抛出仅支持推理的异常；本指南不覆盖 MOSS 训练。 |

FunASR 软件采用 MIT 许可证；模型权重、上游代码、数据集和派生 checkpoint 可能采用不同条款。训练、分发前请检查各项许可和数据授权。

## 准备数据

训练集、验证集和最终测试集应分开，尽量按说话人、录音会话划分，而非只按句子划分。检查重复 ID、音频与文本 ID 对齐、文件可读性、解码后的时长与采样率、文本规整方式及语言覆盖。音频相对路径按进程工作目录解析，不会自动按 JSONL 所在目录解析。需要可复现或隐私保护时优先使用稳定的本地音频路径。

### Paraformer：音频与文本 JSONL

[转换器](../funasr/datasets/audio_datasets/scp2jsonl.py)按 utterance ID 合并 SCP 和文本；输入每行是 `utterance_id value`，文本可以包含空格。以下为两秒音频的结构示例：

```json
{"key":"utt001","source":"data/audio/utt001.wav","source_len":200,"target":"hello world","target_len":2}
```

`key`、`source`、`target` 是字符串，长度字段是整数。`source_len` 为 `int(16kHz采样点数 / 160)`，约为 10 ms 单位，不是秒。转换器对有空格的文本按空格统计词数，否则统计字符数，得到 `target_len`；它并不统一等于分词器 token 数。[索引读取器](../funasr/datasets/audio_datasets/index_ds.py)按配置的长度限制过滤数据，[数据集](../funasr/datasets/audio_datasets/datasets.py)再执行特征提取和分词。

准备 `data/list/train_wav.scp`、`train_text.txt`、`val_wav.scp`、`val_text.txt`，从仓库根目录执行：

```bash
python -m funasr.datasets.audio_datasets.scp2jsonl \
  ++scp_file_list='["data/list/train_wav.scp", "data/list/train_text.txt"]' \
  ++data_type_list='["source", "target"]' \
  ++jsonl_file_out=data/list/train.jsonl
python -m funasr.datasets.audio_datasets.scp2jsonl \
  ++scp_file_list='["data/list/val_wav.scp", "data/list/val_text.txt"]' \
  ++data_type_list='["source", "target"]' \
  ++jsonl_file_out=data/list/val.jsonl
```

转换器可能跳过缺失音频，或在缺少文本时输出不完整记录。必须比较输入输出数量并拒绝不完整行，不能只看进程退出状态。CLI 配置应来自可信来源：该历史转换器对字符串列表存在 `eval` 回退分支。

### SenseVoice：保留富标签

使用 `SenseVoiceCTCDataset` 时，在音频文本结构上增加明确的监督字段：

```json
{"key":"utt001","source":"data/audio/utt001.wav","source_len":200,"target":"你好","target_len":2,"text_language":"<|zh|>","emo_target":"<|NEUTRAL|>","event_target":"<|Speech|>","with_or_wo_itn":"<|woitn|>"}
```

标签必须对应实际录音，不能不加区分地填入示例值。[CTC 数据集源码](../funasr/datasets/sense_voice_datasets/datasets.py)在缺字段时使用上例默认值，但默认值不是经过验证的标注。旧版 `SenseVoiceDataset` 是另一种实现，应保持数据集类与所选模型配置一致。

[sensevoice2jsonl.py](../funasr/datasets/audio_datasets/sensevoice2jsonl.py)通过 `scp_file_list`、`data_type_list` 接收对齐的音频、文本、语言、情感、事件文件。如果缺少语言、情感或事件标签，它会调用 SenseVoice 生成伪标签，可能下载并运行模型；ITN 标志由标点启发式生成。训练前需审核标签与规整规则。增加新语言标签不是改一个字符串，需要分词器与模型协同修改，参见[持续微调指南](../examples/industrial_data_pretraining/sense_voice/CONTINUAL_FINETUNING_zh.md)。

### FunASRNano：ChatML JSONL

Nano 提供的 recipe 不使用普通 Paraformer 数据结构。实际文件见[训练示例](../examples/industrial_data_pretraining/fun_asr_nano/data/train_example.jsonl)和[验证示例](../examples/industrial_data_pretraining/fun_asr_nano/data/val_example.jsonl)。下面仅展示结构，真实数据必须重新计算长度：

```json
{"messages":[{"role":"system","content":"You are a helpful assistant."},{"role":"user","content":"语音转写：<|startofspeech|>!data/audio/utt001.wav<|endofspeech|>"},{"role":"assistant","content":"你好"}],"speech_length":198,"text_length":1}
```

`messages` 是 role/content 字典列表；assistant 内容为参考转写。[recipe 转换器](../examples/industrial_data_pretraining/fun_asr_nano/tools/scp2jsonl.py)按行配对 SCP 和文本并要求 ID 一致，计算 `speech_length = int((duration * 1000 - 25) // 10 + 1)`，用 `Qwen/Qwen3-0.6B` 分词得到 `text_length`。可能下载分词器或 URL 音频。行数不一致只会产生警告，错误样本可能被省略，必须核对输出数量和全部错误。

使用自己的输入输出文件，不要覆盖仓库示例：

```bash
python examples/industrial_data_pretraining/fun_asr_nano/tools/scp2jsonl.py \
  ++scp_file=data/list/train_wav.scp \
  ++transcript_file=data/list/train_text.txt \
  ++jsonl_file=data/list/nano_train.jsonl
python examples/industrial_data_pretraining/fun_asr_nano/tools/scp2jsonl.py \
  ++scp_file=data/list/val_wav.scp \
  ++transcript_file=data/list/val_text.txt \
  ++jsonl_file=data/list/nano_val.jsonl
```

## 先做小规模验证

1. 固定 checkout 与模型资产，记录依赖、分词器与前端配置、GPU 配置、数据哈希和随机种子。启用 `trust_remote_code` 前审核下载的 Python 与 requirements。
2. 用已验证样本准备小而互不重叠的 `data/list/train_smoke.jsonl`、`data/list/val_smoke.jsonl`，实际加载音频、分词，确认长度过滤后仍有非空 batch、loss 有限、可训练参数符合预期。
3. 扩大规模前先完成短训练、验证和 checkpoint 保存流程。不要直接运行历史 shell 脚本：其内部设置 GPU、输出目录和依赖工作目录的路径，通常不会透传附加在脚本末尾的 CLI 参数。

以下是从工业数据 recipe 提炼的 Paraformer 小规模验证模板，路径以仓库根目录为基准。需要兼容 GPU、已安装训练依赖、上述两个 JSONL 文件，以及位于 `models/paraformer` 的完整且已审查模型目录。`2000` 是用于短音频的起始 token 预算，不是显存保证；调整时仍须确保单条样本能容纳。只有数据集足够小，一个 epoch 才是小规模运行。

```bash
CUDA_VISIBLE_DEVICES=0 torchrun --nnodes=1 --nproc_per_node=1 \
  --master_addr=127.0.0.1 --master_port=29619 \
  funasr/bin/train_ds.py \
  ++model=./models/paraformer \
  ++train_data_set_list=data/list/train_smoke.jsonl \
  ++valid_data_set_list=data/list/val_smoke.jsonl \
  ++dataset=AudioDataset ++dataset_conf.index_ds=IndexDSJsonl \
  ++dataset_conf.data_split_num=1 ++dataset_conf.batch_sampler=BatchSampler \
  ++dataset_conf.batch_type=token ++dataset_conf.batch_size=2000 \
  ++dataset_conf.sort_size=16 ++dataset_conf.num_workers=0 \
  ++train_conf.max_epoch=1 ++train_conf.log_interval=1 \
  ++train_conf.resume=false ++train_conf.use_deepspeed=false \
  ++train_conf.validate_interval=1 ++train_conf.save_checkpoint_interval=1 \
  ++train_conf.keep_nbest_models=1 ++train_conf.avg_nbest_model=1 \
  ++optim_conf.lr=0.0002 ++output_dir=./outputs/paraformer-smoke
```

每次新实验使用新输出目录，并选用空闲 rendezvous 端口。SenseVoice、Nano 应从各自 recipe、模型配置和数据结构出发，不能只替换上例的模型名而保留 `AudioDataset`。Nano 脚本通过 `PATH` 找到 `funasr-train-ds`，请确认它属于预期安装。SenseVoice、Paraformer 脚本在 `use_deepspeed=false` 时也传入 DeepSpeed 配置路径；启用前必须确认真实配置存在。完整分布式训练和资源需求仍需单独验证。

## Checkpoint 与恢复

[训练入口](../funasr/bin/train_ds.py)调用 [Trainer.resume_checkpoint](../funasr/train_utils/trainer_ds.py)。非 DeepSpeed 分支中，`++train_conf.resume=true` 从 `output_dir/model.pt` 恢复模型、优化器、调度器及存在的 scaler/训练进度状态。这是布尔开关，不是任意 checkpoint 路径。文件不存在时训练器会提示未恢复并继续，必须检查日志确认实际恢复成功。

继续上面的 smoke run 时，保持输出目录和配置，改为 `++train_conf.resume=true`、`++train_conf.max_epoch=2` 后重新执行。epoch 上限是总轮数，不是新增轮数。`++init_param=...` 仅用于初始化权重，不恢复优化器和进度。新适配阶段应使用新输出目录、`resume=false` 和明确选定的初始化权重。

非 DeepSpeed 保存包括 `model.pt`、`model.pt.ep{epoch}` 或 `model.pt.ep{epoch}.{step}`，`model.pt.best` 取决于验证排序。DeepSpeed 使用目录/tag，需要对应恢复或转换流程。不要把这些目录、不完整状态或仅适配器状态当成普通独立权重。保留配置、分词器、前端资产和基座模型来源，检查保存排除项与 LoRA 配置。单个 checkpoint 文件不一定是可加载的模型目录。

## 评估与导出

使用准备好的 Paraformer 模型目录及真实 checkpoint，先检查单条音频：

```python
from pathlib import Path
from funasr import AutoModel

checkpoint = Path("outputs/paraformer-smoke/model.pt")
assert checkpoint.is_file(), checkpoint
model = AutoModel(
    model="./models/paraformer",
    hub="ms",
    init_param=str(checkpoint),
    device="cpu",
    disable_update=True,
)
print(model.generate(input="data/audio/heldout.wav"))
```

随后在未参与训练或选模的留出集上解码，基线与适配模型使用一致的规整方式及 CER/WER 单位定义。报告各领域、各语言和整体结果、原任务退化、样本数量与 checkpoint 身份。训练 loss 或训练器验证 accuracy 不自动等于转写 CER/WER。[Nano 微调指南](../examples/industrial_data_pretraining/fun_asr_nano/docs/finetune_zh.md)保留了解码、规整、评分入口；[decode.py](../examples/industrial_data_pretraining/fun_asr_nano/decode.py)使用 VAD 和 `remote_code="./model.py"`，需要 recipe 工作目录。该[历史本地类](../examples/industrial_data_pretraining/fun_asr_nano/model.py)可能覆盖[内置 Nano 类](../funasr/models/fun_asr_nano/model.py)，不能假定它保留内置 LoRA 功能；评估前确认实际类、适配器注入和权重加载结果。

导出是单独的兼容性验证任务。[SenseVoice ONNX 示例](../examples/industrial_data_pretraining/sense_voice/export.py)、[Paraformer 导出示例](../examples/industrial_data_pretraining/paraformer/export.py)及[导出工具](../funasr/utils/export_utils.py)只是入口，不承诺所有模型均支持。Paraformer 示例实际选择 contextual checkpoint，必须检查并明确替换为自己的模型。模型导出 hook、分词器、前端、动态形状和运行时解码都需要验证。部署前在留出输入上比较导出运行时与 Python 输出。本次文档修改未运行完整训练、质量基准、真实 checkpoint 恢复、模型下载或模型导出。
