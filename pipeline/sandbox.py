import tempfile
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIRS_TO_COPY = ['pipeline', 'data']


def create_sandbox(patch, target_file):
    """Creates an isolated copy of the project, applies the patch to the target file,
    and returns the sandbox path plus a record of what changed.

    The patch dict must have a 'patched_code' field (as returned by generate_patch()).
    The target_file is a path relative to the project root."""

    sandbox_path = Path(tempfile.mkdtemp(prefix='datamedic_sandbox_'))

    for dir_name in DIRS_TO_COPY:
        src = PROJECT_ROOT / dir_name
        dst = sandbox_path / dir_name
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__'))

    target = sandbox_path / target_file
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


def cleanup_sandbox(path):
    """Removes the sandbox directory entirely."""
    shutil.rmtree(path, ignore_errors=True)
