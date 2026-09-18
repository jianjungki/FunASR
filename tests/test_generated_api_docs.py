"""Exercise API generation without overwriting published page artifacts."""

import ast
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = '''class Example:
    """Example documentation with <escaped> content."""

    def generate(self, input, **kwargs):
        """Return input unchanged."""
        return input


def helper(value):
    """A helper function."""
    return value
'''.replace("A helper function.", "A helper function. " + "longword" * 100)


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.sources = []
        self.in_pre = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))
        if tag == "pre":
            self.in_pre = True
            self.sources.append("")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_pre = False

    def handle_data(self, data):
        if self.in_pre:
            self.sources[-1] += data

    def with_class(self, name):
        return [(tag, attrs) for tag, attrs in self.elements
                if name in attrs.get("class", "").split()]


class GeneratedApiDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="funasr-api-tests-")
        cls.repo = Path(cls.temp.name)
        (cls.repo / "scripts").mkdir()
        (cls.repo / "funasr/auto").mkdir(parents=True)
        (cls.repo / "funasr/auto/auto_model.py").write_text(FIXTURE)
        shutil.copy2(ROOT / "scripts/gen_api_docs.py", cls.repo / "scripts")
        css = ROOT / "gh-pages-output/api-reference.css"
        if css.exists():
            (cls.repo / "gh-pages-output").mkdir()
            shutil.copy2(css, cls.repo / "gh-pages-output")
        result = subprocess.run(
            [sys.executable, str(cls.repo / "scripts/gen_api_docs.py")],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.html = (cls.repo / "gh-pages-output/api.html").read_text()
        cls.page = Page(cls.html)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_existing_numeric_anchors_and_source_are_preserved(self):
        details = self.page.with_class("api-detail")
        self.assertEqual([attrs["id"] for _, attrs in details], ["e1", "e2", "e3"])
        tree = ast.parse(FIXTURE)
        lines = FIXTURE.splitlines(keepends=True)
        def preview(node):
            return "".join(lines[node.lineno - 1:min(node.lineno + 29, node.end_lineno)])
        cls, helper = tree.body
        method = cls.body[1]
        self.assertEqual(self.page.sources, [preview(cls), preview(method), preview(method), preview(helper)])
        self.assertIn("Example documentation with &lt;escaped&gt; content.", self.html)
        self.assertIn("funasr/auto/auto_model.py#L4", self.html)

    def test_group_controls_are_accessible_buttons(self):
        ids = {attrs["id"] for _, attrs in self.page.elements if "id" in attrs}
        controls = self.page.with_class("l1-title") + self.page.with_class("l2-title")
        self.assertTrue(controls)
        for tag, attrs in controls:
            self.assertEqual(tag, "button")
            self.assertEqual(attrs.get("type"), "button")
            self.assertIn(attrs.get("aria-expanded"), {"true", "false"})
            self.assertIn(attrs.get("aria-controls"), ids)
            self.assertNotIn("onclick", attrs)

    def test_entry_links_search_and_landmarks(self):
        for tag, attrs in self.page.with_class("l3-item"):
            self.assertEqual(tag, "a")
            self.assertEqual(attrs.get("href"), "#" + attrs["data-target"])
            self.assertNotIn("onclick", attrs)
        self.assertTrue(any(tag == "main" for tag, _ in self.page.elements))
        search = self.page.with_class("sb-search")[0][1]
        self.assertTrue(search.get("aria-label") or any(
            tag == "label" and attrs.get("for") == search.get("id")
            for tag, attrs in self.page.elements
        ))
        self.assertNotIn("Click source code to expand", self.html)

    def test_independent_local_responsive_stylesheet(self):
        styles = [attrs["href"] for tag, attrs in self.page.elements
                  if tag == "link" and attrs.get("rel") == "stylesheet"]
        self.assertEqual(styles, ["api-reference.css"])
        css = (self.repo / "gh-pages-output/api-reference.css").read_text()
        for contract in (":focus-visible", "minmax(0, 1fr)", "min-width: 0", "overflow-wrap: anywhere", "@media", "[hidden]"):
            self.assertIn(contract, css)

    def test_script_syntax_and_hash_fallback(self):
        script = re.search(r"<script>(.*?)</script>", self.html, re.S).group(1)
        self.assertIn("hashchange", script)
        self.assertIn("aria-current", script)
        if not shutil.which("node"):
            self.skipTest("Node.js is required for JavaScript execution")
        # Execute the real routing function against a minimal DOM, including
        # malformed hashes and IDs belonging to non-entry elements.
        harness = r'''
const assert = require('node:assert/strict');
const listeners = {};
function element(id) {
  const attrs = {};
  return {id, hidden: false, textContent: id, dataset: {target: id},
    classList: {contains: name => name === 'api-detail'},
    setAttribute: (key, value) => attrs[key] = value,
    removeAttribute: key => delete attrs[key],
    getAttribute: key => attrs[key],
    addEventListener() {}, closest() {return null;},
    querySelector() {return {textContent: id};},
    focus() {}, scrollIntoView() {}};
}
const detail = element('e1'), link = element('e1');
const welcomeNode = element('api-welcome');
const searchNode = {...element('api-search'), value: ''};
const empty = element('search-empty');
global.document = {
  title: '',
  querySelector(selector) {return selector === '.skip-link' ? element('skip-link') : null;},
  getElementById(id) {return {e1: detail, 'api-welcome': welcomeNode, 'api-search': searchNode, 'search-empty': empty}[id] || null;},
  querySelectorAll(selector) {
    if (selector === '.api-detail') return [detail];
    if (selector === '.l3-item') return [link];
    return [];
  }
};
global.window = {location: {hash: '#invalid'}, addEventListener(name, fn) {listeners[name] = fn;}};
'''
        assertions = r'''
assert.equal(welcome.hidden, false);
assert.equal(detail.hidden, true);
for (const id of ['e1', 'missing', 'api-welcome', '%ZZ', '"][data-target]']) {
  showEntry(id);
  assert.equal(detail.hidden, id !== 'e1');
  assert.equal(welcome.hidden, id === 'e1');
}
window.location.hash = '#e1'; listeners.hashchange();
assert.equal(detail.hidden, false);
assert.equal(link.getAttribute('aria-current'), 'true');
window.location.hash = ''; listeners.hashchange();
assert.equal(welcome.hidden, false);
assert.equal(link.getAttribute('aria-current'), undefined);
console.log('hash routing passed');
'''
        result = subprocess.run(["node", "-"], input=harness + script + assertions,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_full_checkout_generation_to_isolated_output(self):
        with tempfile.TemporaryDirectory(prefix="funasr-api-source-") as directory:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/gen_api_docs.py"), "--output-dir", directory],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            output = Path(directory)
            self.assertTrue((output / "api-reference.css").is_file())
            page = Page((output / "api.html").read_text())
            entries = page.with_class("api-detail")
            self.assertGreater(len(entries), 100)
            # New modules may be grouped beside old modules in navigation while
            # receiving IDs after legacy entries to preserve existing deep links.
            self.assertEqual(sorted((attrs["id"] for _, attrs in entries), key=lambda value: int(value[1:])),
                             [f"e{i}" for i in range(1, len(entries) + 1)])

    def test_skip_link_preserves_selection_playwright(self):
        try:
            from playwright.sync_api import expect, sync_playwright
        except ImportError:
            self.skipTest("Playwright is required for skip-link interaction regression")
        cache = Path.home() / ".cache/ms-playwright"
        browsers = sorted(cache.glob("chromium_headless_shell-*/chrome-linux*/headless_shell"), reverse=True)
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=str(browsers[0]) if browsers else None,
                headless=True, args=["--no-sandbox"], timeout=15000,
            )
            try:
                for width, activation in ((1440, "keyboard"), (390, "click")):
                    with self.subTest(width=width, activation=activation):
                        context = browser.new_context(viewport={"width": width, "height": 900})
                        try:
                            page = context.new_page()
                            page.goto((self.repo / "gh-pages-output/api.html").as_uri() + "#e3")
                            detail = page.locator("#e3")
                            expect(detail).to_be_visible()
                            detail.locator("summary").click()
                            title, url = page.title(), page.url
                            skip = page.get_by_role("link", name="Skip to content")
                            skip.focus()
                            if activation == "keyboard":
                                page.keyboard.press("Enter")
                            else:
                                skip.click()
                            expect(page.locator("#api-content")).to_be_focused()
                            expect(page).to_have_url(url, timeout=1000)
                            expect(detail).to_be_visible()
                            expect(page.locator("#api-welcome")).to_be_hidden()
                            expect(page.locator('[data-target="e3"]')).to_have_attribute("aria-current", "true")
                            self.assertEqual(page.title(), title)
                            self.assertTrue(detail.locator("details").evaluate("node => node.open"))
                        finally:
                            context.close()
            finally:
                browser.close()

    def test_browser_navigation_and_responsive_overflow(self):
        cache = Path.home() / ".cache/ms-playwright"
        candidates = sorted(cache.glob("chromium_headless_shell-*/chrome-linux*/headless_shell"), reverse=True)
        candidates += [shutil.which("chromium"), shutil.which("google-chrome")]
        candidates += sorted(cache.glob("chromium-*/chrome-linux*/chrome"), reverse=True)
        browser = next((str(path) for path in candidates if path), None)
        if not browser:
            self.skipTest("Chromium is required for browser layout verification")
        check = r'''
<script>
window.addEventListener('load', () => {
  const errors = [];
  const check = (condition, label) => {if (!condition) errors.push(label);};
  check(innerWidth === EXPECTED_WIDTH, 'requested viewport width');
  const group = document.querySelector('.l1-title');
  check(group.getAttribute('aria-expanded') === 'false', 'initial collapsed state');
  group.click();
  check(group.getAttribute('aria-expanded') === 'true', 'button expansion');
  check(!document.getElementById(group.getAttribute('aria-controls')).hidden, 'expanded panel');
  group.click();
  const input = document.getElementById('api-search');
  input.value = 'no-such-entry'; input.dispatchEvent(new Event('input'));
  check(!document.getElementById('search-empty').hidden, 'empty search state');
  input.value = ''; input.dispatchEvent(new Event('input'));
  check(group.getAttribute('aria-expanded') === 'false', 'restore expansion');
  document.querySelector('[href="#e3"]').click();
  const detail = document.getElementById('e3');
  check(!detail.hidden, 'selected entry');
  check(document.activeElement === detail, 'entry keyboard focus');
  check(group.getAttribute('aria-expanded') === 'true', 'reveal ancestors');
  detail.querySelector('details').open = true;
  const source = detail.querySelector('pre');
  check(source.scrollWidth > source.clientWidth, 'long source scrolls internally');
  check(document.documentElement.scrollWidth <= innerWidth, 'page horizontal overflow');
  for (const selector of ['.api-sidebar', '.api-content']) {
    const box = document.querySelector(selector).getBoundingClientRect();
    check(box.left >= 0 && box.right <= innerWidth + 1, selector + ' viewport bounds');
  }
  showEntry('api-welcome');
  check(!document.getElementById('api-welcome').hidden, 'invalid hash fallback');
  showEntry('e3');
  const result = document.createElement('output');
  result.id = 'browser-verification'; result.textContent = errors.length ? errors.join('; ') : 'PASS';
  document.body.append(result);
});
</script>
'''
        page = self.repo / "gh-pages-output/browser-check.html"
        for width, height in ((1440, 1000), (390, 844), (320, 740)):
            with self.subTest(width=width):
                page.write_text(self.html.replace("</body>", check.replace("EXPECTED_WIDTH", str(width)) + "</body>"))
                result = subprocess.run(
                    [browser, "--headless", "--no-sandbox", "--disable-gpu",
                     "--no-first-run", "--disable-background-networking",
                     f"--user-data-dir={self.repo / ('browser-' + str(width))}",
                     f"--window-size={width},{height}", "--force-device-scale-factor=1",
                     "--virtual-time-budget=1000", "--dump-dom", page.as_uri()],
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                match = re.search(r'<output id="browser-verification">(.*?)</output>', result.stdout)
                self.assertIsNotNone(match, result.stderr)
                self.assertEqual(match.group(1), "PASS")


if __name__ == "__main__":
    unittest.main()
