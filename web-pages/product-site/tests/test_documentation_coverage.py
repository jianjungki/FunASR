from pathlib import Path
import ast
import json
import sys
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from markdown import markdown

SITE = Path(__file__).resolve().parents[1]
ROOT = SITE.parents[1]
sys.path.insert(0, str(SITE))


def test_catalogue_covers_the_full_user_journey():
    catalogue = json.loads((SITE / 'data/documentation.json').read_text())
    slugs = {row['slug'] for row in catalogue['pages']}
    assert {
        'installation', 'quickstart', 'python-api', 'model-zoo', 'training',
        'model-registration', 'docker', 'service-api', 'security',
        'javascript', 'kubernetes', 'websocket-protocol', 'runtime-guide',
    } <= slugs
    assert {'train', 'reference'} <= {group['id'] for group in catalogue['groups']}


def test_model_zoo_covers_current_families_without_empty_links():
    for name in ('readme.md', 'readme_zh.md'):
        content = (ROOT / 'model_zoo' / name).read_text()
        for marker in ('Fun-ASR-Nano', 'Fun-ASR-MLT-Nano', 'SenseVoice', 'Paraformer', 'MOSS-Transcribe-Diarize', 'OpenMOSS'):
            assert marker in content
        assert ']()' not in content
        assert '../docs/python_api' in content


def test_model_zoo_alias_links_match_the_hub_mapping():
    tree = ast.parse((ROOT / 'funasr/download/name_maps_from_hub.py').read_text())
    mapping = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign) and any(
                       isinstance(target, ast.Name) and target.id == 'name_maps_ms' for target in node.targets))
    for name in ('readme.md', 'readme_zh.md'):
        soup = BeautifulSoup(markdown((ROOT / 'model_zoo' / name).read_text(), extensions=['extra']), 'html.parser')
        for alias in ('paraformer-zh', 'paraformer-zh-streaming'):
            row = next(row for row in soup.select('tr') if row.select_one('code') and row.select_one('code').get_text() == alias)
            assert any(f'/models/{mapping[alias]}/' in link['href'] for link in row.select('a[href]'))


def test_runtime_index_separates_historical_release_notes():
    for name, history in (('readme.md', 'release-history.md'), ('readme_cn.md', 'release-history_zh.md')):
        content = (ROOT / 'runtime' / name).read_text()
        assert history in content
        assert 'MOSS' in content and 'llama.cpp' in content and 'vLLM' in content
        assert (ROOT / 'runtime' / history).is_file()
        assert './python/websocket/README.md' in content
        assert '`START`/`STOP`' in content


def test_catalogued_repository_links_resolve():
    from documentation import load_catalogue

    sources = {page[f'source_{lang}'] for page in load_catalogue()['pages'] for lang in ('zh', 'en')}
    for relative in sources:
        source = ROOT / relative
        soup = BeautifulSoup(markdown(source.read_text(), extensions=['extra']), 'html.parser')
        for tag, attribute in (('a', 'href'), ('img', 'src')):
            for node in soup.select(f'{tag}[{attribute}]'):
                link = urlsplit(node[attribute])
                if link.scheme or link.netloc or not link.path or link.path.startswith('/'):
                    continue
                destination = (source.parent / unquote(link.path)).resolve()
                assert destination.is_relative_to(ROOT) and destination.exists(), (relative, node[attribute])


def test_compatibility_export_uses_canonical_docs_without_changing_api(tmp_path):
    from export_docs import export_documentation

    built = tmp_path / 'site'
    (built / 'docs').mkdir(parents=True)
    (built / 'en/docs').mkdir(parents=True)
    (built / 'assets').mkdir()
    (built / 'assets/example.css').write_text('body { color: black; }')
    for prefix in ('', 'en/'):
        (built / prefix / 'docs/quickstart.html').write_text('<html><head><link rel="canonical" href="https://www.funasr.com/docs/quickstart.html"><link rel="stylesheet" href="/assets/example.css"></head><body><a href="/docs/python-api.html">API</a><a href="#step">Step</a><h1 id="step">Guide</h1></body></html>')
    output = tmp_path / 'pages'
    output.mkdir()
    (output / 'api.html').write_text('existing generated API')
    export_documentation(built, output, aliases={'quickstart': 'tutorial.html'})
    for relative in ('tutorial.html', 'zh/tutorial.html'):
        soup = BeautifulSoup((output / relative).read_text(), 'html.parser')
        assert soup.select_one('a[href="https://www.funasr.com/docs/python-api.html"]')
        assert soup.select_one('a[href="#step"]')
        asset = soup.select_one('link[rel="stylesheet"]')['href']
        assert not asset.startswith(('/', 'http'))
        assert ((output / relative).parent / asset).read_text() == 'body { color: black; }'
    assert (output / 'api.html').read_text() == 'existing generated API'
