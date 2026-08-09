import pandas as pd
from monitor import check_data
from evidence import collect_evidence
from diagnose import diagnose
from confidence_gate import should_proceed


def main():
    df = pd.read_csv('data/orders_broken.csv')
    print(f"Loaded {len(df)} rows from orders_broken.csv\n")

    findings = check_data(df)

    if not findings:
        print("No issues found.")
        return

    for i, finding in enumerate(findings, 1):
        evidence = collect_evidence(finding, df)
        diagnosis, backend = diagnose(evidence)
        gate_result = should_proceed(diagnosis)

        print(f"{'='*60}")
        print(f"Finding #{i}: {finding['issue']}")
        print(f"  Severity:   {finding['severity'].upper()}")
        print(f"  Confidence: {diagnosis.get('confidence', 'N/A')}")
        print(f"  Decision:   {gate_result['decision'].upper()}")
        print(f"  Reason:     {gate_result['reason']}")
        print()


if __name__ == "__main__":
    main()
