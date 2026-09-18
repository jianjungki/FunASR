"""Check CLI documentation against the real parser and formatter, without models."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import types

from bs4 import BeautifulSoup
from markdown import markdown
import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / 'docs/cli.md', ROOT / 'docs/cli_zh.md']
spec = importlib.util.spec_from_file_location('cli_docs_subject', ROOT / 'funasr/cli.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
docs_spec = importlib.util.spec_from_file_location(
    'cli_docs_renderer', ROOT / 'web-pages/product-site/documentation.py')
renderer = importlib.util.module_from_spec(docs_spec)
docs_spec.loader.exec_module(renderer)


def source(path):
    assert path.is_file(), f'Missing bilingual CLI source: {path.name}'
    return path.read_text(encoding='utf-8')


def blocks(text, language):
    return re.findall(r'^```' + language + r'\n(.*?)^```', text, re.M | re.S)


@pytest.fixture
def parser(monkeypatch):
    captured = []

    class Captured(Exception):
        pass

    def capture(self, *args, **kwargs):
        captured.append(self)
        raise Captured

    with monkeypatch.context() as patch:
        patch.setattr(cli, '_get_version', lambda: 'fixture')
        patch.setattr(argparse.ArgumentParser, 'parse_args', capture)
        with pytest.raises(Captured):
            cli.main()
    assert len(captured) == 1
    return captured[0]


@pytest.mark.parametrize('path', DOCS, ids=lambda p: p.name)
def test_json_example_is_real_formatter_output_not_old_duration_field(path, monkeypatch):
    examples = blocks(source(path), 'json')
    assert len(examples) == 1
    monkeypatch.setitem(sys.modules, 'soundfile', types.SimpleNamespace(
        info=lambda _: types.SimpleNamespace(duration=1.2)))
    segments = [{'start': 0, 'end': 1200, 'text': 'Example.', 'timestamp': [[0, 1200]]}]
    actual = cli._format_output('Example.', segments, [[0, 1200]], 'json',
                                'audio.wav', 'sensevoice', None, 0.01)
    assert json.loads(examples[0]) == json.loads(actual)
    assert '"duration_s"' not in source(path)


def test_formatter_missing_audio_metadata_is_null(monkeypatch):
    def missing(_):
        raise OSError('fixture metadata unavailable')
    monkeypatch.setitem(sys.modules, 'soundfile', types.SimpleNamespace(info=missing))
    payload = json.loads(cli._format_output('Example.', [], None, 'json',
                                          'missing.wav', 'sensevoice', None, 0.01))
    assert payload['audio_duration_s'] is None
    assert payload['processing_s'] == 0.01
    assert 'segments' not in payload and 'timestamps' not in payload


@pytest.mark.parametrize('path', DOCS, ids=lambda p: p.name)
def test_reference_matches_actual_options_defaults_and_model_choices(path, parser):
    text = source(path)
    soup = BeautifulSoup(markdown(text, extensions=['extra']), 'html.parser')
    rows = {row.select_one('code').get_text(): row.get_text(' ', strip=True)
            for table in soup.select('table') for row in table.select('tr')
            if row.select_one('code') and row.select_one('code').get_text().startswith('--')}
    defaults = parser.parse_args(['audio.wav'])
    assert defaults.language is None and defaults.device is None
    assert defaults.model == 'sensevoice' and defaults.hub == 'ms'
    for action in parser._actions:
        long = next((option for option in action.option_strings if option.startswith('--')), None)
        if long:
            assert long in rows, long
            for alias in action.option_strings:
                assert alias in rows[long]
            if action.dest in ('language', 'device', 'output_dir', 'hotwords'):
                assert 'None' in rows[long]
            if action.dest in ('model', 'hub', 'output_format', 'subtitle_segment_mode'):
                assert str(action.default) in rows[long]
            if isinstance(action.default, bool):
                assert str(action.default) in rows[long]
            for choice in action.choices or []:
                assert choice in rows[long]
    model_action = next(a for a in parser._actions if a.dest == 'model')
    assert set(model_action.choices) == set(cli.MODEL_CONFIGS)
    for model in model_action.choices:
        assert model in text
    with pytest.raises(SystemExit) as stopped:
        parser.parse_args(['audio.wav', '--model', 'moss-transcribe-diarize'])
    assert stopped.value.code == 2


@pytest.mark.parametrize('path', DOCS, ids=lambda p: p.name)
def test_documented_shell_commands_parse_without_running_inference(path, parser):
    for block in blocks(source(path), 'bash'):
        checked = subprocess.run(['bash', '-n'], input=block, text=True,
                                 capture_output=True, timeout=10)
        assert checked.returncode == 0, checked.stderr
        for line in block.splitlines():
            args = shlex.split(line, comments=True)
            if not args or args[0] != 'funasr':
                continue
            stop = next((i for i, arg in enumerate(args) if arg in ('|', '>')), len(args))
            options = args[1:stop]
            if options == ['--help'] or options == ['--version']:
                continue
            parser.parse_args(options)


def test_bilingual_commands_are_identical():
    assert blocks(source(DOCS[0]), 'bash') == blocks(source(DOCS[1]), 'bash')


def test_bilingual_cli_navigation_uses_own_sources():
    catalogue = renderer.load_catalogue()
    entry = next(page for page in catalogue['pages'] if page['slug'] == 'command-line')
    assert entry['source_en'] == 'docs/cli.md'
    assert entry['source_zh'] == 'docs/cli_zh.md'
    index = (ROOT / 'docs/index.rst').read_text()
    assert re.search(r'^\s+cli_zh\s*$', index, re.M)


def test_sphinx_cli_pages_keep_unique_legacy_anchors(tmp_path):
    pytest.importorskip('sphinx')
    output = tmp_path / 'html'
    result = subprocess.run(
        [sys.executable, '-m', 'sphinx', '-b', 'html', '-q', str(ROOT / 'docs'), str(output)],
        text=True, capture_output=True, timeout=90,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 0, result.stdout + result.stderr
    for name in ('cli', 'cli_zh'):
        soup = BeautifulSoup((output / f'{name}.html').read_text(), 'html.parser')
        ids = [node['id'] for node in soup.select('[id]')]
        assert len(ids) == len(set(ids)), name
        for anchor in ('command-line-interface', 'installation', 'basic-usage', 'options',
                       'output-formats', 'text-default', 'json', 'srt', 'tsv',
                       'advanced-examples', 'models', 'legacy-cli'):
            assert anchor in ids, (name, anchor)


@pytest.mark.parametrize('path', DOCS, ids=lambda p: p.name)
def test_existing_public_anchors_and_local_links_remain_valid(path):
    from urllib.parse import unquote, urlsplit
    soup = BeautifulSoup(markdown(source(path), extensions=['extra', 'toc'],
                                 extension_configs={'toc': {'slugify': renderer.source_slug}}),
                         'html.parser')
    ids = [node['id'] for node in soup.select('[id]')]
    expected = {'command-line-interface', 'installation', 'basic-usage', 'options',
                'output-formats', 'text-default', 'json', 'srt', 'tsv',
                'advanced-examples', 'models', 'legacy-cli'}
    assert expected <= set(ids)
    assert len(ids) == len(set(ids))
    for link in soup.select('a[href]'):
        parts = urlsplit(link['href'])
        if parts.scheme or parts.netloc:
            continue
        target = (path.parent / unquote(parts.path)).resolve() if parts.path else path
        assert target.is_relative_to(ROOT) and target.is_file(), link['href']
        if parts.fragment and target == path:
            assert unquote(parts.fragment) in ids


@pytest.mark.parametrize('path', DOCS, ids=lambda p: p.name)
def test_scoped_claims_and_required_boundaries(path):
    text = source(path)
    for stale in ('~70ms/10s', '~60ms/10s', 'Include word-level timestamps'):
        assert stale not in text
    for marker in ('audio_duration_s', 'processing_s', 'moss-transcribe-diarize',
                   'moss_transcribe_diarize', 'AutoModel', 'funasr-server',
                   'None', '500', '42', 'sentence_info'):
        assert marker in text


def test_timestamps_flag_retains_existing_json_data_without_requesting_alignment(tmp_path, monkeypatch, capsys):
    audio = tmp_path / 'audio.wav'
    audio.write_bytes(b'fixture; no decoder invoked')
    seen = []

    class Model:
        def __init__(self, **kwargs):
            pass

        def generate(self, **kwargs):
            seen.append(kwargs)
            return [{'text': 'Example.', 'timestamp': [[0, 1200]]}]

    monkeypatch.setitem(sys.modules, 'torch', types.SimpleNamespace(
        cuda=types.SimpleNamespace(is_available=lambda: False)))
    monkeypatch.setitem(sys.modules, 'funasr', types.SimpleNamespace(AutoModel=Model))
    monkeypatch.setitem(sys.modules, 'soundfile', types.SimpleNamespace(
        info=lambda _: types.SimpleNamespace(duration=1.2)))
    monkeypatch.setattr(sys, 'argv', ['funasr', str(audio), '--timestamps', '-f', 'json'])
    cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload['timestamps'] == [[0, 1200]]
    assert seen == [{'input': str(audio), 'batch_size': 1}]
