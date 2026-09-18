"""Model-free contracts for the separate official native serving record."""

import hashlib
import json
from pathlib import Path
import ast
import subprocess

import pytest

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parents[1]
REVISION = 'a4362c943d48951f98ca2a62181cc028970270c5'
MANIFEST = ROOT / 'docs/benchmark/vllm_official_native_20260907.json'


def test_dated_community_record_is_unchanged():
    path = ROOT / 'docs/vllm_native_funasr_validation.md'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        'e8f348b0f473769e1ece224d881edcd03ce897e99bcd17918068ab97fbeb1583')


def test_official_catalogue_has_two_sources_and_keeps_historical_route():
    pages = json.loads((SITE / 'data/documentation.json').read_text())['pages']
    rows = [row for row in pages if row['slug'] == 'official-native-vllm']
    assert len(rows) == 1
    official = rows[0]
    assert official['group'] == 'deploy'
    for language, suffix in (('en', ''), ('zh', '_zh')):
        path = f'docs/vllm_official_native_validation{suffix}.md'
        assert official[f'source_{language}'] == path
        assert Path(path).stem in (ROOT / 'docs/index.rst').read_text()
    historical = next(row for row in pages if row['slug'] == 'native-vllm')
    assert 'historical' in historical['en'].lower()
    assert '历史' in historical['zh']
    assert historical['source_en'] == historical['source_zh'] == 'docs/vllm_native_funasr_validation.md'


@pytest.mark.parametrize('suffix', ('', '_zh'))
def test_official_record_has_reproducibility_and_scoped_evidence(suffix):
    path = ROOT / f'docs/vllm_official_native_validation{suffix}.md'
    assert path.is_file(), 'Missing separate official source record'
    text = path.read_text()
    for marker in (REVISION, 'FunAudioLLM/Fun-ASR-Nano-2512-vllm',
                   '0.27.1+cu129', '2.13.0+cu129', '5.15.0', '12.9',
                   'HF_HUB_OFFLINE=1', 'TRANSFORMERS_OFFLINE=1',
                   'snapshot_download', '--model "$MODEL_DIR"',
                   'language=zh', 'language=en', 'language=ja',
                   '0.911', '5.616', '7.176', '7.224',
                   'vllm_native_funasr_validation.md',
                   'benchmark/vllm_official_native_20260907.json',
                   '54944', 'v0.28.0', '2026-08-13'):
        assert marker in text
    for private in ('/cpfs_speech/', '/Users/', 'ind-gpu8'):
        assert private not in text


def test_official_manifest_preserves_exact_files_and_http_scope():
    assert MANIFEST.is_file(), 'Missing public redacted reproducibility metadata'
    record = json.loads(MANIFEST.read_text())
    assert record['revision'] == REVISION
    files = {row['path']: row for row in record['files']}
    assert len(files) == len(record['files']) == 23
    assert files['model.safetensors']['sha256'] == '96dfbec48282dd24d3334369a01e9e909f321ee39a1b0003c528c5379f68c1a6'
    requests = record['http']['requests']
    assert len(requests) == 8 and all(row['status'] == 200 for row in requests)
    for row in requests:
        if row['body_file'] != 'models.body':
            assert hashlib.sha256(row['raw_body_utf8'].encode()).hexdigest() == row['response_sha256']
    assert {row['request_fields']['language'] for row in requests if row['request_fields']} == {'zh', 'en', 'ja'}
    assert record['http']['two_request_wall_seconds'] == 0.9112209342420101
    assert record['first_chinese_request_warmed'] is False
    assert record['clean_install_validated'] is False
    assert record['guard_failure_before_server_spawn'] is True
    assert record['cleanup']['all_owned_exited'] is True
    for private in ('/cpfs_speech/', '/Users/', 'ind-gpu8', '/tmp/funasr-'):
        assert private not in MANIFEST.read_text()


def test_portable_commands_match_both_sources_and_parse_without_execution():
    entry = next(row for row in json.loads((SITE / 'data/deployments.json').read_text())['deployments']
                 if row['id'] == 'vllm')
    record = json.loads(MANIFEST.read_text())
    assert entry['commands'] == record['commands']
    for commands in entry['commands'].values():
        for command in commands:
            result = subprocess.run(['bash', '-n'], input=command, text=True,
                                    capture_output=True, timeout=10)
            assert result.returncode == 0, result.stderr
            if "<<'PY'\n" in command:
                ast.parse(command.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0])
            for suffix in ('', '_zh'):
                text = (ROOT / f'docs/vllm_official_native_validation{suffix}.md').read_text()
                assert command in text
