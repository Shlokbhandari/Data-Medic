"""
run_live_demo.py

This is a reference script that demonstrates the full DataMedic automated pipeline end-to-end.
It loads broken data, detects issues, diagnoses the root cause, gates execution, generates a patch, 
validates the patch safely in a sandbox, creates a local fix branch, and finally opens a real GitHub 
Pull Request for human review.

How to run (from the project root):
    source venv/bin/activate
    python pipeline/run_live_demo.py

Note: Requires a valid GITHUB_TOKEN in your .env file with repo access.
"""

import sys
import pandas as pd
from pathlib import Path

# Add pipeline directory to path so we can import its modules
sys.path.insert(0, str(Path(__file__).parent / 'pipeline'))

from monitor import check_data
from evidence import collect_evidence
from diagnose import diagnose
from confidence_gate import should_proceed
from retry_controller import generate_and_validate_with_retry
from propose_fix import create_fix_branch
from github_pr import push_and_create_pr

def run_e2e():
    print("🚀 Starting DataMedic Live Run...")

    print("\n1. Loading broken data...")
    df = pd.read_csv('data/orders_broken.csv')
    
    print("2. Monitoring for issues...")
    findings = check_data(df)
    finding = next((f for f in findings if f['column'] == 'transaction_id'), None)
    
    if not finding:
        print("❌ FAILED: Could not find duplicate_transaction_id issue in data.")
        return
        
    print(f"   Found: {finding['issue']}")

    print("\n3. Collecting evidence...")
    evidence = collect_evidence(finding, df)

    print("4. Diagnosing root cause...")
    diagnosis, _ = diagnose(evidence)
    print(f"   Root Cause: {diagnosis.get('root_cause', 'Unknown')}")
    print(f"   Confidence: {diagnosis.get('confidence', 'Unknown')}")

    print("\n5. Checking confidence gate...")
    gate = should_proceed(diagnosis)
    print(f"   Decision: {gate['decision'].upper()}")
    if gate['decision'] != 'proceed':
        print(f"❌ STOPPING: Confidence gate decided to escalate. Reason: {gate.get('reasoning')}")
        return

    print("\n6. Generating and validating patch (with retries)...")
    with open('pipeline/run_pipeline.py', 'r') as f:
        current_code = f.read()
        
    result = generate_and_validate_with_retry(
        diagnosis=diagnosis, 
        evidence=evidence, 
        current_code=current_code, 
        finding_type='duplicate_transaction_id',
        max_attempts=3
    )

    if not result['success']:
        print("❌ FAILED: Could not generate a valid patch that passes sandbox validation.")
        print(f"   Escalation Reason: {result.get('escalation_reason')}")
        for attempt in result['attempts']:
            print(f"   - Attempt {attempt['attempt']} Failed: {attempt.get('failure_reason')}")
        return
        
    print(f"   Success! (Took {result['total_attempts']} attempt(s))")
    print(f"   Patch Explanation: {result['patch']['explanation']}")

    print("\n7. Creating local fix branch...")
    try:
        branch_name = create_fix_branch(
            patch_result=result['patch'], 
            diagnosis=diagnosis, 
            finding_type='duplicate_transaction_id'
        )
        print(f"   Branch created and patch committed locally: {branch_name}")
    except Exception as e:
        print(f"❌ FAILED during local branch creation: {str(e)}")
        return

    print("\n8. Pushing to GitHub and opening Pull Request...")
    try:
        # We need the specific validation result from the final successful attempt
        winning_validation = result['attempts'][-1]
        
        pr_url = push_and_create_pr(
            branch_name=branch_name, 
            patch=result['patch'], 
            diagnosis=diagnosis, 
            evidence=evidence,
            finding_type='duplicate_transaction_id', 
            validation_result=winning_validation
        )
        print("\n" + "="*60)
        print(f"✅ SUCCESS! Pull Request created successfully:")
        print(f"🔗 {pr_url}")
        print("="*60 + "\n")
    except Exception as e:
        print(f"❌ FAILED during GitHub push/PR creation: {str(e)}")
        return

if __name__ == '__main__':
    run_e2e()
