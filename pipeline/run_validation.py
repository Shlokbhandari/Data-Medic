import pandas as pd
from monitor import check_data
from evidence import collect_evidence
from diagnose import diagnose
from confidence_gate import should_proceed
from patch import generate_patch
from sandbox import create_sandbox, run_in_sandbox, cleanup_sandbox
from validate import check_no_regression, check_issue_addressed


def main():
    df = pd.read_csv('data/orders_broken.csv')
    print(f"Loaded {len(df)} rows from orders_broken.csv\n")

    findings = check_data(df)
    dup_finding = next((f for f in findings if f['column'] == 'transaction_id'), None)
    if not dup_finding:
        print("No duplicate transaction_id finding detected.")
        return

    evidence = collect_evidence(dup_finding, df)
    diagnosis_result, diag_backend = diagnose(evidence)
    gate_result = should_proceed(diagnosis_result)

    print(f"Finding: {dup_finding['issue']}")
    print(f"Diagnosis: {diagnosis_result.get('root_cause', 'N/A')}")
    print(f"Confidence: {diagnosis_result.get('confidence', 'N/A')}")
    print(f"Gate: {gate_result['decision'].upper()}")
    print()

    if gate_result['decision'] != 'proceed':
        print("Gate says escalate — stopping here.")
        return

    with open('pipeline/run_pipeline.py', 'r') as f:
        current_code = f.read()

    patch_result, patch_backend = generate_patch(diagnosis_result, evidence, current_code)
    print(f"Patch generated via {patch_backend}")
    print()

    # --- Baseline run (unpatched pipeline) ---
    identity_patch = {'patched_code': current_code}
    baseline_sandbox = create_sandbox(identity_patch, target_file='pipeline/run_pipeline.py')
    baseline_result = run_in_sandbox(baseline_sandbox['sandbox_path'], 'data/orders_broken.csv')
    cleanup_sandbox(baseline_sandbox['sandbox_path'])

    # --- Patched run ---
    patched_sandbox = create_sandbox(patch_result, target_file='pipeline/run_pipeline.py')
    patched_result = run_in_sandbox(patched_sandbox['sandbox_path'], 'data/orders_broken.csv')
    cleanup_sandbox(patched_sandbox['sandbox_path'])

    print(f"Baseline: exit={baseline_result['exit_code']}, rows={len(baseline_result['output_df']) if baseline_result['output_df'] is not None else 'N/A'}")
    print(f"Patched:  exit={patched_result['exit_code']}, rows={len(patched_result['output_df']) if patched_result['output_df'] is not None else 'N/A'}")
    print()

    # --- Validation ---
    regression = check_no_regression(baseline_result, patched_result)
    issue_check = check_issue_addressed('duplicate_transaction_id', baseline_result, patched_result)

    print(f"{'='*60}")
    print(f"VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"  Regression check: {'PASS' if regression['passed'] else 'FAIL'}")
    print(f"    {regression['explanation']}")
    print(f"  Issue addressed:  {'PASS' if issue_check['passed'] else 'FAIL' if issue_check['passed'] is False else 'SKIPPED'}")
    print(f"    {issue_check['explanation']}")
    print()

    if regression['passed'] and issue_check['passed']:
        print("VERDICT: Safe to propose — both checks passed.")
    else:
        print("VERDICT: NOT safe to propose.")
        if not regression['passed']:
            print(f"  FAILED: Regression check — {regression['explanation']}")
        if not issue_check['passed']:
            print(f"  FAILED: Issue addressed check — {issue_check['explanation']}")


if __name__ == "__main__":
    main()
