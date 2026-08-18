import tempfile
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIRS_TO_COPY = ['pipeline', 'data']

SANDBOX_TIMEOUT_SECONDS = 30


def create_sandbox(patch, target_file):
    """Creates an isolated copy of the project, applies the patch to the target file,
    and returns the sandbox path plus a record of what changed.

    The patch dict must have a 'patched_code' field (as returned by generate_patch()).
    The target_file is a path relative to the project root."""

    if patch.get('syntax_valid') is not True:
        raise ValueError("Refusing to proceed: Patch contains invalid syntax (syntax_valid is not True).")

    sandbox_path = Path(tempfile.mkdtemp(prefix='datamedic_sandbox_'))

    for dir_name in DIRS_TO_COPY:
        src = PROJECT_ROOT / dir_name
        dst = sandbox_path / dir_name
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__'))

    target = (sandbox_path / target_file).resolve()
    resolved_sandbox = sandbox_path.resolve()

    if not target.is_relative_to(resolved_sandbox):
        shutil.rmtree(sandbox_path)
        raise ValueError(f"Security error: Target file '{target_file}' resolves outside the sandbox.")

    if not target.exists():
        shutil.rmtree(sandbox_path)
        raise FileNotFoundError(
            f"Target file '{target_file}' does not exist in the sandbox. "
            f"Refusing to create a new file — the patch must target an existing file."
        )

    original_code = target.read_text()
    target.write_text(patch['patched_code'])

    return {
        'sandbox_path': str(sandbox_path),
        'target_file': target_file,
        'original_code': original_code,
        'patched_code': patch['patched_code'],
    }


def run_in_sandbox(sandbox_path, input_csv):
    """Runs pipeline/run_pipeline.py inside the sandbox as a subprocess.

    Copies input_csv over data/orders.csv in the sandbox before running,
    so the hardcoded path in run_pipeline.py reads the intended input.

    Returns a structured result with raw facts — no pass/fail judgment."""

    sandbox = Path(sandbox_path)

    sandbox_input = sandbox / 'data' / 'orders.csv'
    shutil.copy2(input_csv, sandbox_input)

    output_csv_path = sandbox / 'data' / 'processed_orders.csv'
    if output_csv_path.exists():
        output_csv_path.unlink()

    flagged_csv_path = sandbox / 'data' / 'flagged_orders.csv'
    if flagged_csv_path.exists():
        flagged_csv_path.unlink()

    try:
        proc = subprocess.run(
            [sys.executable, 'pipeline/run_pipeline.py'],
            cwd=str(sandbox),
            capture_output=True,
            text=True,
            timeout=SANDBOX_TIMEOUT_SECONDS,
        )
        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ''
        stderr = f'Pipeline timed out after {SANDBOX_TIMEOUT_SECONDS} seconds'

    output_csv_exists = output_csv_path.exists()
    output_df = None
    if output_csv_exists:
        output_df = pd.read_csv(output_csv_path)
        
    flagged_csv_exists = flagged_csv_path.exists()
    flagged_df = None
    if flagged_csv_exists:
        flagged_df = pd.read_csv(flagged_csv_path)

    return {
        'exit_code': exit_code,
        'stdout': stdout,
        'stderr': stderr,
        'output_csv_exists': output_csv_exists,
        'output_df': output_df,
        'flagged_csv_exists': flagged_csv_exists,
        'flagged_df': flagged_df,
    }


def cleanup_sandbox(path):
    """Removes the sandbox directory entirely."""
    shutil.rmtree(path, ignore_errors=True)
