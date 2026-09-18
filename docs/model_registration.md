# Model Registration

[简体中文](model_registration_zh.md) | [Documentation](tutorial/README.md) | [Training](training.md) | [Historical registry tutorial](tutorial/Tables.md)

Registration connects a Python implementation to a configuration name. It does not download weights, make an arbitrary Transformers model compatible, provide training/export support, or certify model quality. This guide describes the checked-in [registry](../funasr/register.py), [AutoModel](../funasr/auto/auto_model.py), [hub loader](../funasr/download/download_model_from_hub.py) and [dynamic importer](../funasr/utils/dynamic_import.py).

## Names and Import Order

Use `@tables.register("model_classes", "YourUniqueModelName")` on a class imported before construction. `tables` comes from `funasr.register`. The second argument is the exact, case-sensitive registry key; omitting it uses the Python class name. The decorator returns the original class and records its source location with `inspect`, so define examples in importable `.py` files, not only a REPL or dynamically generated class.

Keys live in process-global dictionaries. An existing key is overwritten, with a debug log rather than an error; imports and their order therefore matter. Use an organization/project-specific name and a collision guard. Avoid names such as `SenseVoiceSmall`, `Paraformer` or `FunASRNano` for unrelated custom models. `tables.print("model")` displays registration metadata; `tables.model_classes[name]` gives the active implementation.

Other tables include `encoder_classes`, `decoder_classes`, `frontend_classes`, `tokenizer_classes`, `dataset_classes`, `index_ds_classes` and `batch_sampler_classes`. Each consumer has its own contract: registering an encoder does not make it a complete `AutoModel` model. The registry also permits new table names, so a typo can create an unused table instead of failing.

## Minimal Local Contract Example

Put the following example in an importable `custom_model_demo.py` in a scratch directory, then run `python custom_model_demo.py` with this checkout installed. It intentionally returns input text, not speech recognition. It does not need weights, audio, a hub download, or GPU. The parameter is present because this `AutoModel.inference` inspects `next(model.parameters()).device`; a parameterless toy fails that path.

```python
import torch
from funasr import AutoModel
from funasr.register import tables

MODEL_NAME = "DocsEchoModelV1"
if MODEL_NAME in tables.model_classes:
    raise RuntimeError(f"Registry collision: {MODEL_NAME}")


@tables.register("model_classes", MODEL_NAME)
class DocsEchoModel(torch.nn.Module):
    def __init__(self, **kwargs):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1), requires_grad=False)

    def inference(
        self, data_in, data_lengths=None, key=None,
        tokenizer=None, frontend=None, **kwargs,
    ):
        results = [
            {"key": sample_key, "text": str(value)}
            for sample_key, value in zip(key, data_in)
        ]
        return results, {}


if __name__ == "__main__":
    model = AutoModel(
        model=MODEL_NAME,
        model_conf={},
        device="cpu",
        disable_update=True,
        disable_pbar=True,
    )
    result = model.generate(input=["hello", "world"], data_type="text")
    assert [row["text"] for row in result] == ["hello", "world"]
    assert all(isinstance(row["key"], str) for row in result)
    print([row["text"] for row in result])
```

Expected final printed list: `['hello', 'world']`. This is a wiring check only. The focused documentation test executes this block in a temporary file against the checked-out implementation; it does not validate a speech model.

The presence of `model_conf={}` is intentional: `AutoModel.build_model` skips hub/config resolution when that key is supplied. Thus `model` is the already-registered class key here, not a model directory or hub ID. Import the custom module yourself first; adding `remote_code` to this direct path does not cause it to be imported. Resolved kwargs are merged over `model_conf` and passed to the constructor, including built tokenizer/frontend objects, device and vocabulary/input sizes. Accept appropriate named arguments plus `**kwargs`, as the real models do.

## Inference and Training Contracts

| Interface | Contract in this checkout |
| --- | --- |
| Model object | Normally `torch.nn.Module`; must support `.to(...)`, `.eval()` and `.parameters()`. Constructor configuration is model-specific. |
| `inference` inputs | Without VAD, AutoModel batches input into `data_in` and `key` lists and calls `model.inference(**batch, **kwargs)` under `torch.no_grad()`. With `data_type="fbank"` and one item, it passes the feature object directly and supplies `data_lengths=input_len`. Tokenizer/frontend are resolved objects or `None`. |
| Model-level return | Return a two-item tuple `(results, meta_data)`: `results` is `list[dict]`, `meta_data` is a dictionary. For ASR use string `key` and `text` fields, preserving the input order/keys. Returning a bare list of result dictionaries is wrong: AutoModel treats its first item as the entire batch result. |
| Metadata | Optional `load_data`, `extract_feat`, `batch_data_time`. For audio, `batch_data_time` is a positive duration in seconds, not milliseconds; zero causes division by zero in timing code. Omitting it gives the internal `-1` sentinel, as in the non-audio toy, not a meaningful speed measurement. |
| Public return | `AutoModel.generate(...)` returns the flattened result list. Additional fields such as timestamps are model-specific; registration does not promise them. VAD, punctuation, speaker and streaming integrations need additional compatible behavior and independent tests. |
| Training | Implement differentiable `forward` matching the dataset collator's named tensor fields. [Trainer](../funasr/train_utils/trainer_ds.py) unpacks `(loss, stats, weight)`; [SenseVoice](../funasr/models/sense_voice/model.py) and [Nano](../funasr/models/fun_asr_nano/model.py) use `force_gatherable`. The toy deliberately has no training forward. |
| Export | [Export utility](../funasr/utils/export_utils.py) calls the model's `export` and then model-specific methods such as `export_dummy_inputs`, input/output names and dynamic axes. Registration alone does not implement these. |

A custom model must itself implement audio loading, feature preparation, tokenization/decoding and batching where needed. Copy the contract from a close real model, not its capabilities without implementation. For training, also implement/configure the appropriate dataset and loss; see [training](training.md).

## Loading Reviewed Custom Code and Weights

There are two distinct routes:

1. **Direct registration:** import your module; pass its key and `model_conf` as in the toy. Provide compatible tokenizer/frontend/configuration and an existing `init_param` if weights are needed. No hub code import is performed on this path.
2. **Model-directory resolution:** pass a reviewed local directory or hub ID without `model_conf`. The loader reads `configuration.json` file metadata or `config.yaml`, resolves the model key/assets and loads weights. A simple local `config.yaml` directory normally also needs `model.pt` plus all referenced tokenizer/frontend assets. Arbitrary HF weight folders are not automatically FunASR model directories.

For the second route, this is the ModelScope-path interface, not a self-contained runnable example. `models/custom-asr` must already contain the compatible reviewed configuration and weights, and `custom_asr_model.py` must register the exact configuration key:

```python
from funasr import AutoModel

model = AutoModel(
    model="./models/custom-asr",
    hub="ms",
    trust_remote_code=True,
    remote_code="./custom_asr_model.py",
    device="cpu",
    disable_update=True,
)
print(model.generate(input="data/audio/heldout.wav"))
```

The current `download_from_ms` imports `remote_code` when `trust_remote_code=True`, defaulting to module name `model` if omitted. The importer supports module/file paths (and URL download), appends the directory to `sys.path` and imports by basename. A relative path is relative to the working directory, not automatically to the weights directory. Basename collisions and Python's import cache can select an already-loaded module; use distinct module names and verify the active class. Import exceptions are printed rather than re-raised by this helper, so inspect errors and registry state.

**The `hub="hf"` path differs:** in this checkout `download_from_hf` can install model requirements under the trust flag but does not call `import_module_from_path`. Do not assume `remote_code` is executed there. Import your reviewed custom module explicitly before constructing with `hub="hf"`, or use the direct-registration route with complete configuration. The local `config.yaml` fallback also handles `init_param` differently between hubs: ModelScope retains an existing explicit path; Hugging Face assigns the directory's `model.pt`. Check the resolved path rather than assuming a selected checkpoint override survived.

## Real Examples and Boundaries

- [SenseVoiceSmall implementation](../funasr/models/sense_voice/model.py) demonstrates a registered model with training, inference and export integration. Retain its model-specific configuration and tokenizer assumptions.
- [Nano demo1.py](../examples/industrial_data_pretraining/fun_asr_nano/demo1.py) shows `trust_remote_code=True`, `remote_code="./model.py"`, `hub="ms"`; it assumes the recipe directory. Its [local implementation](../examples/industrial_data_pretraining/fun_asr_nano/model.py) registers `FunASRNano` and imports sibling `ctc` and `tools` modules. That can overwrite the [built-in implementation](../funasr/models/fun_asr_nano/model.py); the two are not interchangeable for every feature, including built-in LoRA. Audit the active class and checkpoint keys.
- [MOSS adapter](../funasr/models/moss_transcribe_diarize/model.py) integrates the third-party OpenMOSS model, and explicitly rejects training in `forward`. It is not evidence that a registered model supports fine-tuning or export.
- The [original registration tutorial](tutorial/Tables.md) and [general tutorial](tutorial/README.md) remain useful historical references; use the current source behavior above when their examples differ.

## Safety and Verification

`trust_remote_code=True` permits Python execution; the hub loaders can also install a model directory's `requirements.txt`. A local directory is not inherently trustworthy. Review source, dependencies and weight serialization, use isolated environments, and do not load untrusted pickled checkpoints. Never interpolate untrusted URLs, module names or configs into this workflow. Keep a reviewed local snapshot with hashes when remote revision handling cannot be relied on; `model_revision` is not a universal pin across all loader paths here.

Check the active registry key/class/source before loading. Confirm exact model/config/tokenizer compatibility and inspect missing/unexpected weights: `ignore_init_mismatch` defaults to true in AutoModel, and a nonexistent direct `init_param` prints an error rather than guaranteeing construction fails. Validate checkpoint existence yourself. Test one item, multiple items, error handling and the intended pipeline before training/export/deployment. FunASR software's MIT license does not replace model or upstream component licenses.

Focused syntax, repository-link and no-download toy-contract checks:

```bash
python -m pytest -q tests/test_training_docs_contract.py
```

These checks do not certify arbitrary custom code, actual ASR quality, GPU training, real-checkpoint restoration or export compatibility.
