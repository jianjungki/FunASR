# Training and Adaptation

[简体中文](training_zh.md) | [Documentation](tutorial/README.md) | [Model registration](model_registration.md) | [Model selection](model_selection.md)

This guide connects the checked-in recipes to their dataset and trainer implementations. Commands assume the repository root and an environment with this checkout and the selected recipe's dependencies installed. They are templates for your own data and reviewed model assets, not evidence that full training, convergence, GPU memory use, or export has been tested.

## Choose the Work

| Work | What changes | Starting point |
| --- | --- | --- |
| Inference | No weights change; decode existing audio | [Inference tutorial](tutorial/README.md) |
| Adaptation | Fine-tune selected parameters, all parameters, or supported LoRA adapters from pretrained weights | Recipes below; first record a held-out baseline |
| Training from scratch | Initialize a configured architecture without pretrained weights; prepare tokenizer, features and training schedule | [AISHELL Paraformer recipe](../examples/aishell/paraformer/demo_train_or_finetune.sh) and its [configuration](../examples/aishell/paraformer/conf/paraformer_conformer_12e_6d_2048_256.yaml) |

Full-parameter fine-tuning is not training from scratch. The historical AISHELL script contains author-local paths and supplies `init_param`; replace its paths and deliberately configure initialization before using it for a scratch run. A script under `industrial_data_pretraining` does not reproduce the original industrial pretraining corpus or procedure.

| Family | Real recipe and companion material | Important boundary |
| --- | --- | --- |
| SenseVoice | [finetune.sh](../examples/industrial_data_pretraining/sense_voice/finetune.sh), [English README](../examples/industrial_data_pretraining/sense_voice/README.md), [continual adaptation](../examples/industrial_data_pretraining/sense_voice/CONTINUAL_FINETUNING.md) | Rich labels and tokenizer special tokens matter. The script expects user-prepared `data/train_example.jsonl` and `data/val_example.jsonl`; it does not create them. |
| FunASRNano | [finetune.sh](../examples/industrial_data_pretraining/fun_asr_nano/finetune.sh), [LoRA script](../examples/industrial_data_pretraining/fun_asr_nano/lora_finetune.sh), [fine-tuning guide](../examples/industrial_data_pretraining/fun_asr_nano/docs/finetune.md) | Default script freezes audio encoder/adaptor and unfreezes the LLM; it is not an all-parameter recipe. Pure LoRA additionally uses `llm_conf.use_lora=true`, `lora_only=true`, `llm_conf.freeze=true`. Audit trainable parameters, including any CTC component. |
| Paraformer | [finetune.sh](../examples/industrial_data_pretraining/paraformer/finetune.sh), [README](../examples/industrial_data_pretraining/paraformer/README.md), [LoRA guide](../examples/industrial_data_pretraining/paraformer/README_LoRA_zh.md) | The industrial recipe explicitly selects `AudioDataset` / `IndexDSJsonl`. Paraformer LoRA is a separate recipe, not Nano's adapter configuration. |
| MOSS-Transcribe-Diarize | [FunASR adapter source](../funasr/models/moss_transcribe_diarize/model.py) | Third-party OpenMOSS model. This adapter's `forward` raises an inference-only error; MOSS training is not covered here. |

FunASR software is MIT-licensed; model weights, upstream code, datasets and derived checkpoints can have different licenses. Check each asset's terms and data consent before training or redistribution.

## Prepare the Dataset

Keep training, validation and final test sets separate, ideally split by speaker/session as well as utterance. Check duplicate IDs, matching audio/transcript IDs, file readability, decoded duration/sample rate, transcript normalization and language coverage. Resolve relative audio paths from the process working directory, not implicitly from the JSONL file's directory. Prefer stable local audio paths when reproducibility or privacy matters.

### Paraformer: Audio and Text JSONL

The [converter](../funasr/datasets/audio_datasets/scp2jsonl.py) joins `wav.scp` and text by utterance ID. Each input line is `utterance_id value`; transcript text may contain spaces. For a two-second recording the structural example is:

```json
{"key":"utt001","source":"data/audio/utt001.wav","source_len":200,"target":"hello world","target_len":2}
```

`key`, `source`, `target` are strings; length fields are integers. `source_len` is `int(samples_at_16kHz / 160)`, approximately 10 ms units, not seconds. The converter's `target_len` is whitespace-word count when spaces exist, otherwise character count; it is not universally a tokenizer count. The [index reader](../funasr/datasets/audio_datasets/index_ds.py) filters by configured source/target/token limits, and the [dataset](../funasr/datasets/audio_datasets/datasets.py) performs feature extraction/tokenization.

Prepare `data/list/train_wav.scp`, `train_text.txt`, `val_wav.scp`, `val_text.txt`, then run from the repository root:

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

The converter can skip missing audio and emit incomplete records when transcripts are missing. Compare input/output counts and reject incomplete rows; a successful process exit is insufficient. Use trusted CLI configuration only: this historical converter has an `eval` fallback for string-valued lists.

### SenseVoice: Preserve Rich Labels

For the `SenseVoiceCTCDataset` path, add explicit supervision fields to the audio/text schema:

```json
{"key":"utt001","source":"data/audio/utt001.wav","source_len":200,"target":"你好","target_len":2,"text_language":"<|zh|>","emo_target":"<|NEUTRAL|>","event_target":"<|Speech|>","with_or_wo_itn":"<|woitn|>"}
```

These strings must be appropriate labels for the recording, not placeholders applied indiscriminately. The [CTC dataset implementation](../funasr/datasets/sense_voice_datasets/datasets.py) defaults missing fields to the values above; defaults are not validated ground truth. The older `SenseVoiceDataset` is a different dataset implementation. Keep the dataset class consistent with the selected model configuration.

[sensevoice2jsonl.py](../funasr/datasets/audio_datasets/sensevoice2jsonl.py) accepts aligned source/target/language/emotion/event files via `scp_file_list` and `data_type_list`. If language, emotion or event labels are missing, it invokes SenseVoice to generate pseudo-labels, which can download/run a model. Its ITN flag uses a punctuation heuristic. Review labels and normalization before training. Do not invent a new language tag without coordinated tokenizer/model changes; see the [continual fine-tuning guide](../examples/industrial_data_pretraining/sense_voice/CONTINUAL_FINETUNING.md).

### FunASRNano: ChatML JSONL

Nano does not consume the plain Paraformer schema in its provided recipe. See the actual [training sample](../examples/industrial_data_pretraining/fun_asr_nano/data/train_example.jsonl) and [validation sample](../examples/industrial_data_pretraining/fun_asr_nano/data/val_example.jsonl). A structural example, whose lengths must be recomputed for real data:

```json
{"messages":[{"role":"system","content":"You are a helpful assistant."},{"role":"user","content":"语音转写：<|startofspeech|>!data/audio/utt001.wav<|endofspeech|>"},{"role":"assistant","content":"你好"}],"speech_length":198,"text_length":1}
```

`messages` is a list of role/content dictionaries; assistant content is the target transcript. The [recipe converter](../examples/industrial_data_pretraining/fun_asr_nano/tools/scp2jsonl.py) pairs SCP/transcript lines in order, requires matching IDs, computes `speech_length = int((duration * 1000 - 25) // 10 + 1)`, and obtains `text_length` from `Qwen/Qwen3-0.6B` tokenization. It may fetch that tokenizer or URL audio. Line-count mismatches are only warnings, and bad pairs can be omitted: check the resulting counts and every error.

Use your prepared inputs and output files rather than overwriting the shipped examples:

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

## Validate Small, Then Launch

1. Pin the checkout and model assets; record dependencies, tokenizer/frontend settings, GPU configuration, data hashes and random seed. Review all downloaded Python and requirements before enabling `trust_remote_code`.
2. Build tiny, disjoint `data/list/train_smoke.jsonl` and `data/list/val_smoke.jsonl` from validated records. Actually load their audio and tokenize their targets. Check non-empty batches after length filtering, finite loss and the intended trainable parameter names.
3. Run a short training/validation/checkpoint cycle before scaling. Do not run the historical shell scripts blindly: they set GPU IDs, output paths and working-directory-dependent paths internally and do not generally forward appended CLI overrides.

Here is a root-relative Paraformer smoke-run template derived from the industrial recipe. It requires a compatible GPU, installed training dependencies, the two prepared JSONL files, and a reviewed complete model directory at `models/paraformer`. The token budget `2000` is a starting value for short clips, not a memory guarantee; reduce it only while ensuring individual samples still fit. One epoch is only small if the input dataset is small.

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

Use a new output directory for every fresh experiment and an available rendezvous port. For SenseVoice or Nano, start from that family's recipe/configuration and schema, not a substitution into this `AudioDataset` command. Nano's scripts locate `funasr-train-ds` on `PATH`; confirm it belongs to the intended installation. The SenseVoice and Paraformer scripts contain DeepSpeed config paths even with `use_deepspeed=false`; verify a real config before enabling DeepSpeed. Full distributed training and resource sizing require separate validation.

## Checkpoints and Resume

The [entry point](../funasr/bin/train_ds.py) calls [Trainer.resume_checkpoint](../funasr/train_utils/trainer_ds.py). In the non-DeepSpeed path, `++train_conf.resume=true` restores `output_dir/model.pt`, including model, optimizer, scheduler and available scaler/progress state. It is a boolean switch, not an arbitrary checkpoint path. If that file is missing, the trainer reports no resume and continues. Confirm restoration in logs.

To continue the smoke run, rerun its command with the same output directory/configuration, `++train_conf.resume=true` and `++train_conf.max_epoch=2`. The epoch limit is total, not additional epochs. `++init_param=...` loads initial weights; it does not restore optimizer/progress state. Use a fresh output directory and `resume=false` for a new adaptation stage with a selected initialization checkpoint.

Non-DeepSpeed saves include `model.pt`, `model.pt.ep{epoch}` or `model.pt.ep{epoch}.{step}`; `model.pt.best` depends on validation ranking. DeepSpeed saves use checkpoint directories/tags and require its corresponding restore/conversion path. Do not treat those directories or incomplete/adaptor-only state as ordinary standalone weights. Preserve configuration, tokenizer/frontend assets and base-model provenance; inspect save exclusions and LoRA settings. A checkpoint file alone is not necessarily a loadable model directory.

## Evaluate and Export

Load a prepared Paraformer model directory and a real selected checkpoint for a one-file sanity check:

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

Then decode an untouched held-out set with the same normalization and CER/WER unit definition for baseline and adapted weights. Report per-domain/language results as well as aggregate scores, retained-task regressions, data counts and checkpoint identity. Training loss or trainer validation accuracy is not automatically transcription CER/WER. [Nano's fine-tuning guide](../examples/industrial_data_pretraining/fun_asr_nano/docs/finetune.md) retains the decoding/normalization/scoring references; [decode.py](../examples/industrial_data_pretraining/fun_asr_nano/decode.py) uses VAD and `remote_code="./model.py"`, so it assumes the recipe working directory. That [legacy local class](../examples/industrial_data_pretraining/fun_asr_nano/model.py) can replace the [built-in Nano class](../funasr/models/fun_asr_nano/model.py). Do not assume it preserves built-in LoRA support; verify the active class, adapter injection and loaded keys before evaluation.

Export is a separate compatibility task. [SenseVoice's ONNX example](../examples/industrial_data_pretraining/sense_voice/export.py), [Paraformer export example](../examples/industrial_data_pretraining/paraformer/export.py) and [export utility](../funasr/utils/export_utils.py) are entry points, not universal support promises. The Paraformer example itself selects a contextual checkpoint; inspect and deliberately choose your model. Model-specific export hooks, tokenizer/frontend assets, dynamic shapes and runtime decoding all need validation. Compare the exported runtime against Python on held-out inputs before deployment. No full training, quality benchmark, real-checkpoint resume, model download or export run was performed for this documentation change.
