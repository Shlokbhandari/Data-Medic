import sys
import os
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from sandbox import create_sandbox, cleanup_sandbox

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_PIPELINE = PROJECT_ROOT / 'pipeline' / 'run_pipeline.py'

SAMPLE_PATCH = {
    'explanation': 'test patch',
    'patched_code': '# this is patched code\nprint("patched")\n',
    'risk_notes': 'none',
}


def test_sandbox_contains_pipeline_and_data():
    result = create_sandbox(SAMPLE_PATCH)
    sandbox = Path(result['sandbox_path'])
    try:
        assert (sandbox / 'pipeline').is_dir()
        assert (sandbox / 'data').is_dir()
    finally:
        cleanup_sandbox(str(sandbox))


def test_patched_file_differs_from_original():
    result = create_sandbox(SAMPLE_PATCH)
    sandbox = Path(result['sandbox_path'])
    try:
        patched_content = (sandbox / result['target_file']).read_text()
        assert patched_content == SAMPLE_PATCH['patched_code']
        assert patched_content != result['original_code']
    finally:
        cleanup_sandbox(str(sandbox))


def test_real_repo_file_is_untouched():
    original_bytes = REAL_PIPELINE.read_bytes()
    result = create_sandbox(SAMPLE_PATCH)
    sandbox = Path(result['sandbox_path'])
    try:
        after_bytes = REAL_PIPELINE.read_bytes()
        assert original_bytes == after_bytes
    finally:
        cleanup_sandbox(str(sandbox))


def test_cleanup_removes_directory():
    result = create_sandbox(SAMPLE_PATCH)
    sandbox_path = result['sandbox_path']
    assert Path(sandbox_path).exists()
    cleanup_sandbox(sandbox_path)
    assert not Path(sandbox_path).exists()


def test_nonexistent_target_raises_error():
    bad_patch = {
        'explanation': 'test',
        'patched_code': 'print("bad")',
        'risk_notes': 'none',
    }
    with pytest.raises(FileNotFoundError, match="does not exist in the sandbox"):
        create_sandbox(bad_patch, target_file='pipeline/totally_fake_file.py')
