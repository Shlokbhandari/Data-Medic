import sys
import os
import subprocess
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from propose_fix import create_fix_branch


@pytest.fixture
def dummy_git_repo(tmp_path):
    """
    Creates a temporary dummy git repository to safely test branching and committing
    without affecting the real DataMedic repository.
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    
    # Initialize repo
    subprocess.run(['git', 'init'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=repo_dir, check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.com'], cwd=repo_dir, check=True)
    
    # Create the pipeline dir and a dummy run_pipeline.py
    pipeline_dir = repo_dir / 'pipeline'
    pipeline_dir.mkdir()
    target_file = pipeline_dir / 'run_pipeline.py'
    target_file.write_text('print("original code")\n')
    
    # Commit it to 'main'
    subprocess.run(['git', 'add', '.'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=repo_dir, check=True, capture_output=True)
    
    # Get the name of the main branch (could be 'main' or 'master' depending on git config)
    result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                            cwd=repo_dir, capture_output=True, text=True, check=True)
    original_branch = result.stdout.strip()
    
    return repo_dir, original_branch, 'pipeline/run_pipeline.py'


def test_create_fix_branch(dummy_git_repo):
    repo_dir, original_branch, target_file_rel = dummy_git_repo
    
    patch_result = {
        'patched_code': 'print("patched code")\n',
        'explanation': 'Sorted duplicates by date so the oldest is kept.',
        'syntax_valid': True,
    }
    diagnosis = {
        'root_cause': 'Upstream system occasionally resends the exact same transaction ID.'
    }
    finding_type = 'duplicate_transaction_id'
    
    # 1. Run the function
    branch_name = create_fix_branch(
        patch_result=patch_result,
        diagnosis=diagnosis,
        finding_type=finding_type,
        target_file=target_file_rel,
        repo_path=str(repo_dir)
    )
    
    # 2. Confirm a new branch was created with the correct naming convention
    assert branch_name.startswith('datamedic-fix/duplicate_transaction_id-')
    assert branch_name != original_branch
    
    # 3. Confirm the working directory is currently back on the original branch
    current_branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                    cwd=repo_dir, capture_output=True, text=True).stdout.strip()
    assert current_branch == original_branch
    
    # 4. Confirm the original branch still has the original unpatched file
    target_file_path = repo_dir / target_file_rel
    assert target_file_path.read_text() == 'print("original code")\n'
    
    # 5. Switch to the new branch and confirm it has the patched code
    subprocess.run(['git', 'checkout', branch_name], cwd=repo_dir, check=True, capture_output=True)
    assert target_file_path.read_text() == 'print("patched code")\n'
    
    # 6. Confirm the commit message contains the required human-readable context
    log_result = subprocess.run(['git', 'log', '-1', '--pretty=format:%B'], 
                                cwd=repo_dir, capture_output=True, text=True, check=True)
    commit_msg = log_result.stdout
    assert 'Fix duplicate_transaction_id' in commit_msg
    assert 'Sorted duplicates by date' in commit_msg
    assert 'Upstream system occasionally resends' in commit_msg


def test_create_fix_branch_dirty_state_raises_error(dummy_git_repo):
    repo_dir, original_branch, target_file_rel = dummy_git_repo
    
    # Make the repo dirty
    (repo_dir / "untracked_file.txt").write_text("dirty")
    
    with pytest.raises(RuntimeError, match="working directory is not clean"):
        create_fix_branch(
            patch_result={'patched_code': 'fake', 'syntax_valid': True},
            diagnosis={'root_cause': 'fake'},
            finding_type='test',
            target_file=target_file_rel,
            repo_path=str(repo_dir)
        )
        
    # Confirm it stayed on the original branch
    current_branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                    cwd=repo_dir, capture_output=True, text=True).stdout.strip()
    assert current_branch == original_branch


def test_create_fix_branch_mid_operation_failure_restores_clean_state(dummy_git_repo, monkeypatch):
    repo_dir, original_branch, target_file_rel = dummy_git_repo
    
    # We will simulate a failure during 'git commit' by replacing subprocess.run
    original_run = subprocess.run
    
    def mocked_run(args, **kwargs):
        if args[:2] == ['git', 'commit']:
            raise RuntimeError("Simulated failure during commit")
        return original_run(args, **kwargs)
        
    monkeypatch.setattr(subprocess, "run", mocked_run)
    
    with pytest.raises(RuntimeError, match="Simulated failure during commit"):
        create_fix_branch(
            patch_result={'patched_code': 'print("patched code")\n', 'explanation': 'test', 'syntax_valid': True},
            diagnosis={'root_cause': 'fake'},
            finding_type='test',
            target_file=target_file_rel,
            repo_path=str(repo_dir)
        )
        
    # Check that we are back on original branch
    current_branch = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                    cwd=repo_dir, capture_output=True, text=True).stdout.strip()
    assert current_branch == original_branch
    
    # Check that repo is clean
    status = subprocess.run(['git', 'status', '--porcelain'], 
                            cwd=repo_dir, capture_output=True, text=True).stdout.strip()
    assert status == ""


def test_create_fix_branch_syntax_invalid_patch_is_rejected(dummy_git_repo):
    repo_dir, _, target_file_rel = dummy_git_repo
    with pytest.raises(ValueError, match="invalid syntax"):
        create_fix_branch(
            patch_result={'patched_code': 'fake', 'syntax_valid': False},
            diagnosis={'root_cause': 'fake'},
            finding_type='test',
            target_file=target_file_rel,
            repo_path=str(repo_dir)
        )

