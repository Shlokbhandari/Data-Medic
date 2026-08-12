import os
import subprocess
from dotenv import load_dotenv
from github import Github, GithubException


def push_and_create_pr(branch_name, patch, diagnosis, evidence, finding_type, validation_result):
    """
    Pushes the local fix branch to origin and creates a Pull Request via the GitHub API.
    Builds a plain-English PR body summarizing the diagnosis, evidence, and validation results.
    """
    load_dotenv()
    token = os.environ.get('GITHUB_TOKEN')
    
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable not set. Cannot create PR.")

    # 1. Parse repository owner and name from local git remote
    result = subprocess.run(['git', 'remote', 'get-url', 'origin'], 
                            capture_output=True, text=True, check=True)
    remote_url = result.stdout.strip()
    
    # Handle both https and ssh formats
    if remote_url.startswith('https://github.com/'):
        owner_repo = remote_url.replace('https://github.com/', '').replace('.git', '')
    elif remote_url.startswith('git@github.com:'):
        owner_repo = remote_url.replace('git@github.com:', '').replace('.git', '')
    else:
        raise ValueError(f"Unrecognized github remote format: {remote_url}")

    # 2. Push branch to origin
    subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True, capture_output=True)

    # 3. Authenticate with GitHub API
    g = Github(token)
    try:
        repo = g.get_repo(owner_repo)
    except GithubException as e:
        if e.status == 401:
            raise PermissionError("GITHUB_TOKEN is invalid or expired.")
        elif e.status == 404:
            raise PermissionError(f"GITHUB_TOKEN does not have access to repo {owner_repo} or it does not exist.")
        raise

    # 4. Construct PR Content
    summary = patch.get('explanation', 'Fixed data quality issue').strip()
    
    # Truncate summary for title if too long
    title_summary = summary if len(summary) < 60 else summary[:57] + '...'
    pr_title = f"Fix: {finding_type} - {title_summary}"
    
    root_cause = diagnosis.get('root_cause', 'Unknown')
    confidence = diagnosis.get('confidence', 'N/A')
    reasoning = diagnosis.get('reasoning', 'Unknown')
    
    # Evidence formatting
    issue = evidence.get('finding', {}).get('issue', 'Unknown issue')
    rows_affected = evidence.get('total_affected_in_dataset', 'Unknown')
    
    # Validation formatting
    reg_check = validation_result.get('regression_check', {})
    reg_pass = "✅ PASS" if reg_check.get('passed') else "❌ FAIL"
    reg_exp = reg_check.get('explanation', 'No explanation')
    
    iss_check = validation_result.get('issue_check', {})
    iss_pass = "✅ PASS" if iss_check.get('passed') else "❌ FAIL"
    iss_exp = iss_check.get('explanation', 'No explanation')

    pr_body = f"""### DataMedic Automated Fix

## Evidence
- **Issue Found**: {issue}
- **Rows Affected**: {rows_affected}

## Diagnosis
- **Root Cause**: {root_cause}
- **Confidence**: {confidence}
- **Reasoning**: {reasoning}

## Proposed Fix
{summary}

## Sandbox Validation Results
- **Regression Check** [{reg_pass}]: {reg_exp}
- **Issue-Specific Check** [{iss_pass}]: {iss_exp}
"""

    # 5. Open PR
    pull_request = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base="main"
    )

    return pull_request.html_url
