import pandas as pd
from monitor import check_data
from evidence import collect_evidence
from diagnose import diagnose
from confidence_gate import should_proceed
from patch import generate_patch


def main():
    df = pd.read_csv('data/orders_broken.csv')
    print(f"Loaded {len(df)} rows from orders_broken.csv\n")

    findings = check_data(df)

    # Find the duplicate-transaction-id finding specifically
    dup_finding = None
    for f in findings:
        if f['column'] == 'transaction_id':
            dup_finding = f
            break

    if not dup_finding:
        print("No duplicate transaction_id finding detected.")
        return

    evidence = collect_evidence(dup_finding, df)
    diagnosis_result, diag_backend = diagnose(evidence)
    gate_result = should_proceed(diagnosis_result)

    print(f"Finding: {dup_finding['issue']}")
    print(f"Diagnosis (via {diag_backend}): {diagnosis_result.get('root_cause', 'N/A')}")
    print(f"Confidence: {diagnosis_result.get('confidence', 'N/A')}")
    print(f"Gate decision: {gate_result['decision'].upper()} — {gate_result['reason']}")
    print()

    if gate_result['decision'] != 'proceed':
        print("Gate says escalate — not generating a patch.")
        return

    # Read the current pipeline code
    with open('pipeline/run_pipeline.py', 'r') as f:
        current_code = f.read()

    patch_result, patch_backend = generate_patch(diagnosis_result, evidence, current_code)

    print(f"{'='*60}")
    print(f"PROPOSED PATCH (generated via {patch_backend})")
    print(f"{'='*60}")
    print()
    print(f"Explanation:")
    print(f"  {patch_result.get('explanation', 'N/A')}")
    print()
    print(f"Risk notes:")
    print(f"  {patch_result.get('risk_notes', 'N/A')}")
    print()
    print(f"Patched code:")
    print(f"{'-'*60}")
    print(patch_result.get('patched_code', 'N/A'))
    print(f"{'-'*60}")


if __name__ == "__main__":
    main()
