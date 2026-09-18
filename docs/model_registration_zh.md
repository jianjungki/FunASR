# 模型注册

[English](model_registration.md) | [文档](tutorial/README_zh.md) | [训练](training_zh.md) | [历史注册教程](tutorial/Tables_zh.md)

注册把 Python 实现与配置名称连接起来，不会下载权重、自动兼容任意 Transformers 模型、提供训练或导出能力，也不代表质量认证。本指南依据当前仓库的[注册表](../funasr/register.py)、[AutoModel](../funasr/auto/auto_model.py)、[模型加载器](../funasr/download/download_model_from_hub.py)和[动态导入工具](../funasr/utils/dynamic_import.py)。

## 名称与导入顺序

对构造前已导入的类使用 `@tables.register("model_classes", "YourUniqueModelName")`，其中 `tables` 来自 `funasr.register`。第二个参数是区分大小写的精确注册键，省略时使用 Python 类名。装饰器返回原类，并通过 `inspect` 记录源码位置，所以应把示例定义在可导入的 `.py` 文件中，而非仅在 REPL 或动态生成类中定义。

注册键保存在进程级字典中。同名键会被覆盖，只记录 debug 日志而不报错，因此导入顺序会影响行为。使用组织或项目专属名称并增加冲突检查，不要给无关自定义模型使用 `SenseVoiceSmall`、`Paraformer`、`FunASRNano` 等已有名称。`tables.print("model")` 显示注册元数据，`tables.model_classes[name]` 给出当前生效实现。

其他表包括 `encoder_classes`、`decoder_classes`、`frontend_classes`、`tokenizer_classes`、`dataset_classes`、`index_ds_classes`、`batch_sampler_classes`。每个调用方都有自己的接口约定，注册 encoder 不等于注册完整 `AutoModel` 模型。注册器也允许创建新表，表名拼错可能生成无人使用的表，而不是报错。

## 最小本地接口示例

在临时目录中创建可导入的 `custom_model_demo.py`，内容如下，然后在已安装当前 checkout 的环境执行 `python custom_model_demo.py`。它只回显文本，不执行语音识别；不需要权重、音频、模型下载或 GPU。保留一个参数是因为当前 `AutoModel.inference` 会读取 `next(model.parameters()).device`，无参数的玩具模型会在此失败。

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

最后输出应为 `['hello', 'world']`。这只是接口连通性验证，专项文档测试会在临时文件中针对当前源码执行这段代码，不验证语音模型。

`model_conf={}` 是有意传入的：只要该键存在，`AutoModel.build_model` 就跳过 hub/配置解析。因此这里的 `model` 是已注册类名，不是目录或 hub ID。必须先自行导入模块；在该直接构造路径中添加 `remote_code` 不会触发导入。解析后的 kwargs 覆盖合并到 `model_conf`，一起传给构造器，包括已构造的 tokenizer/frontend、设备、词表与输入维度。请像真实模型一样接收相应命名参数及 `**kwargs`。

## 推理与训练接口

| 接口 | 当前源码约定 |
| --- | --- |
| 模型对象 | 通常为 `torch.nn.Module`，需要支持 `.to(...)`、`.eval()`、`.parameters()`；构造配置由模型决定。 |
| `inference` 输入 | 不使用 VAD 时，AutoModel 把输入组织成 `data_in` 和 `key` 列表，在 `torch.no_grad()` 下调用 `model.inference(**batch, **kwargs)`。单条 `data_type="fbank"` 输入会直接传入特征对象，并设 `data_lengths=input_len`。tokenizer/frontend 是已构造对象或 `None`。 |
| 模型层返回值 | 返回二元组 `(results, meta_data)`，其中 `results` 是 `list[dict]`，`meta_data` 是字典。ASR 结果使用字符串 `key`、`text` 并保持输入顺序与标识。不能只返回结果字典列表，否则 AutoModel 会把第一条当成整个 batch 结果。 |
| 元数据 | 可包含 `load_data`、`extract_feat`、`batch_data_time`。音频的 `batch_data_time` 是以秒为单位的正时长，不能填毫秒或零，零会导致计时代码除零。省略时使用内部 `-1` 哨兵值，如上述非音频示例，并不代表有效速度测量。 |
| 公开返回值 | `AutoModel.generate(...)` 返回展开后的结果列表。时间戳等附加字段由模型决定，注册并不承诺这些字段。VAD、标点、说话人和流式集成还需额外兼容实现与独立测试。 |
| 训练 | 实现可微 `forward`，命名张量参数应匹配 dataset collator。[训练器](../funasr/train_utils/trainer_ds.py)解包 `(loss, stats, weight)`；[SenseVoice](../funasr/models/sense_voice/model.py)和 [Nano](../funasr/models/fun_asr_nano/model.py)使用 `force_gatherable`。玩具模型故意不实现训练 forward。 |
| 导出 | [导出工具](../funasr/utils/export_utils.py)调用模型的 `export`，再使用 `export_dummy_inputs`、输入输出名称、动态轴等模型专属方法。注册本身不会实现这些方法。 |

自定义模型仍需自行实现所需的音频加载、特征处理、分词、解码及 batching。参考相近模型的接口，不能在缺少实现时宣称具有其能力。训练还需适配数据集与损失函数，参见[训练指南](training_zh.md)。

## 加载已审查代码与权重

有两条不同路径：

1. **直接注册构造：**先导入模块，再像玩具示例一样传注册键和 `model_conf`。需要权重时提供兼容的 tokenizer/frontend/配置及真实存在的 `init_param`。该路径不执行 hub 代码导入。
2. **模型目录解析：**传已审查的本地目录或 hub ID，不传 `model_conf`。加载器读取 `configuration.json` 文件元数据或 `config.yaml`，解析类名和资产并加载权重。简单的本地 `config.yaml` 目录通常还需要 `model.pt` 及配置引用的分词器、前端文件。任意 HF 权重文件夹不会自动成为 FunASR 模型目录。

第二条路径的 ModelScope 接口如下，它不是无需准备即可运行的例子。`models/custom-asr` 必须已有兼容且审查过的配置和权重，`custom_asr_model.py` 必须注册配置指定的精确键：

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

当前 `download_from_ms` 在 `trust_remote_code=True` 时导入 `remote_code`，未指定时默认为模块名 `model`。导入器支持模块/文件路径及 URL 下载，把目录加入 `sys.path` 后按文件基本名导入。相对路径按工作目录解析，不会自动相对权重目录解析。文件基本名冲突及 Python 导入缓存可能选中已加载模块，应使用独立模块名并验证当前类。该辅助函数打印导入异常而不重新抛出，应检查错误日志与注册结果。

**`hub="hf"` 路径不同：**本 checkout 的 `download_from_hf` 在信任开关下可安装模型依赖，但不调用 `import_module_from_path`，不能假定它会执行 `remote_code`。在 `hub="hf"` 构造前显式导入已审查模块，或使用完整配置的直接注册构造路径。两条路径的本地 `config.yaml` 回退对 `init_param` 也不同：ModelScope 保留已有且存在的显式路径，Hugging Face 则指定目录内 `model.pt`。必须检查解析后的真实路径，不要假定 checkpoint 覆盖始终有效。

## 真实示例与边界

- [SenseVoiceSmall 实现](../funasr/models/sense_voice/model.py)展示注册、训练、推理和导出集成，但需保持其模型配置与分词器假设。
- [Nano demo1.py](../examples/industrial_data_pretraining/fun_asr_nano/demo1.py)使用 `trust_remote_code=True`、`remote_code="./model.py"`、`hub="ms"`，要求 recipe 工作目录。其[本地实现](../examples/industrial_data_pretraining/fun_asr_nano/model.py)注册 `FunASRNano` 并导入同目录的 `ctc`、`tools` 模块，可能覆盖[内置实现](../funasr/models/fun_asr_nano/model.py)。两者并非对所有功能可互换，尤其不能假定保留内置 LoRA，应检查实际类和权重键。
- [MOSS 适配器](../funasr/models/moss_transcribe_diarize/model.py)集成第三方 OpenMOSS 模型，其 `forward` 明确拒绝训练。注册模型不意味着支持微调或导出。
- [原始注册教程](tutorial/Tables_zh.md)和[通用教程](tutorial/README_zh.md)保留为历史入口；示例有差异时，以这里说明的当前源码行为为准。

## 安全与验证

`trust_remote_code=True` 允许执行 Python；hub 加载器还可能安装模型目录的 `requirements.txt`。本地目录不天然可信。审核源码、依赖与权重序列化方式，使用隔离环境，不加载不可信的 pickle checkpoint。不要把不可信 URL、模块名或配置直接接入流程。远程 revision 行为不可靠时保留带哈希的已审查本地快照；这里的 `model_revision` 并非所有加载路径都能统一固定版本。

加载前检查当前注册键、类和源码位置。确认模型、配置、分词器兼容，并检查缺失或多余权重：AutoModel 的 `ignore_init_mismatch` 默认为 true，直接传入不存在的 `init_param` 会打印错误，不保证构造失败。应自行验证 checkpoint 存在。训练、导出、部署前分别测试单条、多条、异常输入与目标流水线。FunASR 软件的 MIT 许可证不替代模型或上游组件的许可。

运行专项语法、仓库链接和不下载模型的玩具接口测试：

```bash
python -m pytest -q tests/test_training_docs_contract.py
```

这些检查不认证任意自定义代码、真实 ASR 质量、GPU 训练、真实 checkpoint 恢复或导出兼容性。
