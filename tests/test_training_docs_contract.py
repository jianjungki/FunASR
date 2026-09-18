"""Source-backed docs checks, without model downloads or GPU training."""

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DOCS = (
    "training.md",
    "training_zh.md",
    "model_registration.md",
    "model_registration_zh.md",
)


def blocks(name, language):
    text = (ROOT / "docs" / name).read_text(encoding="utf-8")
    return re.findall(rf"^```{language}\n(.*?)^```", text, re.M | re.S)


class TrainingDocsContractTests(unittest.TestCase):
    def test_relative_repository_links(self):
        for name in DOCS:
            document = ROOT / "docs" / name
            text = document.read_text(encoding="utf-8")
            links = re.findall(r"\[[^\]\n]+\]\(([^)]+)\)", text)
            self.assertGreater(len(links), 5)
            for target in links:
                parsed = urlsplit(target)
                if parsed.scheme or not parsed.path:
                    continue
                resolved = (document.parent / unquote(parsed.path)).resolve()
                with self.subTest(document=name, target=target):
                    self.assertTrue(resolved.is_relative_to(ROOT))
                    self.assertTrue(resolved.exists(), target)

    def test_python_json_and_shell_syntax(self):
        for name in DOCS:
            for source in blocks(name, "python"):
                ast.parse(source, filename=name)
            for source in blocks(name, "json"):
                self.assertIsInstance(json.loads(source), dict)
            for source in blocks(name, "bash"):
                result = subprocess.run(
                    ["bash", "-n"], input=source, text=True,
                    capture_output=True, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_bilingual_executable_examples_match(self):
        for english, chinese in (
            ("training.md", "training_zh.md"),
            ("model_registration.md", "model_registration_zh.md"),
        ):
            for language in ("python", "bash", "json"):
                self.assertEqual(blocks(english, language), blocks(chinese, language))

    def test_documented_commands_reference_real_scripts(self):
        for relative in (
            "funasr/bin/train_ds.py",
            "funasr/datasets/audio_datasets/scp2jsonl.py",
            "examples/industrial_data_pretraining/fun_asr_nano/tools/scp2jsonl.py",
        ):
            self.assertTrue((ROOT / relative).is_file(), relative)
        for name in DOCS:
            text = (ROOT / "docs" / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"/(?:Users|home)/[^\s]+")

    def test_loader_and_registry_source_contract(self):
        loader = ast.parse(
            (ROOT / "funasr/download/download_model_from_hub.py").read_text()
        )
        functions = {
            node.name: node for node in loader.body
            if isinstance(node, ast.FunctionDef)
        }
        for name, imports_code in (("download_from_ms", True), ("download_from_hf", False)):
            calls = {
                node.func.id for node in ast.walk(functions[name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            self.assertEqual("import_module_from_path" in calls, imports_code)
        source = (ROOT / "funasr/register.py").read_text()
        self.assertIn("registry[registry_key] = target_class", source)
        auto = (ROOT / "funasr/auto/auto_model.py").read_text()
        self.assertIn('if "model_conf" not in kwargs:', auto)
        self.assertIn("res = model.inference(**batch, **kwargs)", auto)
        self.assertIn("next(model.parameters()).device", auto)

    def test_no_download_toy_against_checkout(self):
        source = blocks("model_registration.md", "python")[0]
        # A real file is necessary for the registry's inspect metadata.
        with tempfile.TemporaryDirectory(prefix="funasr-docs-contract-") as temp:
            path = Path(temp) / "custom_model_demo.py"
            path.write_text(source, encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
            result = subprocess.run(
                [sys.executable, str(path)], cwd=ROOT, env=env,
                text=True, capture_output=True, timeout=90,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("['hello', 'world']", result.stdout)


if __name__ == "__main__":
    unittest.main()
