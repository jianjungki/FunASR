"""Check documented contracts against source without importing model runtimes."""

import ast
import hashlib
import inspect
import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GUIDES = ("vllm_guide.md", "vllm_guide_zh.md", "vllm_guide_zh_v2.md")
NANO = "funasr/models/fun_asr_nano/inference_vllm.py"
AUTO = "funasr/auto/auto_model_vllm.py"
VAD = "funasr/models/fsmn_vad_streaming/model.py"
SERVER = "examples/industrial_data_pretraining/fun_asr_nano/serve_vllm.py"


def blocks(text, language):
    return re.findall(rf"^```{language}\n(.*?)^```", text, re.M | re.S)


@pytest.fixture(params=GUIDES)
def guide(request):
    return request.param, (ROOT / "docs" / request.param).read_text()


def source_function(path, name, class_name=None):
    tree = ast.parse((ROOT / path).read_text())
    if class_name:
        tree = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def signature(path, class_name):
    function = source_function(path, "generate", class_name)
    function.body = [ast.Pass()]
    function.decorator_list = []
    function.returns = None
    for argument in ast.walk(function.args):
        if isinstance(argument, ast.arg):
            argument.annotation = None
    namespace = {}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            path,
            "exec",
        ),
        namespace,
    )
    return inspect.signature(namespace["generate"])


def generate_calls(text):
    kinds = {}
    for block in blocks(text, "python"):
        tree = ast.parse(block)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            constructor = node.value.func
            if isinstance(constructor, ast.Attribute):
                constructor = constructor.value
            if not isinstance(constructor, ast.Name):
                continue
            kind = constructor.id
            if kind == "AutoModel":
                model = next(
                    (kw.value for kw in node.value.keywords if kw.arg == "model"), None
                )
                kind = (
                    "vad"
                    if isinstance(model, ast.Constant) and model.value == "fsmn-vad"
                    else kind
                )
            for target in node.targets:
                if isinstance(target, ast.Name):
                    kinds[target.id] = kind
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "generate"
                and isinstance(node.func.value, ast.Name)
            ):
                yield kinds.get(node.func.value.id), node


def test_generate_examples_bind_to_actual_signatures(guide):
    _, text = guide
    signatures = {
        "AutoModelVLLM": signature(AUTO, "AutoModelVLLM"),
        "FunASRNanoVLLM": signature(NANO, "FunASRNanoVLLM"),
        "vad": signature("funasr/auto/auto_model.py", "AutoModel"),
    }
    checked = 0
    for kind, call in generate_calls(text):
        if kind in signatures:
            signatures[kind].bind(
                object(),
                *[object() for _ in call.args],
                **{kw.arg: object() for kw in call.keywords if kw.arg},
            )
            checked += 1
    assert checked >= 3


def test_manifest_is_a_cli_contract_not_a_direct_engine_input(guide):
    _, text = guide
    for kind, call in generate_calls(text):
        if kind not in {"AutoModelVLLM", "FunASRNanoVLLM"}:
            continue
        inputs = list(call.args) + [
            kw.value for kw in call.keywords if kw.arg == "inputs"
        ]
        for value in inputs:
            for node in ast.walk(value):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    assert not node.value.endswith((".scp", ".jsonl")), ast.unparse(
                        call
                    )
    assert "demo_vllm.py --input wav.scp" in text
    demo = (
        ROOT / "examples/industrial_data_pretraining/fun_asr_nano/demo_vllm.py"
    ).read_text()
    assert 'args.input.endswith(".scp")' in demo
    assert 'args.input.endswith(".jsonl")' in demo
    assert 'audio_files.append(item["source"])' in demo
    assert "load_audio_text_image_video(audio_input" in (ROOT / NANO).read_text()


def test_dynamic_options_are_sent_to_the_actual_vad_consumer(guide):
    _, text = guide
    options = {"silence_schedule", "dynamic_silence"}
    seen = set()
    for kind, call in generate_calls(text):
        specified = options.intersection(kw.arg for kw in call.keywords)
        if specified:
            assert kind == "vad", "VAD options do not configure the ASR engine"
            seen.update(specified)
    assert seen == options
    inference = source_function(VAD, "inference", "FsmnVADStreaming")
    consumed = {
        node.args[0].value
        for node in ast.walk(inference)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and node.args
        and isinstance(node.args[0], ast.Constant)
    }
    assert options <= consumed


def test_dynamic_schedule_table_matches_sdk_constants(guide):
    _, text = guide
    tree = ast.parse((ROOT / VAD).read_text())
    schedules = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id
            in {"DEFAULT_SILENCE_SCHEDULE", "STREAMING_SILENCE_SCHEDULE"}
        ):
            schedules[node.targets[0].id] = eval(
                compile(ast.Expression(node.value), VAD, "eval"),
                {"__builtins__": {}, "float": float},
            )
    rows = re.findall(r"^\| (\d+) ms \| (\d+) ms \| (\d+) ms \|$", text, re.M)
    assert len(rows) >= 9
    for duration, offline, streaming in rows:
        for column, name in [
            (offline, "DEFAULT_SILENCE_SCHEDULE"),
            (streaming, "STREAMING_SILENCE_SCHEDULE"),
        ]:
            expected = next(
                threshold
                for limit, threshold in schedules[name]
                if int(duration) <= limit
            )
            assert int(column) == expected


def test_json_examples_are_valid_and_verbose_output_matches_serializer(guide):
    _, text = guide
    examples = [json.loads(block) for block in blocks(text, "json")]
    assert len(examples) >= 2
    function = source_function(SERVER, "build_openai_verbose_json")
    namespace = {}
    exec(
        compile(ast.Module(body=[function], type_ignores=[]), SERVER, "exec"), namespace
    )
    verbose = next(
        example for example in examples if example.get("task") == "transcribe"
    )
    result = {key: verbose[key] for key in ("text", "duration", "segments")}
    assert (
        namespace["build_openai_verbose_json"](result, language=verbose["language"])
        == verbose
    )
    for example in examples:
        for segment in example.get("segments", []):
            assert 0 <= segment["start"] <= segment["end"] <= example["duration"]
            for word in segment.get("words", []):
                assert (
                    segment["start"] <= word["start"] <= word["end"] <= segment["end"]
                )


def test_websocket_examples_are_individual_messages(guide):
    _, text = guide
    streams = [
        block for block in blocks(text, "text") if '{"event": "started"}' in block
    ]
    assert len(streams) == 2
    for stream in streams:
        events = [json.loads(line) for line in stream.splitlines() if line.strip()]
        assert events[0] == {"event": "started"}
        assert events[-1] == {"event": "stopped"}
        final = next(event for event in events if event.get("is_final"))
        assert final["sentences"]
        for sentence in final["sentences"]:
            assert isinstance(sentence["text"], str) and sentence["text"] != "..."
            assert 0 <= sentence["start"] <= sentence["end"]


def test_performance_claims_distinguish_throughput_and_measured_accuracy(guide):
    _, text = guide
    assert "340 / 21" in text and "16.2" in text
    assert "8.20%" in text and "8.06%" in text and "0.14" in text
    assert "8.14%" in text and "8.19%" in text
    assert "benchmark/rtf_reproducibility.md" in text
    for stale in (
        "16-340x",
        "16–340x",
        "21.7x",
        "7.6x",
        "RTFx 340+",
        "CER 完全一致",
        "CER exactly",
        "CER 不变",
        "CER is unchanged",
        "Subsequent inferences are instant",
        "之后即时",
    ):
        assert stale not in text


def test_historical_heading_anchors_are_preserved(guide):
    name, text = guide
    prose = re.sub(r"^```[^\n]*\n.*?^```\s*$", "", text, flags=re.M | re.S)
    headings = re.findall(r"^#{1,6} .+$", prose, re.M)
    expected = (
        "678bb9b4403454e8773e1470e7e90e9ed2cf2500266eaa06c58b6dda20b48134"
        if name == "vllm_guide.md"
        else "8b56033dfcfc2bf80e12cc8fa272a313311a1a0730f8f5c0c73fd95e8c56018f"
    )
    assert hashlib.sha256("\n".join(headings).encode()).hexdigest() == expected
