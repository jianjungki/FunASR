"""Compatibility contracts for the published pre-catalogue guide URLs."""

import json
from pathlib import Path
import sys

from bs4 import BeautifulSoup
import pytest

SITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SITE))

# IDs independently inventoried from gh-pages at 871ac766876c2f511550478d88c86aa3daab3172.
OLD_IDS = {
    'tutorial.html': 'quick install choose scenarios offline streaming spk emotion vad punc deploy-agent subtitle export faq',
    'training.html': 'overview data paraformer sensevoice nano params multi-gpu deepspeed monitor inference-after tips',
    'model-registration.html': 'architecture setup understand add-model add-component standalone testing pitfalls contribute',
    'model-selection.html': 'default decision aliases runtime benchmark',
    'moss-transcribe-diarize.html': 'contract server runtimes evidence boundaries',
    'vllm.html': 'overview install offline streaming-sdk websocket dynamic-vad performance api-reference faq',
    'deployment-matrix.html': 'matrix choices runtime-diagnostics checklist help',
    # Independently inventoried from public EN/ZH pages on 2026-09-07.
    'agent.html': 'server sdk workflows mcp voice subtitle',
    'benchmark.html': 'summary table method choose',
}
PAGES = [prefix + name for name in OLD_IDS for prefix in ('', 'zh/')]
LOCALIZED_IDS = {
    'ja/agent.html': 'server sdk mcp voice subtitle',
    'ko/agent.html': 'server sdk workflows mcp voice subtitle',
    'ja/benchmark.html': 'summary table method choose',
    'ko/benchmark.html': 'summary table method choose',
}


@pytest.mark.parametrize('invalid', ('language', 'escape', 'wrong-prefix', 'duplicate-route', 'duplicate-source'))
def test_localized_catalogue_rejects_ambiguous_or_unsafe_owners(tmp_path, monkeypatch, invalid):
    import documentation

    catalogue = json.loads((SITE / 'data/documentation.json').read_text())
    entry = {'language': 'ja', 'route': 'ja/agent.html', 'title': 'Agent',
             'source': 'docs/agent_integration.md'}
    catalogue['localized_pages'] = [entry]
    if invalid == 'language':
        entry['language'] = 'fr'
    elif invalid == 'escape':
        entry['route'] = '../agent.html'
    elif invalid == 'wrong-prefix':
        entry['route'] = 'ko/agent.html'
    elif invalid == 'duplicate-route':
        catalogue['localized_pages'].append({**entry, 'source': 'docs/agent_integration_zh.md'})
    else:
        catalogue['localized_pages'].append({**entry, 'route': 'ja/benchmark.html'})
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data/documentation.json').write_text(json.dumps(catalogue))
    monkeypatch.setattr(documentation, 'SITE_ROOT', tmp_path)
    with pytest.raises(ValueError, match='localized'):
        documentation.load_catalogue()


@pytest.fixture(scope='module')
def localized_exported(tmp_path_factory):
    from build import build
    from export_docs import export_documentation

    root = tmp_path_factory.mktemp('localized-legacy-docs')
    built, output = root / 'built', root / 'pages'
    build(built)
    sentinel = output / 'ko/unrelated.html'
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text('existing localized page')
    export_documentation(built, output)
    assert sentinel.read_text() == 'existing localized page'
    return built, output


@pytest.mark.parametrize('route', LOCALIZED_IDS)
def test_localized_pages_have_owned_sources_and_real_legacy_anchors(localized_exported, route):
    from urllib.parse import urlsplit

    built, output = localized_exported
    path = output / route
    assert path.is_file(), route
    language, filename = route.split('/')
    page = BeautifulSoup(path.read_text(), 'html.parser')
    assert page.html['lang'] == language
    assert page.select_one('link[rel=canonical]')['href'] == 'https://modelscope.github.io/FunASR/' + route
    source = (f'docs/agent_integration_{language}.md' if filename == 'agent.html'
              else f'docs/benchmark/historical_asr_{language}.md')
    assert page.select_one('[data-source-link]')['href'].endswith('/' + source)
    assert (SITE.parents[1] / source).is_file()
    ids = [node['id'] for node in page.select('[id]')]
    assert len(ids) == len(set(ids))
    mapping = json.loads((SITE / 'data/legacy_doc_anchors.json').read_text())['pages'][route]
    assert set(mapping) == set(LOCALIZED_IDS[route].split())
    for old, target in mapping.items():
        anchor = page.select_one('.docs-article').find(id=old)
        assert anchor is not None and anchor.name == 'span'
        heading = anchor.find_next_sibling()
        assert heading.name in ('h2', 'h3') and heading['id'] == target
    assert page.select_one('.docs-toc a[href^="#"]')
    assets = [(node, attr) for selector, attr in [('link[rel=stylesheet]', 'href'), ('script[src]', 'src')]
              for node in page.select(selector)]
    assert assets and page.body.get('data-copy-icon')
    for node, attr in assets + [(page.body, 'data-copy-icon')]:
        assert not urlsplit(node[attr]).scheme and not node[attr].startswith('/')
        assert (path.parent / node[attr]).is_file()
    # These legacy translations do not create a fictitious four-language product site.
    assert not (built / language / 'docs').exists()


@pytest.mark.parametrize('language', ('ja', 'ko'))
def test_localized_historical_cells_and_per_cell_links_are_preserved(localized_exported, language):
    _, output = localized_exported
    path = output / language / 'benchmark.html'
    assert path.is_file()
    page = BeautifulSoup(path.read_text(), 'html.parser')
    frozen = json.loads((SITE / 'tests/fixtures/historical_asr_tables.json').read_text())
    record = next(row for row in frozen['pages'] if row['language'] == language)
    tables = page.select('.docs-article table')
    assert len(tables) == len(record['tables']) == 3
    mapping = {'vllm.html': 'https://www.funasr.com/en/docs/vllm.html', 'agent.html': 'agent.html'}
    count = 0
    for table, expected in zip(tables, record['tables']):
        rows = table.select('tr')
        assert len(rows) == len(expected['rows'])
        for row, expected_cells in zip(rows, expected['rows']):
            cells = row.select('th,td')
            assert len(cells) == len(expected_cells)
            for cell, original in zip(cells, expected_cells):
                assert ' '.join(cell.get_text().split()) == original['text']
                assert [a['href'] for a in cell.select('a[href]')] == [mapping.get(a, a) for a in original['links']]
                count += 1
    assert count == 82
    original_url = f"https://github.com/modelscope/FunASR/blob/{frozen['source_commit']}/{language}/benchmark.html"
    assert page.select_one(f'a[href="{original_url}"]')
    article = page.select_one('.docs-article').get_text(' ', strip=True)
    for marker in ('11,539', '11,541', '169.6x', '211.8x', 'RTFx', '2026-09-07'):
        assert marker in article


@pytest.mark.parametrize('language', ('ja', 'ko'))
def test_localized_agent_recipes_match_maintained_contract(localized_exported, language):
    import ast
    import re
    import shlex

    _, output = localized_exported
    path = output / language / 'agent.html'
    assert path.is_file()
    source = (SITE.parents[1] / f'docs/agent_integration_{language}.md').read_text()
    blocks = re.findall(r'^```(\w+)\n(.*?)^```', source, re.M | re.S)
    commands = []
    for kind, block in blocks:
        if kind == 'python':
            ast.parse(block)
        if kind == 'json':
            assert 'mcpServers' in json.loads(block)
        for line in block.splitlines():
            if line.startswith('funasr-server '):
                command = shlex.split(line)
                assert command[command.index('--host') + 1] == '127.0.0.1'
                assert command[command.index('--model') + 1] == 'sensevoice'
                commands.append(command)
    assert commands
    for marker in ('paraformer-en', 'Fun-ASR-MLT-Nano', 'model="custom"', '--model-path', '--hub',
                   'verbose_json', 'examples/mcp_server/funasr_mcp.py',
                   'examples/voice_input/funasr_input.py', 'examples/subtitle/generate_subtitle.py'):
        assert marker in source


@pytest.fixture(scope='module')
def exported(tmp_path_factory):
    from documentation import load_catalogue, render_source
    from export_docs import ALIASES, export_documentation

    root = tmp_path_factory.mktemp('legacy-docs')
    built, output = root / 'built', root / 'pages'
    catalogue = load_catalogue()
    entries = {entry['slug']: entry for entry in catalogue['pages']}
    originals = {}
    for slug, filename in ALIASES.items():
        for language, source_prefix, target_prefix in (('en', 'en/', ''), ('zh', '', 'zh/')):
            content = render_source(entries[slug], language, catalogue)['content_html']
            html = ('<html><head><link rel="stylesheet" href="/assets/site.123.css">'
                    '<script src="/assets/experience.456.js" defer></script></head><body>'
                    '<a href="/docs/python-api.html">API</a>'
                    f'<article class="docs-article">{content}</article></body></html>')
            path = built / source_prefix / 'docs' / f'{slug}.html'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding='utf-8')
            originals[target_prefix + filename] = (path, html)
    (built / 'assets').mkdir()
    (built / 'assets/site.123.css').write_text('body { color: black; }')
    (built / 'assets/experience.456.js').write_text('"use strict";')
    for name in ('api.html', 'zh/api.html', 'reference/AutoModel.html', 'index.html'):
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'existing reference\n')
    export_documentation(built, output)
    return built, output, originals


@pytest.mark.parametrize('page', PAGES)
def test_every_published_fragment_survives(exported, page):
    _, output, _ = exported
    soup = BeautifulSoup((output / page).read_text(), 'html.parser')
    ids = [node['id'] for node in soup.select('[id]')]
    expected = set(OLD_IDS[Path(page).name].split())
    assert expected <= set(ids), (page, sorted(expected - set(ids)))
    assert len(ids) == len(set(ids)), page


@pytest.mark.parametrize('page', PAGES)
def test_aliases_precede_their_semantic_headings(exported, page):
    _, output, _ = exported
    manifest = json.loads((SITE / 'data/legacy_doc_anchors.json').read_text())
    mapping = manifest['pages'][page]
    assert set(mapping) == set(OLD_IDS[Path(page).name].split())
    soup = BeautifulSoup((output / page).read_text(), 'html.parser')
    article = soup.select_one('.docs-article')
    for old, target in mapping.items():
        anchor = article.find(id=old)
        heading = article.find(id=target)
        assert anchor is not None and heading is not None, (page, old, target)
        assert heading.name in ('h2', 'h3'), (page, target)
        assert anchor.name == 'span' and not anchor.get_text(), (page, old)
        sibling = anchor.find_next_sibling()
        while sibling is not None and sibling.name == 'span' and sibling.get('data-legacy-doc-anchor') is not None:
            sibling = sibling.find_next_sibling()
        assert sibling is heading, (page, old, target)


def test_export_preserves_source_content_api_and_local_assets(exported):
    _, output, originals = exported
    for page, (path, original) in originals.items():
        assert path.read_text() == original
        before = BeautifulSoup(original, 'html.parser')
        after = BeautifulSoup((output / page).read_text(), 'html.parser')
        assert after.select_one('.docs-article').get_text() == before.select_one('.docs-article').get_text()
        assert [(n.name, n['id'], n.get_text()) for n in after.select('h2[id],h3[id]')] == [
            (n.name, n['id'], n.get_text()) for n in before.select('h2[id],h3[id]')]
        assert [n.get_text() for n in after.select('pre')] == [n.get_text() for n in before.select('pre')]
        assert after.select_one('a[href="https://www.funasr.com/docs/python-api.html"]')
        for node, attribute in ((after.select_one('link[rel=stylesheet]'), 'href'), (after.script, 'src')):
            assert not node[attribute].startswith(('/', 'http'))
            assert ((output / page).parent / node[attribute]).is_file()
        for node in after.select('[data-legacy-doc-anchor]'):
            node.decompose()
        # Apart from the existing root-link rewrite, the article DOM is unchanged.
        for node in before.select('[href], [src]'):
            for attribute in ('href', 'src'):
                value = node.get(attribute, '')
                if value.startswith('/') and not value.startswith('//'):
                    node[attribute] = 'https://www.funasr.com' + value
        assert str(after.select_one('.docs-article')) == str(before.select_one('.docs-article'))
    for name in ('api.html', 'zh/api.html', 'reference/AutoModel.html', 'index.html'):
        assert (output / name).read_bytes() == b'existing reference\n'


def test_training_alias_and_moss_mappings_are_topic_specific():
    pages = json.loads((SITE / 'data/legacy_doc_anchors.json').read_text())['pages']
    for prefix, data, params, aliases, server in (
        ('', 'prepare-the-dataset', 'validate-small-then-launch', 'openai-compatible-api-aliases', 'funasr-openai-compatible-service'),
        ('zh/', '准备数据', '先做小规模验证', 'openai-兼容-api-别名', 'funasr-openai-兼容服务'),
    ):
        assert pages[prefix + 'training.html']['data'] == data
        assert pages[prefix + 'training.html']['params'] == params
        assert pages[prefix + 'model-selection.html']['aliases'] == aliases
        assert pages[prefix + 'moss-transcribe-diarize.html']['server'] == server
        assert pages[prefix + 'moss-transcribe-diarize.html']['evidence'] == server


def test_insertion_is_idempotent_and_keeps_existing_anchors():
    from export_docs import insert_legacy_anchors

    soup = BeautifulSoup('<article class="docs-article"><a id="existing"></a><h2 id="topic">Topic</h2></article>', 'html.parser')
    mapping = {'old': 'topic', 'existing': 'topic'}
    insert_legacy_anchors(soup, mapping)
    first = str(soup)
    insert_legacy_anchors(soup, mapping)
    assert str(soup) == first
    assert len(soup.select('#existing')) == 1
    assert soup.find(id='existing').name == 'a'


@pytest.mark.parametrize('page, targets', [
    ('agent.html', ['http-server', 'sdk-and-curl', 'workflow-integrations',
                    'mcp-server', 'desktop-voice-input', 'subtitle-generation']),
    ('zh/agent.html', ['http-服务', 'sdk-与-curl', '工作流集成',
                       'mcp-服务', '桌面语音输入', '字幕生成']),
])
def test_agent_legacy_fragments_keep_their_topics(page, targets):
    pages = json.loads((SITE / 'data/legacy_doc_anchors.json').read_text())['pages']
    assert pages[page] == dict(zip('server sdk workflows mcp voice subtitle'.split(), targets))


@pytest.mark.parametrize('page,targets', [
    ('benchmark.html', ['historical-summary', 'historical-results', 'provenance-and-limitations', 'choosing-a-current-path']),
    ('zh/benchmark.html', ['历史概览', '历史结果', '来源与限制', '当前选型']),
])
def test_benchmark_legacy_fragments_keep_their_topics(page, targets):
    pages = json.loads((SITE / 'data/legacy_doc_anchors.json').read_text())['pages']
    assert pages[page] == dict(zip('summary table method choose'.split(), targets))


@pytest.mark.parametrize('heading', ('<h2 id="different">Topic</h2>', '<p id="topic">Not a heading</p>'))
def test_missing_or_nonheading_target_fails_explicitly(heading):
    from export_docs import insert_legacy_anchors

    soup = BeautifulSoup(f'<article class="docs-article">{heading}</article>', 'html.parser')
    with pytest.raises(ValueError, match='topic'):
        insert_legacy_anchors(soup, {'old': 'topic'})
