"""Legacy URLs must lead to maintained, model-specific instructions."""

from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('source,targets', (
    ('docs/reference/build_task.md', ('../model_registration.md', '../training.md')),
    ('docs/reference/application.md', ('../moss_transcribe_diarize.md', '../use_case_showcase.md')),
    ('docs/reference/FQA.md', ('../troubleshooting.md', '../moss_transcribe_diarize.md',
                              '../installation/installation.md')),
))
def test_legacy_reference_pages_link_to_current_guides(source, targets):
    path = ROOT / source
    content = path.read_text()
    links = re.findall(r'\]\(([^)]+)\)', content)
    for target in targets:
        assert target in links
        assert (path.parent / target).is_file()


def test_removed_task_architecture_is_not_an_executable_tutorial():
    content = (ROOT / 'docs/reference/build_task.md').read_text()
    assert content.startswith('# Build custom tasks\n')
    assert '```python' not in content
    assert 'migration' in content.lower()
    assert 'funasr/tasks/abs_task.py' not in content


def test_legacy_faq_preserves_model_boundaries():
    content = (ROOT / 'docs/reference/FQA.md').read_text()
    assert 'MOSS' in content
    assert 'anonymous' in content
    assert 'external `vad_model` or `spk_model`' in content
    assert 'Use a model pipeline that includes both VAD and speaker models:' not in content
    assert 'retry after removing the `funasr-cache` Docker volume' not in content
    assert '## Speaker diarization has no speaker labels' in content
    assert '## Can I use a speaker model other than cam++?' in content


@pytest.mark.parametrize('source', (
    'model_zoo/huggingface_models.md',
    'model_zoo/modelscope_models.md',
    'model_zoo/modelscope_models_zh.md',
))
def test_hub_catalogues_do_not_assign_one_license_to_all_models(source):
    content = (ROOT / source).read_text()
    intro = content[:content.index('### ')]
    assert '../MODEL_LICENSE' in intro
    assert '../LICENSE' in intro
    assert 'OpenMOSS' in intro
    assert '-  Apache License 2.0' not in intro
