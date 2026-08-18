import subprocess
import uuid
from pathlib import Path


def create_fix_branch(patch_result, diagnosis, finding_type, target_file='pipeline/run_pipeline.py', repo_path='.'):
    """
    Creates a new local git branch, applies the validated patch, commits it with a meaningful message,
    and returns to the original branch, leaving the working directory completely clean.
    """
    # 0. Precondition: Ensure the working directory is clean before we start
    status_result = subprocess.run(['git', 'status', '--porcelain'], 
                                   cwd=repo_path, capture_output=True, text=True, check=True)
    if status_result.stdout.strip():
        raise RuntimeError("Refusing to proceed: The working directory is not clean. "
                           "Please commit or stash your changes before running DataMedic.")

    # 1. Get current branch name so we can restore it later
    result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                            cwd=repo_path, capture_output=True, text=True, check=True)
    original_branch = result.stdout.strip()
    
    # 2. Create and checkout new branch
    short_id = uuid.uuid4().hex[:8]
    branch_name = f"datamedic-fix/{finding_type}-{short_id}"
    subprocess.run(['git', 'checkout', '-b', branch_name], cwd=repo_path, check=True, capture_output=True)
    
    try:
        # 3. Apply the patch to the target file
        target_path = Path(repo_path) / target_file
        target_path.write_text(patch_result['patched_code'])
        
        # 4. Stage and commit the change
        subprocess.run(['git', 'add', target_file], cwd=repo_path, check=True, capture_output=True)
        
        # Construct plain-English commit message
        summary = patch_result.get('explanation', 'Fixed data quality issue').strip()
        root_cause = diagnosis.get('root_cause', 'Unknown root cause').strip()
        
        commit_msg = f"Fix {finding_type}: {summary}\n\nDiagnosis: {root_cause}"
        
        subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_path, check=True, capture_output=True)
        
    finally:
        # 5. Restore original branch (leaves working directory clean/unpatched)
        # Guarantee no dirty state is carried over if a failure occurred mid-operation
        subprocess.run(['git', 'reset', '--hard', 'HEAD'], cwd=repo_path, check=True, capture_output=True)
        subprocess.run(['git', 'clean', '-fd'], cwd=repo_path, check=True, capture_output=True)
        
        subprocess.run(['git', 'checkout', original_branch], cwd=repo_path, check=True, capture_output=True)
        
    return branch_name
