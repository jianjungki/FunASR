"""Source-only API signatures must describe the callable without importing it."""

import html
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = '''raise RuntimeError("Documentation must never import this module")

class Example:
    def __init__(self, model: str, *, device: str = "cpu"):
        """Construct without loading weights in the documentation builder."""

    def generate(self, input, input_len=None, progress_callback=None, **cfg):
        pass

    def typed(this, value: "Tensor", /, limit: int = 3, *items: str,
              required: bool, label: str = "<tag>", **options: int) -> "Result":
        pass

    @staticmethod
    def static(self: int = 5, *, enabled=False):
        pass

    @classmethod
    def factory(cls, value=None):
        pass

def helper(value=explode(), *, required, optional=None):
    pass
'''


def headings(page):
    return [html.unescape(re.sub(r"<[^>]*>", "", item))
            for item in re.findall(r"<h2>(.*?)</h2>", page, re.S)]


class ApiSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="funasr-signatures-")
        cls.repo = Path(cls.temp.name)
        for directory in ("scripts", "funasr/auto", "gh-pages-output"):
            (cls.repo / directory).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "scripts/gen_api_docs.py", cls.repo / "scripts")
        shutil.copy2(ROOT / "gh-pages-output/api-reference.css", cls.repo / "gh-pages-output")
        (cls.repo / "funasr/auto/auto_model.py").write_text(FIXTURE)
        (cls.repo / "funasr/register.py").write_text("def register(value=None): pass\n")
        shutil.copy2(ROOT / "funasr/auto/auto_model_vllm.py", cls.repo / "funasr/auto")
        result = subprocess.run([sys.executable, str(cls.repo / "scripts/gen_api_docs.py")],
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.pages = [(cls.repo / "gh-pages-output" / name).read_text()
                     for name in ("api.html",)]

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_defaults_are_visible_without_evaluation(self):
        for page in self.pages:
            self.assertIn("Example.generate(input, input_len=None, progress_callback=None, **cfg)", headings(page))
            self.assertIn("helper(value=explode(), *, required, optional=None)", headings(page))

    def test_all_argument_kinds_annotations_and_return(self):
        expected = 'Example.typed(value: "Tensor", /, limit: int = 3, *items: str, required: bool, label: str = "<tag>", **options: int) -> "Result"'
        for page in self.pages:
            self.assertIn(expected, headings(page))
            self.assertIn('&lt;tag&gt;', page)
            self.assertNotIn('<tag>', page)

    def test_static_and_classmethod_receivers(self):
        for page in self.pages:
            self.assertIn("Example.static(self: int = 5, *, enabled=False)", headings(page))
            self.assertIn("Example.factory(value=None)", headings(page))

    def test_constructor_is_public_without_a_new_numeric_anchor(self):
        for page in self.pages:
            self.assertIn('Example(model: str, *, device: str = "cpu")', headings(page))
            self.assertIn('Construct without loading weights', page)
            # Adding constructor details and a vLLM module must not move old links.
            old = re.findall(r'class="api-detail"[^>]*id="(e\d+)"[^>]*>.*?<h2>(.*?)</h2>', page, re.S)
            by_id = {key: html.unescape(re.sub(r'<[^>]*>', '', title)) for key, title in old}
            self.assertTrue(by_id['e1'].startswith('Example('))
            self.assertTrue(by_id['e2'].startswith('Example.generate('))
            self.assertTrue(by_id['e6'].startswith('helper('))
            self.assertTrue(by_id['e7'].startswith('register('))

    def test_real_vllm_constructor_and_discovery(self):
        for page in self.pages:
            matches = [h for h in headings(page) if h.startswith('AutoModelVLLM(')]
            self.assertEqual(len(matches), 1)
            self.assertIn('model: str, hub: str = "ms", device: str = "cuda:0"', matches[0])
            self.assertIn('tensor_parallel_size: int = 1', matches[0])
            self.assertIn('enforce_eager: bool = False, **kwargs)', matches[0])
            self.assertRegex(page, r'class="entry-link">AutoModelVLLM ')
            self.assertIn('funasr/auto/auto_model_vllm.py#L', page)

    def test_actual_auto_model_generate_defaults(self):
        with tempfile.TemporaryDirectory(prefix="funasr-signature-real-") as output:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/gen_api_docs.py'),
                                     '--output-dir', output], capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in ('api.html',):
                self.assertIn('AutoModel.generate(input, input_len=None, progress_callback=None, **cfg)',
                              headings((Path(output) / name).read_text()))


if __name__ == '__main__':
    unittest.main()
