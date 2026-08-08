import pandas as pd
from monitor import check_data
from evidence import collect_evidence
from diagnose import diagnose


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

        print(f"{'='*60}")
        print(f"Finding #{i}")
        print(f"{'='*60}")
        print(f"  Issue:    {finding['issue']}")
        print(f"  Severity: {finding['severity'].upper()}")
        print(f"  Column:   {evidence['column']}")
        print(f"  Rows affected: {evidence['total_affected_in_dataset']}")
        print()
        print(f"  Diagnosis (via {backend}):")
        print(f"    Root cause:  {diagnosis.get('root_cause', 'N/A')}")
        print(f"    Confidence:  {diagnosis.get('confidence', 'N/A')}")
        print(f"    Reasoning:   {diagnosis.get('reasoning', 'N/A')}")
        print()


if __name__ == "__main__":
    main()
