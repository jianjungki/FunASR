"""Small, model-free builds using the real Sphinx configuration and link adapter.

Run with Sphinx and the extensions listed in docs/conf.py installed.
"""

import os
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from bs4 import BeautifulSoup
import pytest

pytest.importorskip('sphinx')
ROOT = Path(__file__).resolve().parents[1]


def test_vllm_compatibility_pages_preserve_rendered_section_targets(tmp_path):
    docs = tmp_path / 'docs'
    docs.mkdir()
    shutil.copy2(ROOT / 'docs/conf.py', docs / 'conf.py')
    shutil.copytree(ROOT / 'docs/_ext', docs / '_ext')
    names = ('vllm_guide_zh', 'vllm_guide_zh_v2')
    (docs / 'index.rst').write_text(
        'Guides\n======\n\n.. toctree::\n\n   vllm_guide_zh\n   vllm_guide_zh_v2\n')
    for name in names:
        shutil.copy2(ROOT / 'docs' / (name + '.md'), docs / (name + '.md'))
    output = tmp_path / 'html'
    result = subprocess.run(
        [sys.executable, '-m', 'sphinx', '-b', 'html', str(docs), str(output)],
        text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    for name in names:
        soup = BeautifulSoup((output / (name + '.html')).read_text(), 'html.parser')
        article = soup.select_one('[role=main]')
        pairs = []
        for section in article.select('section[id],div.section[id]'):
            heading = section.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'], recursive=False)
            ids = [section['id']] + [
                node['id'] for node in section.find_all(id=True, recursive=False)
                if node.name == 'span']
            pairs.append([ids, heading.get_text() if heading else None])
        # Published pre-consolidation Sphinx output: 40 heading/target pairs,
        # including numeric ids and the duplicate Chinese heading alias.
        assert len(pairs) == 40
        digest = hashlib.sha256(json.dumps(pairs, ensure_ascii=False).encode()).hexdigest()
        assert digest == 'fe2775e9be07ba6a8bc7cb899a41fe7441ca9d1710ec7b7aee425dfff26a095e', name
    mirror = BeautifulSoup((output / 'vllm_guide_zh_v2.html').read_text(), 'html.parser')
    assert mirror.select_one('a[href="vllm_guide_zh.html"]')

GUIDE = '''# Link fixture

[Body code](../../examples/demo.py)
[Body model guide](../../examples/guide.md)
[Body directory](../../examples/)
[Body license](../../LICENSE)
[Body encoded](../../examples/folder%20name/guide.md?view=1&lang=zh#usage)
[Body Unicode](../../examples/中文/guide.md)
[Body internal](../training.md)
[Body query](../training.md?view=1#details)
[Body query without fragment](../training.md?view=2)
[Body query raw anchor](../training.md?view=1#%72aw-anchor)
[Body query missing](../training.md?view=1#body-query-ABSENT)
[Body later target](../zz_later.md?view=1#details)
[Body external](https://docs.example.test/guide.md?view=1#usage)
[Body cross-host](//docs.example.test/guide.md)
[Body root](../../../outside.txt)
[Body missing](../../examples/missing.py)
[Body missing fragment](../training.md#absent-section)
[Numbered heading](../training.md#1-installation--environment)
[Unicode heading](../training.md#安装或-import-失败)
[Encoded heading](../training.md#%E5%AE%89%E8%A3%85%E6%88%96-import-%E5%A4%B1%E8%B4%A5)
[Punctuation heading](../training.md#llamacpp-or-gguf)
[Repeated heading](../training.md#repeat-1)
[Local numbered heading](#2-local--section)
[Colliding heading](../training.md#collision-1)

## 2. Local & section

| Case | Destination |
| --- | --- |
| code | [Table code](../../examples/demo.py) |
| markdown | [Table model guide](../../examples/guide.md) |
| directory | [Table directory](../../examples/) |
| encoded | [Table encoded](../../examples/folder%20name/guide.md?view=1&lang=zh#usage) |
| Unicode | [Table Unicode](../../examples/中文/guide.md) |
| internal | [Table internal](../training.md?view=1#details) |
| query | [Table query without fragment](../training.md?view=2) |
| raw anchor | [Table raw anchor](../training.md?view=1#%72aw-anchor) |
| missing fragment | [Table missing fragment](../training.md#table-ABSENT) |
| missing query fragment | [Table missing query fragment](../training.md?view=1#table-query-ABSENT) |
| later target | [Table later target](../zz_later.md?view=1#details) |
| rst | [Table RST](../reference.rst) |
| external | [Table external](https://docs.example.test/guide.md?view=1#usage) |
| cross-host | [Table cross-host](//docs.example.test/guide.md) |
| missing | [Table missing](../../examples/table-missing.py) |
| escape | [Table escape](../../../outside.txt) |
| symlink | [Table symlink](../../examples/escape.txt) |
| numbered | [Table numbered](../training.md#1-installation--environment) |
| Unicode | [Table Unicode heading](../training.md#安装或-import-失败) |
| collision | [Table colliding heading](../training.md#collision-1) |

<a href="//docs.example.test/raw.md" data-label="do not alter">Raw cross-host</a>
<a href="/other-site/guide.md">Root-relative</a>
<a href="mailto:help@example.test">Mail</a>
<a href="#local-anchor">Local fragment</a>
<span id="local-anchor"></span>
<a href="../training.md#raw-ABSENT">Raw missing fragment</a>
<a href="#self-ABSENT">Raw missing self fragment</a>
<a href="../training.md#collision-1">Raw colliding heading</a>

```python
print("../examples/demo.py is code, not a link")
```
'''


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    work = tmp_path_factory.mktemp('sphinx-links')
    repo = work / 'repo'
    docs = repo / 'docs'
    (docs / 'tutorial').mkdir(parents=True)
    shutil.copy2(ROOT / 'docs/conf.py', docs / 'conf.py')
    if (ROOT / 'docs/_ext').is_dir():
        shutil.copytree(ROOT / 'docs/_ext', docs / '_ext')
    (docs / 'index.rst').write_text(
        'Fixture\n=======\n\n.. toctree::\n\n   tutorial/guide\n   tutorial/guide_zh\n   training\n   reference\n   zz_later\n')
    for name in ('guide.md', 'guide_zh.md'):
        (docs / 'tutorial' / name).write_text(GUIDE, encoding='utf-8')
    (docs / 'training.md').write_text(
        '# Training\n\n## Details\n\nReal destination.\n\n<span id="raw-anchor"></span>\n'
        '\n## 1. Installation & Environment\n\nInstall.\n'
        '\n## 安装或 `import` 失败\n\nDiagnose.\n'
        '\n## llama.cpp or GGUF\n\nRuntime.\n'
        '\n## Repeat\n\nFirst.\n\n## Repeat\n\nSecond.\n'
        '\n## Collision\n\nFirst collision.\n\n## Collision\n\nSecond collision.\n'
        '\n## Collision-1\n\nThird collision.\n'
        '\n<span id="rawcollision"></span>\n\n## Raw.Collision\n\nRaw collision.\n',
        encoding='utf-8')
    (docs / 'reference.rst').write_text('Reference\n=========\n\nExisting RST page.\n')
    # Sphinx reads this target after tutorial/*, so early doctree access fails.
    (docs / 'zz_later.md').write_text('# Later target\n\n## Details\n\nLate-read destination.\n')
    for name in ('examples/demo.py', 'examples/guide.md', 'LICENSE',
                 'examples/folder name/guide.md', 'examples/中文/guide.md'):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture\n', encoding='utf-8')
    (work / 'outside.txt').write_text('outside repository\n')
    (repo / 'examples/escape.txt').symlink_to(work / 'outside.txt')
    original = {p: p.read_bytes() for p in docs.rglob('*') if p.is_file()}
    output = work / 'html'
    command = [sys.executable, '-m', 'sphinx', '-b', 'html', '-n', '-E',
               '-d', str(work / 'doctrees'), str(docs), str(output)]
    result = subprocess.run(command, text=True, capture_output=True, timeout=90,
                            env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    assert result.returncode == 0, result.stdout + result.stderr
    assert all(p.read_bytes() == text for p, text in original.items())
    pages = {name: BeautifulSoup((output / f'tutorial/{name}.html').read_text(), 'html.parser')
             for name in ('guide', 'guide_zh')}
    return output, pages, result.stdout + result.stderr


@pytest.mark.parametrize('language', ('guide', 'guide_zh'))
@pytest.mark.parametrize('label,path', (
    ('Body code', 'blob/main/examples/demo.py'),
    ('Body model guide', 'blob/main/examples/guide.md'),
    ('Body directory', 'tree/main/examples'),
    ('Body license', 'blob/main/LICENSE'),
    ('Body encoded', 'blob/main/examples/folder%20name/guide.md?view=1&lang=zh#usage'),
    ('Body Unicode', 'blob/main/examples/%E4%B8%AD%E6%96%87/guide.md'),
    ('Table code', 'blob/main/examples/demo.py'),
    ('Table model guide', 'blob/main/examples/guide.md'),
    ('Table directory', 'tree/main/examples'),
    ('Table encoded', 'blob/main/examples/folder%20name/guide.md?view=1&lang=zh#usage'),
    ('Table Unicode', 'blob/main/examples/%E4%B8%AD%E6%96%87/guide.md'),
))
def test_existing_repository_targets_use_github(built, language, label, path):
    _, pages, _ = built
    link = pages[language].find('a', string=label)
    assert link is not None
    assert link['href'] == 'https://github.com/modelscope/FunASR/' + path


@pytest.mark.parametrize('language', ('guide', 'guide_zh'))
def test_internal_table_links_use_builder_routes(built, language):
    output, pages, _ = built
    page = pages[language]
    assert page.find('a', string='Body internal')['href'] == '../training.html'
    assert page.find('a', string='Table internal')['href'] == '../training.html?view=1#details'
    assert page.find('a', string='Table RST')['href'] == '../reference.html'
    assert (output / 'training.html').is_file()
    assert BeautifulSoup((output / 'training.html').read_text(), 'html.parser').find(id='details')


@pytest.mark.parametrize('language', ('guide', 'guide_zh'))
def test_body_and_table_queries_resolve_identically(built, language):
    _, pages, log = built
    page = pages[language]
    for body, table, uri in (
        ('Body query', 'Table internal', '../training.html?view=1#details'),
        ('Body query without fragment', 'Table query without fragment', '../training.html?view=2'),
        ('Body query raw anchor', 'Table raw anchor', '../training.html?view=1#%72aw-anchor'),
        ('Body later target', 'Table later target', '../zz_later.html?view=1#details'),
    ):
        assert page.find('a', string=body)['href'] == uri
        assert page.find('a', string=table)['href'] == uri
    warnings = [line for line in log.splitlines() if 'WARNING:' in line]
    assert not any('raw-anchor' in line or '%72aw-anchor' in line or '#details' in line
                   or 'docs.example.test' in line or '#local-anchor' in line for line in warnings)


@pytest.mark.parametrize('fragment', (
    'body-query-ABSENT', 'table-ABSENT', 'table-query-ABSENT', 'raw-ABSENT', 'self-ABSENT',
))
def test_unresolved_query_and_raw_fragments_warn(built, fragment):
    _, _, log = built
    warnings = [line for line in log.splitlines() if 'WARNING:' in line]
    assert any(fragment in line and '[repository_links.fragment]' in line for line in warnings)


@pytest.mark.parametrize('language', ('guide', 'guide_zh'))
def test_external_hosts_root_urls_and_code_are_untouched(built, language):
    _, pages, _ = built
    page = pages[language]
    for label, uri in (
        ('Body external', 'https://docs.example.test/guide.md?view=1#usage'),
        ('Table external', 'https://docs.example.test/guide.md?view=1#usage'),
        ('Body cross-host', '//docs.example.test/guide.md'),
        ('Table cross-host', '//docs.example.test/guide.md'),
        ('Raw cross-host', '//docs.example.test/raw.md'),
        ('Root-relative', '/other-site/guide.md'),
        ('Mail', 'mailto:help@example.test'),
        ('Local fragment', '#local-anchor'),
    ):
        assert page.find('a', string=label)['href'] == uri
    assert page.find('a', string='Raw cross-host')['data-label'] == 'do not alter'
    assert any('print("../examples/demo.py is code, not a link")' in pre.get_text()
               for pre in page.select('pre'))


def test_missing_targets_and_fragments_still_warn(built):
    _, pages, log = built
    warnings = [line for line in log.splitlines() if 'WARNING:' in line]
    for marker in ('missing.py', 'table-missing.py', 'outside.txt', 'escape.txt', 'absent-section'):
        assert any(marker in line for line in warnings), (marker, warnings)
    assert not any('examples/demo.py' in line or 'examples/guide' in line for line in warnings)
    for page in pages.values():
        assert page.find('a', string='Body missing')['href'] == '../../examples/missing.py'
        assert page.find('a', string='Table missing')['href'] == '../../examples/table-missing.py'
        assert page.find('a', string='Table escape')['href'] == '../../../outside.txt'
        assert page.find('a', string='Table symlink')['href'] == '../../examples/escape.txt'


@pytest.mark.parametrize('language', ('guide', 'guide_zh'))
def test_source_heading_fragments_remain_clickable(built, language):
    from urllib.parse import unquote

    output, pages, log = built
    target = BeautifulSoup((output / 'training.html').read_text(), 'html.parser')
    for label, fragment in (
        ('Numbered heading', '1-installation--environment'),
        ('Unicode heading', '安装或-import-失败'),
        ('Encoded heading', '安装或-import-失败'),
        ('Punctuation heading', 'llamacpp-or-gguf'),
        ('Repeated heading', 'repeat-1'),
        ('Table numbered', '1-installation--environment'),
        ('Table Unicode heading', '安装或-import-失败'),
    ):
        link = pages[language].find('a', string=label)
        assert link is not None, label
        assert unquote(link['href']) == '../training.html#' + fragment
        assert target.find(id=fragment), fragment
        assert not any(fragment in line for line in log.splitlines() if 'WARNING:' in line)
    local = pages[language].find('a', string='Local numbered heading')
    assert local is not None
    assert local['href'] == '#2-local--section'
    assert pages[language].find(id='2-local--section')
    # Existing Sphinx IDs are public URLs too; aliases must not replace them.
    assert target.find(id='details')
    assert target.find(id='llama-cpp-or-gguf')
    ids = [element['id'] for element in target.select('[id]')]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize('language', ('guide', 'guide_zh'))
@pytest.mark.parametrize('label', ('Colliding heading', 'Table colliding heading', 'Raw colliding heading'))
def test_colliding_alias_links_reach_the_intended_heading(built, language, label):
    output, pages, log = built
    page = BeautifulSoup((output / 'training.html').read_text(), 'html.parser')
    fragment = pages[language].find('a', string=label)['href'].split('#')[1]
    target = page.find(id=fragment)
    section = target if target.name == 'section' else target.find_parent('section')
    assert 'Second collision.' in section.get_text()
    assert 'Third collision.' not in section.get_text()
    assert len(page.select('[id="rawcollision"]')) == 1
    assert 'rawcollision' in log and '[repository_links.collision]' in log
    assert page.find(id='collision-1'), 'Do not remove existing Sphinx URLs'


@pytest.mark.parametrize('builder', ('text', 'latex'))
def test_non_html_builders_keep_sphinx_fragment_resolution(tmp_path, builder):
    docs = tmp_path / 'repo' / 'docs'
    docs.mkdir(parents=True)
    shutil.copy2(ROOT / 'docs/conf.py', docs / 'conf.py')
    shutil.copytree(ROOT / 'docs/_ext', docs / '_ext')
    (docs / 'index.rst').write_text('Fixture\n=======\n\n.. toctree::\n\n   guide\n   target\n')
    (docs / 'guide.md').write_text('# Guide\n\n[Valid](target.md#details)\n\n[Missing](target.md#ABSENT)\n')
    (docs / 'target.md').write_text('# Target\n\n## Details\n\nDestination.\n')
    result = subprocess.run(
        [sys.executable, '-m', 'sphinx', '-b', builder, '-n', '-E',
         str(docs), str(tmp_path / 'output')],
        text=True, capture_output=True, timeout=90,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'ABSENT' in result.stderr or 'absent' in result.stderr
    assert 'WARNING' in result.stderr


def test_faq_points_to_the_existing_speaker_contract():
    source = (ROOT / 'docs/reference/FQA.md').read_text()
    assert 'speaker-verification--diarization-eres2netv2' not in source
    assert '../python_api.md#vad-timestamps-and-speakers' in source
    from markdown import markdown
    page = BeautifulSoup(markdown((ROOT / 'docs/python_api.md').read_text(),
                                  extensions=['extra', 'toc']), 'html.parser')
    assert page.find(id='vad-timestamps-and-speakers')
