"""Keep repository Markdown links usable in the legacy Sphinx output."""

from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from docutils import nodes
from recommonmark.parser import CommonMarkParser
from sphinx.util import logging

LOGGER = logging.getLogger(__name__)
GITHUB = 'https://github.com/modelscope/FunASR'


def resolve_uri(app, source, uri, *, raw=False, validate=False):
    """Resolve only existing repository targets; None leaves Sphinx in charge."""
    link = urlsplit(uri)
    if link.scheme or link.netloc or link.path.startswith('/'):
        return uri
    if not link.path and not (raw or link.query or link.fragment):
        return None
    root = Path(app.srcdir).resolve().parent
    target = (source.parent / unquote(link.path)).resolve() if link.path else source.resolve()
    if not target.is_relative_to(root) or not target.exists():
        if raw:
            LOGGER.warning('Unresolved repository link: %s', uri,
                           location=str(source), type='repository_links', subtype='missing')
        return None
    target_doc = app.env.path2doc(str(target))
    if target_doc in app.env.found_docs:
        if app.builder.format != 'html':
            return None
        if not raw and not (link.query or link.fragment):
            # Plain document links retain Sphinx's own resolution.
            return None
        current_doc = app.env.path2doc(str(source))
        destination = app.builder.get_relative_uri(current_doc, target_doc)
        if validate and link.fragment:
            fragment = unquote(link.fragment)
            target_tree = app.env.get_doctree(target_doc)
            mapped = target_tree.get('repository_heading_targets', {}).get(fragment)
            if mapped:
                link = link._replace(fragment=quote(mapped, safe='-_'))
            validate_fragment(app, source, target_doc, uri, unquote(link.fragment))
    else:
        kind = 'tree' if target.is_dir() else 'blob'
        destination = f'{GITHUB}/{kind}/main/{quote(target.relative_to(root).as_posix(), safe="/")}'
    parts = urlsplit(destination)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, link.query, link.fragment))


def validate_fragment(app, source, target_doc, uri, fragment):
    """Called during writing, when every target doctree has been read."""
    target = app.env.get_doctree(target_doc)
    ids = set(target.ids)
    for node in target.findall(nodes.raw):
        if 'html' in node.get('format', '').split():
            ids.update(RawLinks(node.astext(), lambda uri: None).ids)
    if fragment not in ids:
        LOGGER.warning('Unresolved repository fragment: %s', uri,
                       location=str(source), type='repository_links', subtype='fragment')


class RepositoryMarkdownParser(CommonMarkParser):
    def visit_link(self, mdnode):
        source = Path(self.document['source'])
        uri = resolve_uri(self.document.settings.env.app, source, mdnode.destination)
        if uri is None:
            return super().visit_link(mdnode)
        # Resolve before recommonmark strips .md or treats //host as a doc ref.
        parsed = urlsplit(uri)
        if not (parsed.scheme or parsed.netloc or parsed.path or parsed.query) and parsed.fragment:
            # A fragment-only refuri is rewritten to a Sphinx label before our
            # heading aliases exist. A refid stays an HTML anchor reference.
            reference = nodes.reference(refid=unquote(parsed.fragment))
        else:
            reference = nodes.reference(refuri=uri)
        reference['repository_links_uri'] = mdnode.destination
        reference.line = self._get_line(mdnode)
        if mdnode.title:
            reference['title'] = mdnode.title
        self.current_node.append(reference)
        self.current_node = reference


class RawLinks(HTMLParser):
    """Replace changed opening tags only, preserving all other raw HTML bytes."""

    def __init__(self, text, resolve):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.resolve = resolve
        self.replacements = []
        self.ids = set()
        self.offsets = [0]
        for line in text.splitlines(keepends=True):
            self.offsets.append(self.offsets[-1] + len(line))
        self.feed(text)
        self.close()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get('id'):
            self.ids.add(attributes['id'])
        if tag == 'a' and attributes.get('name'):
            self.ids.add(attributes['name'])
        if tag != 'a':
            return
        uri = attributes.get('href')
        if uri is None:
            return
        destination = self.resolve(uri)
        if destination is None or destination == uri:
            return
        original = self.get_starttag_text()
        rewritten = '<' + tag
        for key, value in attrs:
            if key == 'href':
                value = destination
            rewritten += ' ' + key
            if value is not None:
                rewritten += '="' + escape(value, quote=True) + '"'
        rewritten += '/>' if original.endswith('/>') else '>'
        line, column = self.getpos()
        start = self.offsets[line - 1] + column
        self.replacements.append((start, start + len(original), rewritten))

    def rendered(self):
        result = self.text
        for start, end, replacement in reversed(self.replacements):
            result = result[:start] + replacement + result[end:]
        return result


def add_markdown_heading_aliases(app, doctree):
    """Keep Sphinx IDs while accepting fragments used by repository Markdown."""
    if app.builder.format != 'html' or Path(doctree['source']).suffix != '.md':
        return
    used = set()
    raw_ids = set()
    targets = {}
    for node in doctree.findall(nodes.raw):
        if 'html' in node.get('format', '').split():
            raw_ids.update(RawLinks(node.astext(), lambda uri: None).ids)
    for section in doctree.findall(nodes.section):
        title = section.next_node(nodes.title, descend=True, siblings=False)
        if title is None:
            continue
        base = re.sub(r'[^\w\- ]', '', title.astext().lower()).replace(' ', '-')
        if not base:
            continue
        alias = base
        suffix = 0
        while alias in used:
            suffix += 1
            alias = f'{base}-{suffix}'
        used.add(alias)
        if alias in raw_ids:
            LOGGER.warning('Markdown heading fragment conflicts with raw HTML anchor: %s',
                           alias, location=section, type='repository_links', subtype='collision')
        elif alias not in doctree.ids:
            section['ids'].append(alias)
            doctree.ids[alias] = section
        elif doctree.ids[alias] is not section:
            # An existing public Sphinx ID belongs to a different heading.
            # Keep that URL and route Markdown links to this heading's own ID.
            targets[alias] = section['ids'][0]
    doctree['repository_heading_targets'] = targets


def resolve_links(app, doctree, docname):
    if app.builder.format != 'html':
        return
    source = Path(doctree['source'])
    for node in doctree.findall(nodes.reference):
        original = node.attributes.pop('repository_links_uri', None)
        if original is not None:
            destination = resolve_uri(app, source, original, validate=True)
            if destination is not None:
                parsed = urlsplit(destination)
                if 'refid' in node:
                    node['refid'] = unquote(parsed.fragment)
                else:
                    node['refuri'] = destination
    for node in doctree.findall(nodes.raw):
        if 'html' not in node.get('format', '').split():
            continue
        original = node.astext()
        rewritten = RawLinks(
            original, lambda uri: resolve_uri(app, source, uri, raw=True, validate=True)
        ).rendered()
        if rewritten != original:
            node.children[:] = []
            node += nodes.Text(rewritten)


def setup(app):
    app.add_source_parser(RepositoryMarkdownParser, override=True)
    app.connect('doctree-read', add_markdown_heading_aliases)
    app.connect('doctree-resolved', resolve_links)
    return {'version': '1.1', 'parallel_read_safe': True}
