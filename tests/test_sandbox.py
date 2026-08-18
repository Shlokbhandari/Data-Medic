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
    'syntax_valid': True,
}


def test_sandbox_contains_pipeline_and_data():
    result = create_sandbox(SAMPLE_PATCH, target_file='pipeline/run_pipeline.py')
    sandbox = Path(result['sandbox_path'])
    try:
        assert (sandbox / 'pipeline').is_dir()
        assert (sandbox / 'data').is_dir()
    finally:
        cleanup_sandbox(str(sandbox))


def test_patched_file_differs_from_original():
    result = create_sandbox(SAMPLE_PATCH, target_file='pipeline/run_pipeline.py')
    sandbox = Path(result['sandbox_path'])
    try:
        patched_content = (sandbox / result['target_file']).read_text()
        assert patched_content == SAMPLE_PATCH['patched_code']
        assert patched_content != result['original_code']
    finally:
        cleanup_sandbox(str(sandbox))


def _snapshot_repo():
    snapshot = {}
    for d in ['pipeline', 'data']:
        dir_path = PROJECT_ROOT / d
        if dir_path.exists():
            for filepath in dir_path.rglob('*'):
                if filepath.is_file() and '__pycache__' not in filepath.parts:
                    rel_path = str(filepath.relative_to(PROJECT_ROOT))
                    snapshot[rel_path] = filepath.read_bytes()
    return snapshot


def test_real_repo_file_is_untouched():
    before_snapshot = _snapshot_repo()
    result = create_sandbox(SAMPLE_PATCH, target_file='pipeline/run_pipeline.py')
    sandbox = Path(result['sandbox_path'])
    try:
        after_snapshot = _snapshot_repo()
        assert before_snapshot == after_snapshot
    finally:
        cleanup_sandbox(str(sandbox))


def test_cleanup_removes_directory():
    result = create_sandbox(SAMPLE_PATCH, target_file='pipeline/run_pipeline.py')
    sandbox_path = result['sandbox_path']
    assert Path(sandbox_path).exists()
    cleanup_sandbox(sandbox_path)
    assert not Path(sandbox_path).exists()


def test_nonexistent_target_raises_error():
    bad_patch = {
        'explanation': 'test',
        'patched_code': 'print("bad")',
        'risk_notes': 'none',
        'syntax_valid': True,
    }
    with pytest.raises(FileNotFoundError, match="does not exist in the sandbox"):
        create_sandbox(bad_patch, target_file='pipeline/totally_fake_file.py')


def test_path_traversal_is_rejected():
    malicious_patch = {
        'explanation': 'malicious',
        'patched_code': 'print("hacked")',
        'risk_notes': 'none',
        'syntax_valid': True,
    }
    
    # Try traversing out of the sandbox
    with pytest.raises(ValueError, match="resolves outside the sandbox"):
        create_sandbox(malicious_patch, target_file='../../../etc/passwd')
        
    # Try an absolute path
    with pytest.raises(ValueError, match="resolves outside the sandbox"):
        create_sandbox(malicious_patch, target_file='/etc/passwd')


def test_syntax_invalid_patch_is_rejected():
    invalid_patch = {
        'explanation': 'invalid syntax',
        'patched_code': 'print("broken"',
        'risk_notes': 'none',
        'syntax_valid': False,
    }
    with pytest.raises(ValueError, match="invalid syntax"):
        create_sandbox(invalid_patch, target_file='pipeline/run_pipeline.py')

