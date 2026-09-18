"""Source-backed service docs checks without loading models or starting servers."""

import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/openai_api"
READMES = [EXAMPLE / name for name in ("README.md", "README_zh.md", "README_ja.md", "README_ko.md")]
DOCS = [EXAMPLE / "CLIENTS.md", *READMES]
PACKAGED = ROOT / "funasr/bin/_server_app.py"
WORKFLOW_DOCS = [EXAMPLE / name for name in ("WORKFLOWS.md", "WORKFLOWS_zh.md")]
JAVASCRIPT_DOCS = [EXAMPLE / name for name in ("JAVASCRIPT.md", "JAVASCRIPT_zh.md")]
SECURITY_DOCS = [EXAMPLE / name for name in ("SECURITY.md", "SECURITY_zh.md")]

# Frozen from the two pre-edit workflow guides, not translated from one language.
WORKFLOW_HEADINGS = {
    "WORKFLOWS.md": "Low-code Workflow Recipes for the FunASR OpenAI-Compatible API|Server preflight|Postman smoke test|Multipart HTTP request|Dify custom tool or HTTP node|Direct file upload path|Audio URL path|n8n HTTP Request node|n8n OpenAI Audio node|Webhook worker pattern|Production guardrails|Troubleshooting",
    "WORKFLOWS_zh.md": "FunASR OpenAI 兼容 API 低代码工作流配方|服务预检|Postman smoke test|Multipart HTTP 请求|Dify 自定义工具或 HTTP 节点|直接上传文件|音频 URL 转写|n8n HTTP Request 节点|n8n OpenAI Audio 节点|Webhook worker 模式|生产环境护栏|故障排查",
}

# Frozen from the pre-edit README inventory, excluding fenced code comments.
LEGACY_HEADINGS = {
    "README.md": "FunASR OpenAI-Compatible API Server|API Contract|Quick Start|End-to-end smoke test|Browser demo with Gradio|Usage with OpenAI SDK (Python)|Usage with curl|Available Models|API Endpoints|Agent Framework Integration|LangChain Example|Docker Deployment|Kubernetes Deployment|Configuration|Troubleshooting",
    "README_zh.md": "FunASR OpenAI 兼容 API 服务|API Contract|快速开始|端到端 smoke test|Gradio 浏览器 Demo|使用 OpenAI SDK|使用 curl|可用模型|API 端点|Agent 与低代码工作流|Docker 部署|Kubernetes 部署|配置|故障排查",
    "README_ja.md": "FunASR OpenAI 互換 API サーバー|クイックスタート|エンドツーエンド smoke test|Gradio ブラウザデモ|OpenAI SDK で使う|curl で使う|利用できるモデル|API エンドポイント|エージェントとローコードワークフロー|Docker デプロイ|Kubernetes デプロイ|設定|トラブルシューティング",
    "README_ko.md": "FunASR OpenAI 호환 API 서버|빠른 시작|엔드투엔드 smoke test|Gradio 브라우저 데모|OpenAI SDK로 사용하기|curl로 사용하기|사용 가능한 모델|API 엔드포인트|에이전트 및 로우코드 워크플로|Docker 배포|Kubernetes 배포|설정|문제 해결",
}


def supported_module_command(args):
    """Allow only the documented environment setup commands, not arbitrary modules."""
    return args in (["python3.11", "-m", "venv", ".venv"],
                    ["python", "-m", "pip", "install", "-e", "."],
                    ["python", "-m", "pip", "install", "fastapi", "uvicorn", "python-multipart"],
                    ["python", "-m", "pip", "install", "openai"],
                    ["python", "-m", "pip", "install", "gradio"],
                    ["python", "-m", "pip", "check"])


def blocks(text, language):
    return re.findall(r"^```" + language + r"\n(.*?)^```", text, re.M | re.S)


def tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def function(path, name):
    return next(node for node in ast.walk(tree(path))
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name)


def form_defaults(node):
    defaults = {}
    for arg, value in zip(node.args.args[-len(node.args.defaults):], node.args.defaults):
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "Form":
            defaults[arg.arg] = ast.literal_eval(next(
                keyword.value for keyword in value.keywords if keyword.arg == "default"))
    return defaults


def headings(text):
    text = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)
    result = set()
    counts = {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", text, re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(f"{slug}-{count}" if count else slug)
    return result


class ServiceDocsContract(unittest.TestCase):
    def test_preserves_existing_readme_headings(self):
        for path in READMES:
            text = path.read_text(encoding="utf-8")
            source = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)
            actual = re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", source, re.M)
            expected = LEGACY_HEADINGS[path.name].split("|")
            self.assertEqual([value for value in actual if value in expected], expected, path.name)

    def test_long_contract_and_model_explanations_are_readable_lists(self):
        model_headings = ("Available Models", "可用模型", "利用できるモデル", "사용 가능한 모델")
        configs = next(node for node in ast.walk(tree(EXAMPLE / "server.py"))
                       if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                       and target.id == "MODEL_CONFIGS" for target in node.targets))
        aliases = [ast.literal_eval(key) for key in configs.value.keys]
        for path, model_heading in zip(READMES, model_headings):
            text = path.read_text(encoding="utf-8")
            for heading in ("API Contract", model_heading):
                section = text.split("## " + heading + "\n", 1)[1].split("\n## ", 1)[0]
                self.assertNotRegex(section, r"(?m)^\|", path.name)
                if heading == model_heading:
                    self.assertEqual(re.findall(r"(?m)^- `([^`]+)`", section), aliases, path.name)

    def test_module_command_allowlist_rejects_unchecked_variants(self):
        self.assertTrue(supported_module_command(["python", "-m", "pip", "check"]))
        for args in (["python", "-m", "missing"], ["python", "-m", "pip", "uninstall", "funasr"],
                     ["python3.11", "-m", "venv"], ["python", "-m", "pip", "check", "--bogus"]):
            self.assertFalse(supported_module_command(args))

    def test_readme_checkout_and_loopback_recipes(self):
        for path in READMES:
            text = path.read_text(encoding="utf-8")
            quick_start = blocks(text, "bash")[0]
            ordered = ["git clone https://github.com/modelscope/FunASR.git FunASR-api", "cd FunASR-api",
                       "git checkout --detach d91d961e37a005837b1523bcc6b09f087877be54",
                       "python3.11 -m venv .venv", "source .venv/bin/activate",
                       "python -m pip install -e .", "python -m pip install fastapi uvicorn python-multipart",
                       "python -m pip check", "cd examples/openai_api",
                       "python server.py --host 127.0.0.1 --model sensevoice --device cpu --port 8000"]
            positions = [quick_start.index(command) for command in ordered]
            self.assertEqual(positions, sorted(positions), path.name)
            self.assertIn("SECURITY", text[:text.index("```bash")])
            for marker in ("/v1/models", "/openapi.json", "Fun-ASR-MLT-Nano", '--model-path', '--hub',
                           'model="custom"', 'whisper-1', 'sentence_info', 'ctc_timestamps', '0.0.0.0'):
                self.assertIn(marker, text, path.name)
            self.assertIn("FUNASR_HOST_PORT=127.0.0.1:8000 docker compose up --build", text)
            for code in blocks(text, "bash"):
                for line in code.replace("\\\n", " ").splitlines():
                    args = shlex.split(line, comments=True)
                    if args[:2] == ["docker", "run"]:
                        self.assertEqual(args[args.index("-p") + 1], "127.0.0.1:8000:8000")
            self.assertNotRegex(text, r"(?:170|120|3\.6)[x×倍]")

    def test_readme_clients_close_files_and_use_supported_form_fields(self):
        allowed = set(form_defaults(function(EXAMPLE / "server.py", "transcribe"))) | {"file"}
        for path in READMES:
            formats = []
            for code in blocks(path.read_text(encoding="utf-8"), "python"):
                parsed = ast.parse(code)
                calls = [node for node in ast.walk(parsed) if isinstance(node, ast.Call)
                         and isinstance(node.func, ast.Attribute) and node.func.attr == "create"]
                for call in calls:
                    kwargs = {kw.arg: kw.value for kw in call.keywords}
                    formats.append(ast.literal_eval(kwargs["response_format"]) if "response_format" in kwargs else None)
                    self.assertEqual(ast.literal_eval(kwargs["model"]), "sensevoice")
                    self.assertLessEqual(set(kwargs), allowed)
                    self.assertIsInstance(kwargs["file"], ast.Name)
                    contexts = [node for node in ast.walk(parsed) if isinstance(node, ast.With)
                                and call in list(ast.walk(node))]
                    self.assertTrue(any(isinstance(item.optional_vars, ast.Name)
                                        and item.optional_vars.id == kwargs["file"].id
                                        and isinstance(item.context_expr, ast.Call)
                                        and isinstance(item.context_expr.func, ast.Name)
                                        and item.context_expr.func.id == "open"
                                        and len(item.context_expr.args) == 2
                                        and ast.literal_eval(item.context_expr.args[1]) == "rb"
                                        for node in contexts for item in node.items))
            self.assertGreaterEqual(len(formats), 2, path.name)
            self.assertEqual(set(formats), {None, "verbose_json"}, path.name)

    def test_relative_links_and_owned_page_anchors(self):
        owned = {path.resolve() for path in DOCS}
        for path in DOCS:
            text = path.read_text(encoding="utf-8")
            self.assertIn("## API Contract", text)
            self.assertIn("](#api-contract)", text)
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                parts = urlsplit(link)
                if parts.scheme or parts.netloc:
                    continue
                target = (path.parent / unquote(parts.path)).resolve() if parts.path else path.resolve()
                self.assertIn(ROOT.resolve(), target.parents)
                self.assertNotIn(".mcp-tasks", target.parts)
                self.assertTrue(target.exists(), f"{path.name}: {link}")
                if parts.fragment and target in owned:
                    self.assertIn(unquote(parts.fragment), headings(target.read_text(encoding="utf-8")), link)

    def test_sdk_links_and_unsupported_claims(self):
        for path in DOCS:
            text = path.read_text(encoding="utf-8")
            for link in ("../../docs/python_api.md", "../../docs/python_api_zh.md"):
                self.assertIn(f"]({link})", text)
            for marker in ("spk=true", "segments=[]", "--model auto", "OpenAI API"):
                self.assertIn(marker, text)
            for stale in ("170x realtime", "120x realtime", "3.6x realtime",
                          "Server starts in ~20s", "Works with **any agent framework**",
                          "Fast default with language, emotion, and event tags",
                          "Returns: text, segments (with start/end/speaker), duration"):
                self.assertNotIn(stale, text)

    def test_python_and_shell_examples_are_syntactically_valid(self):
        for path in DOCS:
            text = path.read_text(encoding="utf-8")
            for index, code in enumerate(blocks(text, "python")):
                compile(code, f"{path}:{index}", "exec")
            for index, code in enumerate(blocks(text, "bash")):
                result = subprocess.run(["bash", "-n"], input=code, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, f"{path}:{index}: {result.stderr}")

    def test_local_script_commands_and_options_match_source(self):
        for path in DOCS:
            text = path.read_text(encoding="utf-8")
            if path.name.startswith("README"):
                quick_start = blocks(text, "bash")[0]
                self.assertIn("cd examples/openai_api", quick_start)
                self.assertLess(quick_start.index("cd examples/openai_api"), quick_start.index("python server.py"))
            for code in blocks(text, "bash"):
                for line in code.replace("\\\n", " ").splitlines():
                    args = shlex.split(line, comments=True)
                    if len(args) < 2 or args[0] not in ("python", "python3.11", "bash"):
                        continue
                    if args[1] == "-m":
                        self.assertTrue(supported_module_command(args), args)
                        continue
                    script = EXAMPLE / args[1]
                    self.assertTrue(script.is_file(), str(script))
                    if args[0] != "python":
                        continue
                    options = {ast.literal_eval(arg) for node in ast.walk(tree(script))
                               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                               and node.func.attr == "add_argument"
                               for arg in node.args if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
                    for arg in args[2:]:
                        if arg.startswith("--"):
                            self.assertIn(arg.split("=", 1)[0], options, str(script))

    def test_form_defaults_and_alias_boundaries_match_source(self):
        example = form_defaults(function(EXAMPLE / "server.py", "transcribe"))
        packaged = form_defaults(function(PACKAGED, "transcribe"))
        self.assertEqual(example["model"], "sensevoice")
        self.assertNotIn("spk", example)
        self.assertEqual(packaged["model"], "fun-asr-nano")
        self.assertIs(packaged["spk"], False)
        for path, name, expected in ((EXAMPLE / "server.py", "MODEL_CONFIGS", True),
                                     (PACKAGED, "FALLBACK_CONFIGS", False)):
            assignment = next(node for node in ast.walk(tree(path))
                              if isinstance(node, ast.Assign) and any(
                                  isinstance(target, ast.Name) and target.id == name for target in node.targets))
            aliases = [ast.literal_eval(key) for key in assignment.value.keys]
            self.assertEqual("paraformer-en" in aliases, expected)

    def test_example_serializes_sentence_info_not_raw_sdk_timestamps(self):
        handler = function(EXAMPLE / "server.py", "transcribe")
        branch = next(node for node in ast.walk(handler) if isinstance(node, ast.If)
                      and isinstance(node.test, ast.Compare)
                      and isinstance(node.test.left, ast.Name)
                      and node.test.left.id == "response_format")

        class CaptureReturn(ast.NodeTransformer):
            def visit_Return(self, node):
                return ast.copy_location(ast.Assign(
                    targets=[ast.Name(id="response", ctx=ast.Store())], value=node.value), node)

        executable = ast.fix_missing_locations(CaptureReturn().visit(ast.Module(body=[branch], type_ignores=[])))
        clean = function(EXAMPLE / "server.py", "clean_text")
        namespace = {"re": re, "JSONResponse": lambda value: value, "response_format": "verbose_json",
                     "elapsed": 0.42, "language": None, "model": "sensevoice", "text": "hello"}
        exec(compile(ast.Module(body=[clean], type_ignores=[]), "clean-text", "exec"), namespace)
        raw_token = {"token": "hello", "start_time": 100, "end_time": 400}
        cases = [({"timestamp": [[100, 400]], "timestamps": [raw_token], "ctc_timestamps": [raw_token]}, []),
                 ({"sentence_info": [{"start": 100, "end": 400, "text": "<|HAPPY|>hello"}]},
                  [{"start": 0.1, "end": 0.4, "text": "hello", "speaker": None}])]
        for result, expected in cases:
            namespace["result"] = [result]
            exec(compile(executable, "example-verbose-branch", "exec"), namespace)
            self.assertEqual(namespace["response"]["segments"], expected)
            self.assertEqual(namespace["response"]["language"], "auto")
            self.assertEqual(namespace["response"]["duration"], 0.42)

    def test_workflow_alias_and_compose_host_binding_match_source(self):
        resolver = function(EXAMPLE / "server.py", "resolve_openai_transcription_model")
        namespace = {"N8N_OPENAI_MODEL_ALIAS": "whisper-1", "DEFAULT_MODEL": "sensevoice"}
        exec(compile(ast.Module(body=[resolver], type_ignores=[]), "workflow-alias", "exec"), namespace)
        self.assertEqual(namespace[resolver.name]("whisper-1"), "sensevoice")
        self.assertEqual(namespace[resolver.name]("paraformer"), "paraformer")
        compose = (EXAMPLE / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn('"${FUNASR_HOST_PORT:-8000}:8000"', compose)
        dockerfile = (EXAMPLE / "Dockerfile").read_text(encoding="utf-8")
        command = next(json.loads(line[4:]) for line in dockerfile.splitlines() if line.startswith("CMD "))
        args = shlex.split(command[-1])
        self.assertEqual(args[args.index("--host") + 1], "0.0.0.0")

    def test_startup_defaults_match_source(self):
        for path, expected in ((EXAMPLE / "server.py", "sensevoice"),
                               (ROOT / "funasr/bin/server.py", "auto")):
            option = next(node for node in ast.walk(tree(path)) if isinstance(node, ast.Call)
                          and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
                          and node.args and isinstance(node.args[0], ast.Constant)
                          and node.args[0].value == "--model")
            self.assertEqual(next(ast.literal_eval(kw.value) for kw in option.keywords
                                  if kw.arg == "default"), expected)
        startup = function(PACKAGED, "create_app")
        selection = next(node for node in ast.walk(startup) if isinstance(node, ast.IfExp)
                         and isinstance(node.body, ast.Constant) and node.body.value == "fun-asr-nano")
        for device, expected in (("cuda:0", "fun-asr-nano"), ("cpu", "sensevoice"), ("mps", "sensevoice")):
            self.assertEqual(eval(compile(ast.Expression(selection), str(PACKAGED), "eval"), {"device": device}), expected)

    def test_packaged_verbose_example_matches_real_builder(self):
        samples = [json.loads(code) for code in blocks(DOCS[0].read_text(encoding="utf-8"), "json")]
        self.assertEqual(len(samples), 3)
        namespace = {"resolve_transcription_language": lambda requested, result: requested or result["language"]}
        builder = function(PACKAGED, "build_openai_verbose_json")
        exec(compile(ast.Module(body=[builder], type_ignores=[]), str(PACKAGED), "exec"), namespace)
        result = {"text": "recognized speech", "language": "en", "duration": 3.2,
                  "segments": [{"start": 0.0, "end": 3.2, "text": "recognized speech"}]}
        self.assertEqual(namespace[builder.name](result), samples[1])
        self.assertNotIn("speaker", samples[1]["segments"][0])
        self.assertLessEqual(samples[1]["segments"][0]["end"], samples[1]["duration"])

    def test_example_verbose_sample_and_duration_meaning(self):
        samples = [json.loads(code) for code in blocks(DOCS[0].read_text(encoding="utf-8"), "json")]
        handler = function(EXAMPLE / "server.py", "transcribe")
        response = next(node for node in ast.walk(handler) if isinstance(node, ast.Dict)
                        and any(isinstance(key, ast.Constant) and key.value == "duration" for key in node.keys))
        expected = eval(compile(ast.Expression(response), "example-response", "eval"),
                        {"text": "recognized speech", "segments": [], "language": None,
                         "elapsed": 0.42, "model": "sensevoice"})
        self.assertEqual(expected, samples[2])
        source = PACKAGED.read_text(encoding="utf-8")
        self.assertIn("float(sf.info(audio_path).duration)", source)
        self.assertIn('"duration": len(audio_data) / sr', source)
        clients = DOCS[0].read_text(encoding="utf-8")
        self.assertIn("not audio duration", clients)
        self.assertIn("Audio duration in seconds", clients)
        self.assertIn("does not enable diarization", clients)


class WorkflowDocsContract(unittest.TestCase):
    def test_workflow_explanatory_sections_use_complete_readable_lists(self):
        sections = [
            (("Multipart HTTP request", "Multipart HTTP 请求"),
             ["Method", "URL", "Body type", "File field", "Text field", "Text field", "Timeout"],
             [("POST",), ("/v1/audio/transcriptions",), ("multipart/form-data",), ("`file`",),
              ("model=sensevoice",), ("response_format=verbose_json",), ("300",)]),
            (("n8n HTTP Request node", "n8n HTTP Request 节点"),
             ["Method", "URL", "Send Body", "Body Content Type", "Binary file field", "Additional form fields", "Response Format", "Timeout"],
             [("POST",), ("/v1/audio/transcriptions",), ("enabled",), ("Form-Data", "multipart"),
              ("`file`",), ("model=sensevoice", "response_format=verbose_json"), ("JSON",), ()]),
        ]
        symptoms = [
            ["Workflow can call `/health` but transcription fails", "`localhost` connection fails from Dify or n8n",
             "Response has no usable `segments`", "Requests time out", "First request is slow", "Unknown model alias"],
            ["工作流能访问 `/health`，但转写失败", "Dify 或 n8n 访问 `localhost` 失败", "响应中没有可用 `segments`",
             "请求超时", "第一次请求很慢", "模型别名未知"],
        ]
        fixes = [("multipart/form-data", "`file`"), ("Compose", "Kubernetes"),
                 ("sentence_info", "verbose_json"), ("HTTP timeout",), ("--model sensevoice", "/health"), ("/v1/models",)]
        for language, path in enumerate(WORKFLOW_DOCS):
            text = path.read_text(encoding="utf-8")
            cases = [*sections, (("Troubleshooting", "故障排查"), symptoms[language], fixes)]
            for titles, labels, tokens in cases:
                with self.subTest(path=path.name, section=titles[language]):
                    section = text.split("## " + titles[language] + "\n", 1)[1].split("\n## ", 1)[0]
                    self.assertNotRegex(section, r"(?m)^\s*\|")
                    self.assertNotRegex(section, r"(?i)<table\b")
                    lines = section.splitlines()
                    start = next((i for i, line in enumerate(lines) if line.startswith("- **")), None)
                    self.assertIsNotNone(start, "Missing explanation list")
                    items = []
                    for line in lines[start:]:
                        if not line.startswith("- "):
                            break
                        match = re.fullmatch(r"- \*\*(.+?):\*\* (.+)", line)
                        self.assertIsNotNone(match, line)
                        items.append(match.groups())
                    self.assertEqual([label for label, _ in items], labels)
                    for (_, value), required in zip(items, tokens):
                        for token in required:
                            self.assertIn(token, value)

    def test_preserves_workflow_headings_and_links(self):
        for path in WORKFLOW_DOCS:
            text = path.read_text(encoding="utf-8")
            source = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)
            actual = re.findall(r"^(#{1,6}) (.+)$", source, re.M)
            titles = WORKFLOW_HEADINGS[path.name].split("|")
            levels = [1, 2, 2, 2, 2, 3, 3, 2, 3, 2, 2, 2]
            self.assertEqual([(len(level), title) for level, title in actual], list(zip(levels, titles)))
            suffix = "_zh" if path.stem.endswith("_zh") else ""
            preserved = {"WORKFLOWS.md" if suffix else "WORKFLOWS_zh.md",
                         f"POSTMAN{suffix}.md", f"OPENAPI{suffix}.md", f"SECURITY{suffix}.md",
                         f"../../docs/moss_transcribe_diarize{suffix}.md"}
            links = set(re.findall(r"\[[^\]]+\]\(([^)]+)\)", text))
            self.assertLessEqual(preserved, links)
            for link in links:
                parts = urlsplit(link)
                if parts.scheme or parts.netloc:
                    continue
                target = (path.parent / unquote(parts.path)).resolve()
                self.assertIn(ROOT.resolve(), target.parents)
                self.assertNotIn(".mcp-tasks", target.parts)
                self.assertTrue(target.is_file(), link)
                if parts.fragment:
                    self.assertIn(unquote(parts.fragment), headings(target.read_text(encoding="utf-8")), link)

    def test_workflow_preflight_uses_prepared_loopback_server(self):
        options = {ast.literal_eval(arg) for node in ast.walk(tree(EXAMPLE / "server.py"))
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == "add_argument" for arg in node.args
                   if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
        for path in WORKFLOW_DOCS:
            text = path.read_text(encoding="utf-8")
            prefix = text.split("```bash", 1)[0]
            suffix = "_zh" if path.stem.endswith("_zh") else ""
            self.assertIn(f"](README{suffix}.md", prefix)
            self.assertIn(f"](SECURITY{suffix}.md)", prefix)
            self.assertIn(f"](../../docs/agent_integration{suffix}.md)", text)
            startup = blocks(text, "bash")[0]
            commands = [shlex.split(line, comments=True) for line in startup.splitlines() if line.strip()]
            self.assertIn(["source", "../../.venv/bin/activate"], commands)
            launches = [args for args in commands if args[:2] == ["python", "server.py"]]
            self.assertEqual(len(launches), 1)
            args = launches[0]
            for option, expected in (("--host", "127.0.0.1"), ("--model", "sensevoice"), ("--device", "cpu")):
                self.assertIn(option, args)
                self.assertEqual(args[args.index(option) + 1], expected)
            self.assertLessEqual({arg for arg in args if arg.startswith("--")}, options)

    def test_workflow_url_assignments_are_copyable_and_checks_are_explicit(self):
        for path in WORKFLOW_DOCS:
            codes = blocks(path.read_text(encoding="utf-8"), "bash")
            assignments = []
            for code in codes:
                self.assertNotRegex(code, r"<[^\n>]+>")
                result = subprocess.run(["bash", "-n"], input=code, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                for line in code.replace("\\\n", " ").splitlines():
                    args = shlex.split(line, comments=True)
                    if args[:1] == ["export"]:
                        assignments.extend(arg for arg in args[1:] if arg.startswith("FUNASR_BASE_URL="))
            self.assertEqual(assignments, ["FUNASR_BASE_URL=http://127.0.0.1:8000"])
            for endpoint in ("health", "v1/models", "openapi.json"):
                self.assertIn(f'"$FUNASR_BASE_URL/{endpoint}"', "\n".join(codes))

    def test_workflow_json_examples_match_actual_service_response_builders(self):
        handler = function(EXAMPLE / "server.py", "transcribe")
        response = next(node for node in ast.walk(handler) if isinstance(node, ast.Dict)
                        and any(isinstance(key, ast.Constant) and key.value == "duration" for key in node.keys))
        example = eval(compile(ast.Expression(response), "example-response", "eval"),
                       {"text": "recognized speech", "segments": [], "language": None,
                        "elapsed": 0.42, "model": "sensevoice"})
        namespace = {}
        functions = [function(PACKAGED, name) for name in
                     ("_split_text_for_openai_segments", "build_openai_fallback_segments",
                      "resolve_transcription_language", "build_openai_verbose_json")]
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(PACKAGED), "exec"), namespace)
        result = {"text": "recognized speech", "duration": 3.2, "language": "en",
                  "segments": namespace["build_openai_fallback_segments"]("recognized speech", 3.2)}
        packaged = namespace["build_openai_verbose_json"](result)
        for path in WORKFLOW_DOCS:
            text = path.read_text(encoding="utf-8")
            samples = [json.loads(code) for code in blocks(text, "json")]
            self.assertEqual(samples, [example, packaged], path.name)
            self.assertIn("](CLIENTS.md#response-formats)", text)
            for marker in ("sentence_info", "segments=[]", "spk=true", "ctc_timestamps", "use_itn", "hotwords"):
                self.assertIn(marker, text)
        for speaker in (None, 0, "SPK0", "S01"):
            result["segments"][0]["speaker"] = speaker
            segment = namespace["build_openai_verbose_json"](result)["segments"][0]
            if speaker is None:
                self.assertNotIn("speaker", segment)
            else:
                self.assertEqual(segment["speaker"], speaker)

    def test_workflow_url_worker_warns_before_code_and_declares_dependency(self):
        for path in WORKFLOW_DOCS:
            text = path.read_text(encoding="utf-8")
            section = text.split("### Audio URL path" if path.name == "WORKFLOWS.md" else "### 音频 URL 转写", 1)[1]
            warning = section.split("```python", 1)[0]
            markers = ("not implemented", "redirect", "private-network", "byte", "trusted") if path.name == "WORKFLOWS.md" else (
                "未实现", "重定向", "私网", "字节", "可信")
            for marker in markers:
                self.assertIn(marker, warning)
            self.assertIn("python -m pip install requests", text[:text.index("```python")])

    def test_workflow_python_examples_are_equivalent_and_send_real_multipart_fields(self):
        snippets = [blocks(path.read_text(encoding="utf-8"), "python") for path in WORKFLOW_DOCS]
        self.assertEqual([len(items) for items in snippets], [2, 2])
        self.assertEqual([ast.dump(ast.parse(code)) for code in snippets[0]],
                         [ast.dump(ast.parse(code)) for code in snippets[1]])
        allowed = set(form_defaults(function(EXAMPLE / "server.py", "transcribe"))) | {"file"}
        for code, name in zip(snippets[0], ("transcribe_from_url", "transcribe_bytes")):
            calls = []
            handles = []
            payload = b"test audio bytes, no acoustic inference"

            def post(url, *, files, data, timeout):
                self.assertEqual(urlsplit(url).path, "/v1/audio/transcriptions")
                self.assertEqual(set(files), {"file"})
                self.assertLessEqual(set(data) | set(files), allowed)
                self.assertEqual(data, {"model": "sensevoice", "response_format": "verbose_json"})
                self.assertGreater(timeout, 0)
                body = files["file"][1]
                if hasattr(body, "read"):
                    handles.append(body)
                    body = body.read()
                self.assertEqual(body, payload)
                calls.append(url)
                return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"text": "hello", "segments": []})

            downloads = []

            def get(url, *, timeout):
                downloads.append(url)
                self.assertGreater(timeout, 0)
                return SimpleNamespace(content=payload, raise_for_status=lambda: None)

            parsed = ast.parse(code)
            # Substitute only the HTTP boundary; execute the documented worker body unchanged.
            parsed.body = [node for node in parsed.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
            namespace = {"Path": Path, "tempfile": tempfile, "requests": SimpleNamespace(get=get, post=post)}
            exec(compile(parsed, name, "exec"), namespace)
            args = ("https://storage.example.invalid/approved.wav",) if name == "transcribe_from_url" else ("audio.wav", payload)
            self.assertEqual(namespace[name](*args), {"text": "hello", "segments": []})
            self.assertEqual(len(calls), 1)
            self.assertEqual(downloads, list(args) if name == "transcribe_from_url" else [])
            self.assertTrue(all(handle.closed for handle in handles))


class JavaScriptDocsContract(unittest.TestCase):
    """Source/text contracts only; actual JS execution and TS checking are separate."""

    def test_javascript_preserves_headings_and_resolves_guide_links(self):
        legacy = [
            "JavaScript and TypeScript Recipes for the FunASR OpenAI-Compatible API|Preflight|OpenAI JavaScript SDK|Built-in fetch without an SDK|TypeScript helper|Next.js route handler|Production checklist|Troubleshooting",
            "FunASR OpenAI 兼容 API JavaScript/TypeScript 接入配方|预检查|OpenAI JavaScript SDK|不依赖 SDK 的内置 fetch 写法|TypeScript helper|Next.js route handler|生产检查清单|故障排查",
        ]
        for path, expected in zip(JAVASCRIPT_DOCS, legacy):
            text = path.read_text(encoding="utf-8")
            prose = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)
            self.assertEqual(re.findall(r"(?m)^#{1,6} (.+)$", prose), expected.split("|"))
            self.assertEqual([len(level) for level in re.findall(r"(?m)^(#{1,6}) ", prose)], [1] + [2] * 7)
            suffix = "_zh" if path.stem.endswith("_zh") else ""
            links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
            self.assertIn(f"../../docs/moss_transcribe_diarize{suffix}.md", links)
            for link in links:
                parts = urlsplit(link)
                if parts.scheme or parts.netloc:
                    continue
                target = (path.parent / unquote(parts.path)).resolve()
                self.assertIn(ROOT.resolve(), target.parents)
                self.assertNotIn(".mcp-tasks", target.parts)
                self.assertTrue(target.is_file(), link)
                if parts.fragment:
                    self.assertIn(unquote(parts.fragment), headings(target.read_text(encoding="utf-8")), link)

    def test_javascript_startup_and_smoke_use_explicit_source_options(self):
        for path in JAVASCRIPT_DOCS:
            text = path.read_text(encoding="utf-8")
            prefix = text.split("```bash", 1)[0]
            suffix = "_zh" if path.stem.endswith("_zh") else ""
            self.assertIn(f"](README{suffix}.md", prefix)
            self.assertIn(f"](SECURITY{suffix}.md)", prefix)
            startup = blocks(text, "bash")[0]
            self.assertIn("cd examples/openai_api", startup)
            self.assertIn("source ../../.venv/bin/activate", startup)
            found = set()
            for code in blocks(text, "bash"):
                parsed = subprocess.run(["bash", "-n"], input=code, text=True, capture_output=True)
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
                for line in code.replace("\\\n", " ").splitlines():
                    args = shlex.split(line, comments=True)
                    if len(args) < 2 or args[0] != "python":
                        continue
                    self.assertIn(args[1], ("server.py", "smoke_test.py"))
                    found.add(args[1])
                    options = {ast.literal_eval(arg) for node in ast.walk(tree(EXAMPLE / args[1]))
                               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                               and node.func.attr == "add_argument" for arg in node.args
                               if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
                    self.assertLessEqual({arg for arg in args[2:] if arg.startswith("--")}, options)
                    self.assertIn("--model", args)
                    self.assertEqual(args[args.index("--model") + 1], "sensevoice")
                    if args[1] == "server.py":
                        self.assertIn("--host", args)
                        self.assertEqual(args[args.index("--host") + 1], "127.0.0.1")
                        self.assertEqual(args[args.index("--device") + 1], "cpu")
                    else:
                        self.assertEqual(args[args.index("--base-url") + 1], "http://127.0.0.1:8000")
            self.assertEqual(found, {"server.py", "smoke_test.py"})
            for endpoint in ("/health", "/v1/models", "/openapi.json"):
                self.assertIn(endpoint, text)

    def test_javascript_examples_keep_bilingual_code_and_runnable_module_entries(self):
        texts = [path.read_text(encoding="utf-8") for path in JAVASCRIPT_DOCS]
        for language in ("javascript", "typescript"):
            examples = [blocks(text, language) for text in texts]
            self.assertEqual([len(items) for items in examples], [2, 2])
            self.assertEqual(examples[0], examples[1])
        for text in texts:
            shell = "\n".join(blocks(text, "bash"))
            self.assertIn("node transcribe.mjs meeting.wav", shell)
            self.assertIn("node transcribe-fetch.mjs meeting.wav", shell)
            self.assertRegex(shell, r"npm install openai@\d+\.\d+\.\d+")
            self.assertIn("app/api/transcribe/route.ts", text)
            self.assertIn("funasr-client.ts", text)
            for code in blocks(text, "javascript") + blocks(text, "typescript"):
                self.assertNotRegex(code, r"[\"']Content-Type[\"']\s*:\s*[\"']multipart/form-data")

    def test_javascript_sdk_stream_lifecycle_is_owned_by_the_caller(self):
        for path in JAVASCRIPT_DOCS:
            text = path.read_text(encoding="utf-8")
            for code in (blocks(text, "javascript")[0], blocks(text, "typescript")[0]):
                with self.subTest(path=path.name, helper="typescript" if "interface" in code else "javascript"):
                    self.assertIn('from "node:fs/promises"', code)
                    self.assertIn('from "node:stream/promises"', code)
                    self.assertRegex(code, r'await open\(audioPath, ["\']r["\']\)')
                    self.assertIn("handle.createReadStream()", code)
                    self.assertRegex(code, r"finished\(file\)\.catch\(")
                    self.assertIn("toStreamingFile(file, basename(audioPath))", code)
                    self.assertLess(code.index("finished(file)"), code.index("client.audio.transcriptions.create"))
                    self.assertRegex(code, r"finally\s*\{\s*file\.destroy\(\);\s*await closed;")
                    self.assertRegex(code, r"finally\s*\{\s*await handle\.close\(\);")
                    self.assertNotIn("createReadStream(audioPath)", code)
                    self.assertNotRegex(code, r"\b(?:access|existsSync)\(audioPath")

    def test_javascript_speaker_union_covers_actual_serialized_values(self):
        functions = [function(PACKAGED, name) for name in
                     ("resolve_transcription_language", "build_openai_verbose_json")]
        namespace = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(PACKAGED), "exec"), namespace)
        kinds = set()
        for speaker in (0, "SPK0", "S01"):
            result = {"text": "hello", "segments": [{"start": 0, "end": 1, "text": "hello", "speaker": speaker}]}
            actual = namespace["build_openai_verbose_json"](result)["segments"][0]["speaker"]
            kinds.add("number" if isinstance(actual, int) else "string")
        handler = function(EXAMPLE / "server.py", "transcribe")
        speaker_value = next(node.values[node.keys.index(key)] for node in ast.walk(handler)
                             if isinstance(node, ast.Dict) for key in node.keys
                             if isinstance(key, ast.Constant) and key.value == "speaker")
        self.assertIsNone(eval(compile(ast.Expression(speaker_value), "example-speaker", "eval"), {"seg": {}}))
        kinds.add("null")
        for path in JAVASCRIPT_DOCS:
            helper = blocks(path.read_text(encoding="utf-8"), "typescript")[0]
            match = re.search(r"speaker\?\s*:\s*([^;}]+)", helper)
            self.assertIsNotNone(match)
            self.assertEqual({value.strip() for value in match.group(1).split("|")}, kinds)

    def test_javascript_guides_explain_response_and_forwarding_boundaries(self):
        for path in JAVASCRIPT_DOCS:
            text = path.read_text(encoding="utf-8")
            self.assertIn("](CLIENTS.md#response-formats)", text)
            for marker in ("sentence_info", "segments=[]", "spk=true", "ctc_timestamps", "use_itn", "hotwords", "Node.js 22"):
                self.assertIn(marker, text)
            before_route = text.split("## Next.js route handler", 1)[1].split("```typescript", 1)[0]
            markers = ("not implemented", "authentication", "upload", "build") if path.name == "JAVASCRIPT.md" else (
                "未实现", "鉴权", "上传", "build")
            for marker in markers:
                self.assertIn(marker, before_route)

    def test_javascript_native_route_has_fixed_upstream_and_bounded_error_contract(self):
        for path in JAVASCRIPT_DOCS:
            code = blocks(path.read_text(encoding="utf-8"), "typescript")[1]
            self.assertRegex(code, r"export const runtime\s*=\s*[\"']nodejs[\"']")
            self.assertIn("process.env.FUNASR_UPSTREAM_URL", code)
            self.assertIn("process.env.FUNASR_MODEL", code)
            self.assertNotIn("NEXT_PUBLIC_", code)
            self.assertNotRegex(code, r'incoming\.get\([\"\'](?:model|target|url)[\"\']\)')
            self.assertRegex(code, r"try\s*\{\s*incoming = await request\.formData\(\)")
            self.assertRegex(code, r"AbortSignal\.timeout\(120_?000\)")
            self.assertRegex(code, r'redirect:\s*[\"\']error[\"\']')
            self.assertRegex(code, r"\bsignal\s*[,}]")
            self.assertRegex(code, r"response\.status\s*>=\s*400")
            self.assertRegex(code, r"response\.status\s*<=\s*599")
            self.assertIn("await response.json()", code)
            self.assertIn("signal.aborted", code)
            self.assertNotIn("clearTimeout", code)
            self.assertNotIn("await response.text()", code)
            self.assertNotIn("error.message", code)
            self.assertNotIn("from \"next/", code)

    def test_javascript_fetch_cli_does_not_log_raw_upstream_errors(self):
        for path in JAVASCRIPT_DOCS:
            code = blocks(path.read_text(encoding="utf-8"), "javascript")[1]
            self.assertRegex(code, r"AbortSignal\.timeout\(120_?000\)")
            self.assertRegex(code, r'redirect:\s*[\"\']error[\"\']')
            self.assertIn("process.exitCode = 1", code)
            self.assertNotIn("await response.text()", code)
            self.assertNotIn("error.message", code)
            fields = re.findall(r'form\.append\([\"\']([^\"\']+)[\"\']', code)
            self.assertEqual(fields, ["file", "model", "response_format"])
            allowed = set(form_defaults(function(EXAMPLE / "server.py", "transcribe"))) | {"file"}
            self.assertLessEqual(set(fields), allowed)


class SecurityDocsContract(unittest.TestCase):
    """Documentation/source contracts, not proxy syntax or authentication execution."""

    def test_security_preserves_headings_levels_and_existing_links(self):
        expected = [
            "Security and Gateway Guide for the FunASR OpenAI-Compatible API|Recommended topology|Minimum controls before sharing|NGINX reverse proxy sketch|Caddy reverse proxy sketch|Kubernetes notes|Client configuration|Data handling checklist|Rollout checklist",
            "FunASR OpenAI 兼容 API 安全与网关指南|推荐拓扑|对团队开放前的最低控制项|NGINX 反向代理示例|Caddy 反向代理示例|Kubernetes 注意事项|客户端配置|数据处理清单|上线检查清单",
        ]
        for path, legacy in zip(SECURITY_DOCS, expected):
            text = path.read_text(encoding="utf-8")
            prose = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)
            self.assertEqual(re.findall(r"(?m)^#{1,6} (.+)$", prose), legacy.split("|"))
            self.assertEqual([len(level) for level in re.findall(r"(?m)^(#{1,6}) ", prose)], [1] + [2] * 8)
            suffix = "_zh" if path.stem.endswith("_zh") else ""
            links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
            for link in (f"README{suffix}.md", "CLIENTS.md", f"WORKFLOWS{suffix}.md",
                         f"GRADIO{suffix}.md", f"kubernetes/README{suffix}.md", "../../SECURITY.md"):
                self.assertIn(link, links)
            for link in links:
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc:
                    continue
                target = (path.parent / unquote(parsed.path)).resolve()
                self.assertIn(ROOT.resolve(), target.parents)
                self.assertNotIn(".mcp-tasks", target.parts)
                self.assertTrue(target.is_file(), link)
                if parsed.fragment:
                    self.assertIn(unquote(parsed.fragment), headings(target.read_text(encoding="utf-8")), link)

    def test_security_proxy_and_python_examples_are_bilingual(self):
        texts = [path.read_text(encoding="utf-8") for path in SECURITY_DOCS]
        for language in ("nginx", "caddyfile", "bash"):
            examples = [blocks(text, language) for text in texts]
            self.assertTrue(examples[0], language)
            normalized = [["\n".join(line.strip() for line in code.splitlines()
                                      if line.strip() and not line.lstrip().startswith("#"))
                           for code in items] for items in examples]
            self.assertEqual(normalized[0], normalized[1], language)
        examples = [blocks(text, "python") for text in texts]
        self.assertEqual([len(items) for items in examples], [1, 1])
        self.assertEqual(ast.dump(ast.parse(examples[0][0])), ast.dump(ast.parse(examples[1][0])))

    def test_security_backend_binding_matches_source_and_is_explicit(self):
        for source in (EXAMPLE / "server.py", ROOT / "funasr/bin/server.py"):
            host = next(node for node in ast.walk(tree(source)) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute) and node.func.attr == "add_argument"
                        and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "--host")
            self.assertEqual(ast.literal_eval(next(k.value for k in host.keywords if k.arg == "default")), "0.0.0.0")
        self.assertIn('${FUNASR_HOST_PORT:-8000}:8000', (EXAMPLE / "docker-compose.yml").read_text())
        for path in SECURITY_DOCS:
            text = path.read_text(encoding="utf-8")
            prefix = text.split("```nginx", 1)[0]
            for marker in ("127.0.0.1", "0.0.0.0", "FUNASR_HOST_PORT=127.0.0.1:8000", "ClusterIP"):
                self.assertIn(marker, prefix)
            recipes = blocks(text, "bash")
            for recipe in recipes:
                parsed = subprocess.run(["bash", "-n"], input=recipe, text=True, capture_output=True)
                self.assertEqual(parsed.returncode, 0, parsed.stderr)
            startup = next(code for code in recipes if "python server.py" in code)
            self.assertIn("cd examples/openai_api", startup)
            self.assertIn("source ../../.venv/bin/activate", startup)
            args = shlex.split(next(line for line in startup.splitlines() if line.startswith("python server.py")))
            self.assertEqual(args[args.index("--host") + 1], "127.0.0.1")
            self.assertEqual(args[args.index("--model") + 1], "sensevoice")
            self.assertEqual(args[args.index("--device") + 1], "cpu")

    def test_security_nginx_requires_basic_auth_and_restricts_route(self):
        for path in SECURITY_DOCS:
            code = blocks(path.read_text(encoding="utf-8"), "nginx")[0]
            code = "\n".join(line for line in code.splitlines() if not line.lstrip().startswith("#"))
            for directive in ("ssl_certificate ", "ssl_certificate_key ", "auth_basic ",
                              "auth_basic_user_file ", "client_max_body_size "):
                self.assertIn(directive, code)
            realms = re.findall(r"(?m)^\s*auth_basic\s+([^;\n]+);", code)
            self.assertEqual(len(realms), 1)
            realm = shlex.split(realms[0])
            self.assertEqual(len(realm), 1)
            self.assertTrue(realm[0].strip())
            self.assertNotEqual(realm[0].lower(), "off")
            self.assertRegex(code, r"location\s+=\s+/v1/audio/transcriptions\s*\{")
            self.assertRegex(code, r"limit_except\s+POST\s*\{\s*deny\s+all;")
            self.assertRegex(code, r"location\s+/\s*\{\s*return\s+404;\s*\}")
            self.assertEqual(len(re.findall(r"\bproxy_pass\b", code)), 1)
            self.assertRegex(code, r"proxy_pass\s+http://127\.0\.0\.1:8000;")
            self.assertIn('proxy_set_header Authorization "";', code)
            self.assertNotIn("$http_authorization", code)

    def test_security_caddy_orders_auth_before_body_and_proxy(self):
        for path in SECURITY_DOCS:
            code = blocks(path.read_text(encoding="utf-8"), "caddyfile")[0]
            self.assertRegex(code, r"@transcribe\s*\{\s*path /v1/audio/transcriptions\s+method POST\s*\}")
            self.assertRegex(code, r"handle @transcribe\s*\{\s*route\s*\{")
            self.assertIn("basic_auth {", code)
            self.assertLess(code.index("basic_auth {"), code.index("request_body {"))
            self.assertLess(code.index("request_body {"), code.index("reverse_proxy "))
            self.assertEqual(code.count("reverse_proxy "), 1)
            self.assertIn("reverse_proxy 127.0.0.1:8000", code)
            self.assertIn("header_up -Authorization", code)
            self.assertRegex(code, r'handle\s*\{\s*respond "Not found" 404\s*\}')
            self.assertRegex(code, r"(?m)^\s*tls /\S+ /\S+$")

    def test_security_covers_registered_routes_and_unimplemented_controls(self):
        routes = set()
        for source in (EXAMPLE / "server.py", PACKAGED):
            for node in ast.walk(tree(source)):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("get", "post"):
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        if node.args[0].value.startswith("/"):
                            routes.add(node.args[0].value)
        self.assertEqual(routes, {"/health", "/v1/models", "/v1/audio/transcriptions", "/asr"})
        for path in SECURITY_DOCS:
            text = path.read_text(encoding="utf-8")
            for route in routes | {"/openapi.json", "/docs", "/redoc"}:
                inline_code = re.findall(r"`([^`\n]+)`", text)
                self.assertTrue(any(route in value.split() for value in inline_code), route)
            for marker in ("200m", "600s", "NetworkPolicy", "CORS"):
                self.assertIn(marker, text)
            markers = ("not implemented", "model admission", "temporary", "cancel") if path.name == "SECURITY.md" else (
                "未实现", "模型准入", "临时", "取消")
            for marker in markers:
                self.assertIn(marker, text)

    def test_security_client_distinguishes_basic_from_bearer_and_local_smoke(self):
        for path in SECURITY_DOCS:
            text = path.read_text(encoding="utf-8")
            client_section = text.split("## Client configuration" if path.name == "SECURITY.md" else "## 客户端配置", 1)[1].split("\n## ", 1)[0]
            for marker in ("Basic", "Bearer", "api_key", "OIDC", "mTLS"):
                self.assertIn(marker, client_section)
            curl = next(code for code in blocks(text, "bash") if "curl " in code)
            args = shlex.split(curl.replace("\\\n", " "))
            self.assertEqual(args[0], "curl")
            # Parse only this recipe's option set; argparse also expands short-flag clusters.
            parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
            for short, long in (("-k", "--insecure"), ("-L", "--location"),
                                ("-f", "--fail"), ("-S", "--show-error"), ("-s", "--silent")):
                parser.add_argument(short, long, action="store_true")
            for short, long in (("-u", "--user"), ("-m", "--max-time"),
                                ("-o", "--output"), ("-w", "--write-out")):
                parser.add_argument(short, long)
            parser.add_argument("-F", "--form", action="append")
            options, operands = parser.parse_known_args(args[1:])
            self.assertFalse(options.insecure)
            self.assertFalse(options.location)
            self.assertEqual(operands, ["https://funasr.example.com/v1/audio/transcriptions"])
            self.assertEqual(options.user, "team_user")
            self.assertEqual(options.output, "/dev/null")
            markers = ("unauthenticated local", "does not send", "not a Bearer") if path.name == "SECURITY.md" else (
                "无鉴权本地", "不发送", "不是 Bearer")
            for marker in markers:
                self.assertIn(marker, text)


GRADIO_DOCS = [EXAMPLE / name for name in ("GRADIO.md", "GRADIO_zh.md")]
GRADIO_HEADINGS = {
    "GRADIO.md": "Gradio Browser Demo for the FunASR OpenAI-Compatible API|1. Start the API server|2. Install and launch the browser UI|3. Verify the backend first|Model aliases|Production notes",
    "GRADIO_zh.md": "FunASR OpenAI 兼容 API Gradio 浏览器 Demo|1. 启动 API 服务|2. 安装并启动浏览器 UI|3. 先验证后端服务|模型别名|生产注意事项",
}


def shell_commands(text):
    return [shlex.split(line, comments=True) for code in blocks(text, "bash")
            for line in code.replace("\\\n", " ").splitlines()
            if shlex.split(line, comments=True)]


def gradio_client_module():
    # The client imports Gradio only inside build_app, not during CLI parsing.
    spec = importlib.util.spec_from_file_location("gradio_docs_client", EXAMPLE / "gradio_app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GradioDocsContract(unittest.TestCase):
    def test_preserves_gradio_headings_and_existing_links(self):
        for path in GRADIO_DOCS:
            text = path.read_text(encoding="utf-8")
            source = re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", "", text, flags=re.M | re.S)
            actual = re.findall(r"^(#{1,6}) (.+)$", source, re.M)
            self.assertEqual([heading for _, heading in actual], GRADIO_HEADINGS[path.name].split("|"))
            self.assertEqual([len(level) for level, _ in actual], [1] + [2] * 5)
            suffix = "_zh" if path.name.endswith("_zh.md") else ""
            for relative in (f"../../docs/moss_transcribe_diarize{suffix}.md",
                             f"../../docs/model_selection{suffix}.md", f"SECURITY{suffix}.md"):
                self.assertIn(f"]({relative})", text)
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                parts = urlsplit(link)
                if parts.scheme or parts.netloc:
                    continue
                target = (path.parent / unquote(parts.path)).resolve() if parts.path else path.resolve()
                self.assertIn(ROOT.resolve(), target.parents)
                self.assertNotIn(".mcp-tasks", target.parts)
                self.assertTrue(target.is_file(), link)
                if parts.fragment:
                    self.assertIn(unquote(parts.fragment), headings(target.read_text(encoding="utf-8")), link)

    def test_gradio_commands_are_bilingual_equivalent(self):
        self.assertEqual(*(shell_commands(path.read_text(encoding="utf-8")) for path in GRADIO_DOCS))

    def test_gradio_preflight_reuses_pinned_loopback_checkout(self):
        for path in GRADIO_DOCS:
            text = path.read_text(encoding="utf-8")
            self.assertIn("SECURITY", text[:text.index("```bash")])
            suffix = "_zh" if path.name.endswith("_zh.md") else ""
            readme = (EXAMPLE / f"README{suffix}.md").read_text(encoding="utf-8")
            self.assertEqual(shell_commands("```bash\n" + blocks(text, "bash")[0] + "```\n"),
                             shell_commands("```bash\n" + blocks(readme, "bash")[0] + "```\n"))
            for command in shell_commands(text):
                if command[:2] == ["python", "server.py"]:
                    self.assertEqual(command[command.index("--host") + 1], "127.0.0.1")
                    self.assertEqual(command[command.index("--device") + 1], "cpu")

    def test_gradio_client_environment_is_separate_and_reachable(self):
        for path in GRADIO_DOCS:
            text = path.read_text(encoding="utf-8")
            setup = next((code for code in blocks(text, "bash") if "-m venv .venv-gradio" in code), None)
            self.assertIsNotNone(setup, path.name)
            commands = shell_commands("```bash\n" + setup + "```\n")
            expected = [["cd", "FunASR-api"], ["python3.12", "-m", "venv", ".venv-gradio"],
                        ["source", ".venv-gradio/bin/activate"],
                        ["python", "-m", "pip", "install", "gradio==6.26.0"],
                        ["python", "-m", "pip", "check"], ["cd", "examples/openai_api"]]
            self.assertEqual(commands[:len(expected)], expected)
            self.assertEqual(commands[-1][:2], ["python", "gradio_app.py"])
            self.assertNotIn(["python", "-m", "pip", "install", "-e", "."], commands)
            self.assertNotIn("--share", commands[-1])

    def test_gradio_recipes_cover_profiles_and_explicit_served_model(self):
        client = gradio_client_module()
        for path in GRADIO_DOCS:
            launches = [command[2:] for command in shell_commands(path.read_text(encoding="utf-8"))
                        if command[:2] == ["python", "gradio_app.py"]]
            self.assertGreaterEqual(len(launches), 5, path.name)
            pairs = set()
            for command in launches:
                self.assertLessEqual({"--backend", "--model", "--base-url", "--host", "--port"}, set(command))
                options = client.parse_args(command)
                self.assertEqual(options.host, "127.0.0.1")
                self.assertEqual(options.port, 7860)
                self.assertFalse(options.share)
                url = urlsplit(options.base_url)
                self.assertEqual((url.scheme, url.hostname, url.path, url.query, url.fragment),
                                 ("http", "127.0.0.1", "", "", ""))
                self.assertIn(url.port, (8000, 8898))
                pairs.add((options.backend, options.model))
            self.assertLessEqual({("funasr", "sensevoice"), ("funasr", "moss-transcribe-diarize"),
                                 ("vllm", "moss-transcribe-diarize"),
                                 ("sglang-omni", "OpenMOSS-Team/MOSS-Transcribe-Diarize"),
                                 ("vllm", "meeting-asr")}, pairs)

    def test_gradio_model_lists_distinguish_service_contracts(self):
        profiles = gradio_client_module().BACKEND_PROFILES
        configs = next(node for node in ast.walk(tree(EXAMPLE / "server.py"))
                       if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                       and target.id == "MODEL_CONFIGS" for target in node.targets))
        aliases = [ast.literal_eval(key) for key in configs.value.keys]
        self.assertEqual(list(profiles["funasr"]["models"]), aliases)
        for path in GRADIO_DOCS:
            text = path.read_text(encoding="utf-8")
            heading = "Model aliases" if path.name == "GRADIO.md" else "模型别名"
            section = text.split("## " + heading + "\n", 1)[1].split("\n## ", 1)[0]
            self.assertNotRegex(section, r"(?m)^\|", path.name)
            self.assertEqual(re.findall(r"(?m)^- `([^`]+)`", section), aliases)
            for backend, profile in profiles.items():
                paragraph = text.split(f"**{backend}**", 1)[1].split("\n\n", 1)[0]
                identifiers = re.findall(r"`([^`]+)`", paragraph)
                self.assertEqual(identifiers[:2], [profile["models"][0], profile["default_format"]])
                self.assertLessEqual(set(profile["formats"]), set(identifiers))
            for marker in ("funasr", "vllm", "sglang-omni", "json", "verbose_json", "diarized_json",
                           "OpenMOSS-Team/MOSS-Transcribe-Diarize", "--model", "speaker", "[Sxx]",
                           "segments", "duration", "sentence_info", "Fun-ASR-MLT-Nano"):
                self.assertIn(marker, text, path.name)

    def test_gradio_guides_explain_remote_privacy_and_check_boundaries(self):
        markers = {
            "GRADIO.md": ("Authorization", "Basic", "Bearer", "allowlist", "redirect", "--share",
                          "Gradio process", "temporary", "redact", "not streaming", "does not cancel",
                          "Chinese sample", "downloads", "not an authentication", "metadata",
                          "not a model-readiness", "not an identity"),
            "GRADIO_zh.md": ("Authorization", "Basic", "Bearer", "allowlist", "重定向", "--share",
                             "Gradio 进程", "临时", "脱敏", "不是流式", "不会取消",
                             "中文样本", "下载", "不是鉴权", "metadata", "不代表模型就绪", "不是身份"),
        }
        for path in GRADIO_DOCS:
            text = path.read_text(encoding="utf-8")
            for marker in markers[path.name]:
                self.assertIn(marker.lower(), text.lower(), path.name)

    def test_readmes_delegate_gradio_install_to_isolated_guide(self):
        sections = ("Browser demo with Gradio", "Gradio 浏览器 Demo", "Gradio ブラウザデモ", "Gradio 브라우저 데모")
        for path, heading in zip(READMES, sections):
            text = path.read_text(encoding="utf-8")
            section = text.split("## " + heading + "\n", 1)[1].split("\n## ", 1)[0]
            self.assertNotIn("```", section, path.name)
            self.assertNotIn("pip install", section, path.name)
            self.assertNotIn("python gradio_app.py", section, path.name)
            guide = "GRADIO_zh.md" if path.name == "README_zh.md" else "GRADIO.md"
            self.assertIn(f"]({guide})", section)
            self.assertIn(".venv-gradio", section)
            self.assertIn("Python 3.12", section)


KUBERNETES_DOCS = [EXAMPLE / "kubernetes" / name for name in ("README.md", "README_zh.md")]


class KubernetesDocsContract(unittest.TestCase):
    def test_bilingual_commands_match_and_parse(self):
        self.assertEqual(*(shell_commands(path.read_text(encoding="utf-8")) for path in KUBERNETES_DOCS))
        for path in KUBERNETES_DOCS:
            for code in blocks(path.read_text(encoding="utf-8"), "bash"):
                result = subprocess.run(["bash", "-n"], input=code, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_builds_use_explicit_source_backed_contexts(self):
        expected = {
            "examples/openai_api/Dockerfile": ("examples/openai_api", "server.py", "cpu-latest"),
            "examples/openai_api/Dockerfile.moss": (".", "pyproject.toml", "moss-local"),
        }
        for path in KUBERNETES_DOCS:
            commands = shell_commands(path.read_text(encoding="utf-8"))
            self.assertFalse(any(args[0] == "cd" for args in commands))
            builds = [args[2:] for args in commands if args[:2] == ["docker", "build"]]
            self.assertEqual(len(builds), 2)
            seen = set()
            parser = argparse.ArgumentParser(allow_abbrev=False)
            parser.add_argument("-f", "--file", required=True)
            parser.add_argument("-t", "--tag", required=True)
            parser.add_argument("context")
            for args in builds:
                options = parser.parse_args(args)
                context, source, tag = expected[options.file]
                seen.add(options.file)
                self.assertEqual(options.context, context)
                self.assertTrue((ROOT / context / source).is_file())
                self.assertTrue((ROOT / options.file).is_file())
                dockerfile = (ROOT / options.file).read_text(encoding="utf-8")
                copy_source = "." if source == "pyproject.toml" else source
                self.assertRegex(dockerfile, rf"(?m)^COPY {re.escape(copy_source)} ")
                self.assertTrue(options.tag.endswith(":" + tag))
                self.assertIn(["docker", "push", options.tag], commands)
            self.assertEqual(seen, set(expected))

    def test_apply_paths_resolve_from_checkout_root(self):
        for path in KUBERNETES_DOCS:
            commands = shell_commands(path.read_text(encoding="utf-8"))
            applies = [args for args in commands if args[:4] == ["kubectl", "-n", "speech", "apply"]]
            self.assertEqual(applies, [
                ["kubectl", "-n", "speech", "apply", "-k", "examples/openai_api/kubernetes"],
                ["kubectl", "-n", "speech", "apply", "-f", "examples/openai_api/kubernetes/funasr-moss-api.yaml"],
            ])
            self.assertTrue((ROOT / applies[0][-1] / "kustomization.yaml").is_file())
            self.assertTrue((ROOT / applies[1][-1]).is_file())
            for deployment in ("funasr-api", "funasr-moss-api"):
                self.assertIn(["kubectl", "-n", "speech", "rollout", "status", "deploy/" + deployment,
                               "--timeout=15m"], commands)

    def test_port_forward_and_smoke_match_each_service(self):
        smoke_path = "examples/openai_api/smoke_test.py"
        options = {ast.literal_eval(arg) for node in ast.walk(tree(ROOT / smoke_path))
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == "add_argument" for arg in node.args
                   if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
        for path in KUBERNETES_DOCS:
            commands = shell_commands(path.read_text(encoding="utf-8"))
            smokes = [args for args in commands if args[0] == "python3"]
            self.assertEqual(len(smokes), 2)
            for args, service, model, port in zip(smokes, ("funasr-api", "funasr-moss-api"),
                                                ("sensevoice", "moss-transcribe-diarize"), (8000, 8001)):
                self.assertEqual(args[1], smoke_path)
                self.assertLessEqual({arg for arg in args[2:] if arg.startswith("--")}, options)
                self.assertEqual(args[args.index("--model") + 1], model)
                self.assertEqual(args[args.index("--response-format") + 1], "verbose_json")
                self.assertEqual(args[args.index("--base-url") + 1], f"http://127.0.0.1:{port}")
                self.assertIn(["kubectl", "-n", "speech", "port-forward", "--address", "127.0.0.1",
                               "svc/" + service, f"{port}:8000"], commands)

    def test_guides_link_owned_security_and_model_contracts(self):
        for path in KUBERNETES_DOCS:
            text = path.read_text(encoding="utf-8")
            suffix = "_zh" if path.stem.endswith("_zh") else ""
            for link in (f"../SECURITY{suffix}.md", f"../../../docs/moss_transcribe_diarize{suffix}.md"):
                self.assertIn(f"]({link})", text)
            self.assertIn(f"](../SECURITY{suffix}.md)", text.split("```bash", 1)[0])
            for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
                parts = urlsplit(link)
                if parts.scheme or parts.netloc:
                    continue
                target = (path.parent / unquote(parts.path)).resolve()
                self.assertIn(ROOT.resolve(), target.parents)
                self.assertNotIn(".mcp-tasks", target.parts)
                self.assertTrue(target.is_file(), link)
                if parts.fragment:
                    self.assertIn(unquote(parts.fragment), headings(target.read_text(encoding="utf-8")))

    def test_operational_limits_are_explicit(self):
        expected = {
            "README.md": ("repository root", "ClusterIP is not authentication", "PyPI",
                          "not an inference check", "does not send", "Python 3.10", "immutable digest",
                          "not native vLLM", "speaker identity", "not included in", "kustomization.yaml"),
            "README_zh.md": ("仓库根目录", "ClusterIP 不是鉴权", "PyPI", "不代表推理验收",
                             "不发送", "Python 3.10", "不可变 digest", "不是原生 vLLM", "说话人身份",
                             "不包含", "kustomization.yaml"),
        }
        for path in KUBERNETES_DOCS:
            text = path.read_text(encoding="utf-8")
            for marker in expected[path.name]:
                self.assertIn(marker, text, path.name)


MATRIX_DOCS = [ROOT / "docs" / ("deployment_matrix" + suffix + ".md")
               for suffix in ("", "_zh", "_ja", "_ko")]


class DeploymentMatrixDocsContract(unittest.TestCase):
    def test_four_language_shell_recipes_match(self):
        expected = shell_commands(MATRIX_DOCS[0].read_text(encoding="utf-8"))
        for path in MATRIX_DOCS:
            self.assertEqual(shell_commands(path.read_text(encoding="utf-8")), expected)

    def test_compose_recipe_overrides_ambient_settings_in_real_shell(self):
        expected = ["FUNASR_HOST_PORT=127.0.0.1:8000", "FUNASR_DEVICE=cpu", "FUNASR_MODEL=sensevoice",
                    "docker", "compose", "-f", "examples/openai_api/docker-compose.yml", "up", "--build"]
        with tempfile.TemporaryDirectory() as directory:
            docker = Path(directory) / "docker"
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$FUNASR_HOST_PORT" "$FUNASR_DEVICE" '
                              '"$FUNASR_MODEL" "$PWD" "$@"\n', encoding="utf-8")
            docker.chmod(0o700)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ.get("PATH", ""),
                       FUNASR_HOST_PORT="0.0.0.0:9999", FUNASR_DEVICE="cuda", FUNASR_MODEL="auto")
            for path in MATRIX_DOCS:
                code = next(code for code in blocks(path.read_text(encoding="utf-8"), "bash")
                            if "docker compose" in code)
                # Only the single reviewed launch is executed; the Docker binary is a capture fixture.
                self.assertEqual(shell_commands("```bash\n" + code + "```\n"), [expected])
                result = subprocess.run(["sh", "-c", code], cwd=ROOT, env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.splitlines(), ["127.0.0.1:8000", "cpu", "sensevoice",
                                  str(ROOT), "compose", "-f", "examples/openai_api/docker-compose.yml",
                                  "up", "--build"])
        self.assertTrue((ROOT / expected[-3]).is_file())
        self.assertTrue((ROOT / expected[-3]).with_name("Dockerfile").is_file())

    def test_second_terminal_smoke_uses_root_path_and_explicit_model(self):
        source = ROOT / "examples/openai_api/smoke_test.py"
        options = {ast.literal_eval(arg) for node in ast.walk(tree(source))
                   if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == "add_argument" for arg in node.args
                   if isinstance(arg, ast.Constant) and isinstance(arg.value, str)}
        expected = ["python3", str(source.relative_to(ROOT)), "--base-url", "http://127.0.0.1:8000",
                    "--model", "sensevoice", "--response-format", "verbose_json"]
        for path in MATRIX_DOCS:
            commands = shell_commands(path.read_text(encoding="utf-8"))
            self.assertEqual(len(commands), 2)
            self.assertEqual(commands[1], expected)
            self.assertLessEqual({arg for arg in expected[2:] if arg.startswith("--")}, options)

    def test_compose_guidance_explains_scope_and_preserves_owned_links(self):
        markers = {
            "deployment_matrix.md": ("repository root", "second terminal", "does not overwrite", "PyPI",
                                     "not a locked", "Authorization", "Python 3.10", "sample.wav"),
            "deployment_matrix_zh.md": ("仓库根目录", "第二个终端", "不会覆盖", "PyPI", "未锁定",
                                        "Authorization", "Python 3.10", "sample.wav"),
            "deployment_matrix_ja.md": ("リポジトリのルート", "別のターミナル", "上書きしません", "PyPI",
                                        "固定されていません", "Authorization", "Python 3.10", "sample.wav"),
            "deployment_matrix_ko.md": ("저장소 루트", "두 번째 터미널", "덮어쓰지 않습니다", "PyPI",
                                        "고정되지", "Authorization", "Python 3.10", "sample.wav"),
        }
        for path in MATRIX_DOCS:
            text = path.read_text(encoding="utf-8")
            for marker in markers[path.name]:
                self.assertIn(marker, text, path.name)
            security = "SECURITY_zh.md" if path.stem.endswith("_zh") else "SECURITY.md"
            self.assertIn(f"](../examples/openai_api/{security})", text)
            self.assertTrue((EXAMPLE / security).is_file())
            self.assertNotIn("cp .env.example .env", text)


if __name__ == "__main__":
    unittest.main()
