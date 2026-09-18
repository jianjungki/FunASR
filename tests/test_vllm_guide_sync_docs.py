"""Exercise the compatibility guide generator through its real CLI."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/sync_vllm_guide.py"


@pytest.fixture
def guide_tree(tmp_path):
    assert SCRIPT.is_file(), "The compatibility guide needs a sync CLI"
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs").mkdir()
    shutil.copy2(SCRIPT, tmp_path / "scripts" / SCRIPT.name)
    source = tmp_path / "docs/vllm_guide_zh.md"
    source.write_bytes(b"# Guide\n\n## Section\n\n[Local](./api.md)\n")
    return tmp_path, source, tmp_path / "docs/vllm_guide_zh_v2.md"


def run_sync(root, *args):
    return subprocess.run(
        [sys.executable, str(root / "scripts" / SCRIPT.name), *args],
        cwd=root.parent,
        capture_output=True,
        text=True,
        check=False,
    )


def test_generate_full_guide_and_repeat_without_changing_source(guide_tree):
    root, source, target = guide_tree
    original = source.read_bytes()
    result = run_sync(root)
    assert result.returncode == 0, result.stderr
    generated = target.read_bytes()
    assert generated.endswith(original)
    assert b"[" in generated[: -len(original)]
    assert b"vllm_guide_zh.md" in generated[: -len(original)]
    assert run_sync(root).returncode == 0
    assert target.read_bytes() == generated
    assert source.read_bytes() == original
    assert run_sync(root, "--check").returncode == 0


@pytest.mark.parametrize("change", ["missing", "target", "source", "line-endings"])
def test_check_detects_drift_without_writing(guide_tree, change):
    root, source, target = guide_tree
    assert run_sync(root).returncode == 0
    if change == "missing":
        target.unlink()
    elif change == "target":
        target.write_bytes(target.read_bytes() + b"\nManual edit\n")
    elif change == "source":
        source.write_bytes(source.read_bytes() + b"\nNew section\n")
    else:
        target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))
    before = {p.name: p.read_bytes() for p in (source, target) if p.exists()}
    result = run_sync(root, "--check")
    assert result.returncode == 1
    assert "sync_vllm_guide.py" in result.stderr
    after = {p.name: p.read_bytes() for p in (source, target) if p.exists()}
    assert before == after


@pytest.mark.parametrize("args", [(), ("--check",)])
def test_missing_source_does_not_replace_existing_mirror(guide_tree, args):
    root, source, target = guide_tree
    target.write_bytes(b"Existing compatibility page\n")
    source.unlink()
    result = run_sync(root, *args)
    assert result.returncode == 1
    assert "vllm_guide_zh.md" in result.stderr
    assert target.read_bytes() == b"Existing compatibility page\n"


def test_repository_compatibility_guide_is_current():
    result = run_sync(ROOT, "--check")
    assert result.returncode == 0, result.stderr
