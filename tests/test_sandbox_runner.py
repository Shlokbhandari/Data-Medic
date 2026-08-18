import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from sandbox import create_sandbox, run_in_sandbox, cleanup_sandbox

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORDERS_CSV = str(PROJECT_ROOT / 'data' / 'orders.csv')
REAL_PROCESSED = PROJECT_ROOT / 'data' / 'processed_orders.csv'

IDENTITY_PATCH = {
    'explanation': 'no change',
    'patched_code': (PROJECT_ROOT / 'pipeline' / 'run_pipeline.py').read_text(),
    'risk_notes': 'none',
    'syntax_valid': True,
}

BROKEN_PATCH = {
    'explanation': 'deliberately broken',
    'patched_code': 'raise RuntimeError("intentional crash")\n',
    'risk_notes': 'none',
    'syntax_valid': True,
}


def test_successful_run_returns_zero_with_output():
    result = create_sandbox(IDENTITY_PATCH, target_file='pipeline/run_pipeline.py')
    sandbox_path = result['sandbox_path']
    try:
        run_result = run_in_sandbox(sandbox_path, ORDERS_CSV)
        assert run_result['exit_code'] == 0
        assert run_result['output_csv_exists'] is True
        assert run_result['output_df'] is not None
        assert len(run_result['output_df']) > 0
    finally:
        cleanup_sandbox(sandbox_path)


def test_broken_pipeline_returns_nonzero_with_stderr():
    result = create_sandbox(BROKEN_PATCH, target_file='pipeline/run_pipeline.py')
    sandbox_path = result['sandbox_path']
    try:
        run_result = run_in_sandbox(sandbox_path, ORDERS_CSV)
        assert run_result['exit_code'] != 0
        assert 'intentional crash' in run_result['stderr']
        assert run_result['output_csv_exists'] is False
    finally:
        cleanup_sandbox(sandbox_path)


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


def test_real_repo_untouched_by_run():
    before_snapshot = _snapshot_repo()
    result = create_sandbox(IDENTITY_PATCH, target_file='pipeline/run_pipeline.py')
    sandbox_path = result['sandbox_path']
    try:
        run_in_sandbox(sandbox_path, ORDERS_CSV)
        after_snapshot = _snapshot_repo()
        assert before_snapshot == after_snapshot
    finally:
        cleanup_sandbox(sandbox_path)
