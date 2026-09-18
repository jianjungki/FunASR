"""Static learning-guide contracts; never import models or download artifacts."""

import ast
from collections import Counter
import importlib.util
from pathlib import Path
import re
import shlex
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
PAIRS = (
    ("docs/installation/installation.md", "docs/installation/installation_zh.md"),
    ("docs/installation/docker.md", "docs/installation/docker_zh.md"),
    ("docs/tutorial/README.md", "docs/tutorial/README_zh.md"),
)
DOCS = tuple(path for pair in PAIRS for path in pair)


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def fences(text):
    """Read the unindented fenced examples used by these six guides."""
    language = None
    lines = []
    for line in text.splitlines():
        if line.startswith("```"):
            if language is None:
                language = line[3:].strip()
                lines = []
            else:
                yield language, "\n".join(lines) + "\n"
                language = None
        elif language is not None:
            lines.append(line)
    if language is not None:
        raise AssertionError("Unclosed code fence")


class LearningDocsContract(unittest.TestCase):
    def test_rendered_tutorial_ids_are_unique_and_keep_legacy_anchors(self):
        from bs4 import BeautifulSoup

        spec = importlib.util.spec_from_file_location(
            "learning_documentation", ROOT / "web-pages/product-site/documentation.py"
        )
        documentation = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(documentation)
        catalogue = documentation.load_catalogue()
        entry = next(page for page in catalogue["pages"] if page["slug"] == "quickstart")
        legacy = {
            "en": ("Inference", "Training", "Export", "new-model-registration-tutorial"),
            "zh": ("模型推理", "模型训练与测试", "模型导出与测试", "新模型注册教程"),
        }
        for language, anchors in legacy.items():
            with self.subTest(language=language):
                rendered = documentation.render_source(entry, language, catalogue)
                soup = BeautifulSoup(rendered["content_html"], "html.parser")
                ids = Counter(node["id"] for node in soup.select("[id]"))
                self.assertEqual({key: count for key, count in ids.items() if count > 1}, {})
                for anchor in anchors:
                    self.assertEqual(ids[anchor], 1)

    def test_python_examples_compile_without_running(self):
        count = 0
        for path in DOCS:
            for language, code in fences(read(path)):
                if language == "python":
                    with self.subTest(path=path, code=code[:70]):
                        compile(code, path, "exec")
                    count += 1
        self.assertGreaterEqual(count, 16)

    def test_shell_syntax_and_embedded_python_without_execution(self):
        for path in DOCS:
            for language, code in fences(read(path)):
                if language not in {"sh", "shell", "bash"}:
                    continue
                with self.subTest(path=path, code=code[:70]):
                    result = subprocess.run(
                        ["bash", "-n"], input=code, text=True,
                        capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    for line in code.splitlines():
                        if not line.startswith("python -c "):
                            continue
                        words = shlex.split(line)
                        if words[:2] == ["python", "-c"]:
                            compile(words[2], path, "exec")

    def test_bilingual_examples_are_identical(self):
        for english, chinese in PAIRS:
            with self.subTest(pair=(english, chinese)):
                self.assertEqual(list(fences(read(english))), list(fences(read(chinese))))

    def test_relative_link_targets_exist(self):
        for path in DOCS:
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", read(path)):
                if target.startswith(("https://", "http://", "#")):
                    continue
                with self.subTest(path=path, target=target):
                    resolved = (ROOT / path).parent / target.split("#", 1)[0]
                    self.assertTrue(resolved.exists(), str(resolved))

    def test_sdk_examples_have_source_evidence(self):
        sources = (
            "funasr/auto/auto_model.py",
            "funasr/models/seaco_paraformer/model.py",
            "funasr/models/fsmn_vad_streaming/model.py",
            "funasr/download/download_model_from_hub.py",
            "funasr/utils/postprocess_hotwords.py",
        )
        literals = {
            node.value
            for source in sources
            for node in ast.walk(ast.parse(read(source)))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertIn('"AutoModel": ("funasr.auto.auto_model", "AutoModel")', read("funasr/__init__.py"))
        aliases = ast.parse(read("funasr/download/name_maps_from_hub.py"))
        ms_map = next(
            ast.literal_eval(node.value) for node in aliases.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "name_maps_ms" for target in node.targets)
        )
        for language, code in fences(read("docs/tutorial/README.md")):
            if language != "python":
                continue
            for node in ast.walk(ast.parse(code)):
                if isinstance(node, ast.ImportFrom) and node.module == "funasr":
                    self.assertEqual([alias.name for alias in node.names], ["AutoModel"])
                if not isinstance(node, ast.Call):
                    continue
                is_constructor = isinstance(node.func, ast.Name) and node.func.id == "AutoModel"
                is_generate = isinstance(node.func, ast.Attribute) and node.func.attr == "generate"
                if not (is_constructor or is_generate):
                    continue
                for keyword in node.keywords:
                    if keyword.arg != "input":
                        self.assertIn(keyword.arg, literals)
                    if keyword.arg in {"model", "vad_model", "punc_model"}:
                        self.assertIn(ast.literal_eval(keyword.value), ms_map)
        self.assertIn("speech_seaco_paraformer", ms_map["paraformer-zh"])
        sample = "https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_zh.wav"
        self.assertIn(sample, read("examples/industrial_data_pretraining/paraformer/demo.py"))
        self.assertIn(sample, read("docs/tutorial/README.md"))

    def test_installation_distinguishes_metadata_and_offline_limits(self):
        setup = read("setup.py")
        self.assertIn('python_requires=">=3.7.0"', setup)
        self.assertIn('"modelscope"', setup)
        self.assertIn('"huggingface_hub"', setup)
        self.assertIn("setuptools.build_meta", read("pyproject.toml"))
        self.assertTrue(read("funasr/version.txt").strip())
        loader = ast.parse(read("funasr/download/download_model_from_hub.py"))
        helper = next(node for node in loader.body if isinstance(node, ast.FunctionDef) and node.name == "get_or_download_model_dir_hf")
        download = next(node for node in ast.walk(helper) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "snapshot_download")
        self.assertFalse(download.keywords, "HF revision caveat needs review after helper changes")
        for path in PAIRS[0]:
            text = read(path)
            for marker in ("PyPI", "python -m pip install -e .", "sys.executable", "funasr.__file__", "pip check", "disable_update=True", "trust_remote_code=False", "snapshot_download(model)", "model_revision", "MIT"):
                self.assertIn(marker, text)

    def test_runtime_tags_have_independent_repository_evidence(self):
        evidence = "\n".join(read(path) for path in (
            "runtime/docs/SDK_advanced_guide_offline.md",
            "runtime/docs/SDK_advanced_guide_offline_gpu.md",
            "runtime/docs/SDK_advanced_guide_online.md",
            "runtime/dockerfile/Dockerfile.online.cpu",
        ))
        pattern = r"registry\.cn-hangzhou\.aliyuncs\.com/funasr_repo/funasr:[a-z0-9.-]+"
        for path in PAIRS[1]:
            images = re.findall(pattern, read(path))
            self.assertGreaterEqual(len(set(images)), 3)
            for image in images:
                self.assertIn(image, evidence)
            for language, code in fences(read(path)):
                if language == "sh":
                    self.assertNotIn("--privileged", code)
                    self.assertNotIn("-v /root", code)
                    self.assertNotIn("curl ", code)
            self.assertIn("-f runtime/dockerfile/Dockerfile.online.cpu", read(path))
            self.assertIn("funasr-online-cpu:local", evidence)

    def test_learning_flow_keeps_boundaries_and_advanced_entrypoints(self):
        for path in PAIRS[2]:
            text = read(path)
            for marker in ("sentence_info", 'sentence.get("spk")', "batch_size_s", "batch_size_threshold_s", "max_single_segment_time", "hotword", "hotwords", "language", "9600", "OpenMOSS", "finetune.sh", "infer_from_local.sh", "export.py", "model_zoo/", "Tables"):
                self.assertIn(marker, text)
            self.assertNotIn("remote_code=\"./model.py\"", text)
        for anchor in ("Inference", "Training", "Export", "new-model-registration-tutorial"):
            self.assertIn('name="' + anchor + '"', read(PAIRS[2][0]))
            self.assertIn('id="' + anchor + '"', read(PAIRS[2][0]))


if __name__ == "__main__":
    unittest.main()
