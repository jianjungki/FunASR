"""Render the documentation catalogue from repository-owned Markdown sources."""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from markdown import Markdown

SITE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SITE_ROOT.parents[1]
GITHUB = 'https://github.com/modelscope/FunASR/blob/main/'
RAW = 'https://raw.githubusercontent.com/modelscope/FunASR/main/'


def source_slug(value: str, separator: str) -> str:
    """Preserve Unicode and repeated spaces used by source Markdown fragments."""
    return re.sub(r'[^\w\- ]', '', value.lower()).replace(' ', separator)


def load_catalogue() -> dict:
    catalogue = json.loads((SITE_ROOT / 'data/documentation.json').read_text())
    groups = [group['id'] for group in catalogue['groups']]
    slugs = [entry['slug'] for entry in catalogue['pages']]
    if len(set(groups)) != len(groups) or len(set(slugs)) != len(slugs):
        raise ValueError('Duplicate documentation group or slug')
    for entry in catalogue['pages']:
        if entry['group'] not in groups or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', entry['slug']):
            raise ValueError(f'Invalid documentation entry: {entry["slug"]}')
        for language in ('zh', 'en'):
            path = (REPO_ROOT / entry[f'source_{language}']).resolve()
            if not path.is_relative_to(REPO_ROOT) or not path.is_file():
                raise ValueError(f'Missing documentation source: {path}')
    routes, sources = set(), set()
    for entry in catalogue.get('localized_pages', []):
        language, route, relative = entry['language'], entry['route'], entry['source']
        path = (REPO_ROOT / relative).resolve()
        if (language not in ('ja', 'ko') or
                not re.fullmatch(rf'{re.escape(language)}/[a-z0-9-]+\.html', route) or
                route in routes or path in sources or
                not path.is_relative_to(REPO_ROOT) or not path.is_file()):
            raise ValueError(f'Invalid localized documentation owner: {route}')
        routes.add(route)
        sources.add(path)
    return catalogue


def doc_route(slug: str, language: str) -> str:
    return f'/{"en/" if language == "en" else ""}docs/{slug}.html'


def render_source(entry: dict, language: str, catalogue: dict, *, extra_routes: dict | None = None) -> dict:
    relative = entry[f'source_{language}']
    parser = Markdown(extensions=['extra', 'toc', 'sane_lists'],
                      extension_configs={'toc': {'slugify': source_slug}})
    soup = BeautifulSoup(parser.convert((REPO_ROOT / relative).read_text()), 'html.parser')
    local_routes = {}
    variants = ('en', 'zh') if language == 'zh' else ('zh', 'en')
    for variant in variants:
        for page in catalogue['pages']:
            local_routes[page[f'source_{variant}']] = doc_route(page['slug'], variant)
    local_routes.update(extra_routes or {})
    for element, attr in [('a', 'href'), ('img', 'src')]:
        for node in soup.select(f'{element}[{attr}]'):
            value = str(node[attr])
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith('/'):
                continue
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(relative), unquote(parsed.path)))
            if resolved.startswith('../'):
                raise ValueError(f'Documentation link escapes repository: {relative}: {value}')
            destination = local_routes.get(resolved) if element == 'a' else None
            if destination is None:
                destination = (RAW if element == 'img' else GITHUB) + quote(resolved, safe='/')
            node[attr] = urlunsplit((*urlsplit(destination)[:3], parsed.query, parsed.fragment))
    heading = soup.find('h1')
    if heading:
        # Keep source anchor names when the document title is moved into the shell.
        heading.name = 'div'
        heading['class'] = ['source-title-anchor']
        heading.clear()
    for index, code in enumerate(soup.select('pre')):
        code['id'] = code.get('id', f'code-{index}')
    return {
        'content_html': str(soup),
        'toc_html': parser.toc,
        'source_url': GITHUB + quote(relative, safe='/'),
        'source_english_only': language == 'zh' and relative == entry['source_en'],
    }


def write_search_indexes(stage: Path) -> None:
    indexes: dict[str, list] = {'zh': [], 'en': []}
    for path in sorted(stage.rglob('*.html')):
        if path.name == '404.html':
            continue
        soup = BeautifulSoup(path.read_text(), 'html.parser')
        heading = soup.select_one('h1')
        canonical = soup.select_one('link[rel="canonical"]')
        if heading is None or canonical is None:
            continue
        url = urlsplit(canonical['href']).path
        if url in {'/', '/en/'} or '/static/' in url or '/voice/' in url:
            continue
        content = soup.select_one('.docs-article') or soup.select_one('main') or soup.select_one('article') or soup.body
        if content is None:
            continue
        for node in content.select('script, style, nav, .site-header, .site-footer'):
            node.decompose()
        indexes['en' if url.startswith('/en/') else 'zh'].append({
            'title': heading.get_text(' ', strip=True),
            'url': url,
            'text': content.get_text(' ', strip=True)[:24000],
        })
    for language, entries in indexes.items():
        (stage / f'search-{language}.json').write_text(json.dumps(entries, ensure_ascii=False))
