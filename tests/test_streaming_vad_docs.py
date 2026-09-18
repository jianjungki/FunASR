"""Execute the documented event/chunk handling without loading model weights."""

import ast
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from markdown import markdown

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(params=["streaming_vad.md", "streaming_vad_zh.md"])
def recipe(request):
    return lambda: load_recipe(ROOT / "docs" / request.param)


def load_recipe(path):
    assert path.is_file(), f"Missing runnable guide: {path}"
    soup = BeautifulSoup(markdown(path.read_text(), extensions=["fenced_code"]), "html.parser")
    blocks = soup.select("code.language-python")
    assert len(blocks) == 1
    tree = ast.parse(blocks[0].get_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    scope = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), scope)
    return scope


@pytest.mark.parametrize("length,want", [
    (1, [(0, 1, True)]),
    (3200, [(0, 3200, True)]),
    (3201, [(0, 3200, False), (3200, 3201, True)]),
    (6400, [(0, 3200, False), (3200, 6400, True)]),
])
def test_last_nonempty_chunk_is_final(recipe, length, want):
    recipe = recipe()
    assert list(recipe["chunk_ranges"](length, 3200)) == want


@pytest.mark.parametrize("length,stride", [(0, 3200), (-1, 3200), (10, 0), (10, -1)])
def test_invalid_audio_chunk_dimensions_are_rejected(recipe, length, stride):
    recipe = recipe()
    with pytest.raises(ValueError):
        list(recipe["chunk_ranges"](length, stride))


def test_partial_events_pair_across_calls_without_chunk_offsets(recipe):
    recipe = recipe()
    consume = recipe["consume_events"]
    pending, spans = consume([[100, -1]], None)
    assert (pending, spans) == (100, [])
    pending, spans = consume([], pending)
    assert (pending, spans) == (100, [])
    pending, spans = consume([[-1, 600], [800, 1000], [1200, -1]], pending)
    assert (pending, spans) == (1200, [(100, 600), (800, 1000)])
    assert consume([[-1, 1500]], pending) == (None, [(1200, 1500)])


@pytest.mark.parametrize("events,pending", [
    ([[-1, 600]], None), ([[100, 50]], None),
    ([[200, -1]], 100), ([[-1, -1]], None),
])
def test_invalid_event_order_does_not_silently_invent_spans(recipe, events, pending):
    recipe = recipe()
    with pytest.raises(ValueError):
        recipe["consume_events"](events, pending)
