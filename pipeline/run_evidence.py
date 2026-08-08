import pandas as pd
import json
from monitor import check_data
from evidence import collect_evidence


def main():
    df = pd.read_csv('data/orders_broken.csv')
    print(f"Loaded {len(df)} rows from orders_broken.csv\n")

    findings = check_data(df)

    if not findings:
        print("No issues found.")
        return

    for i, finding in enumerate(findings, 1):
        evidence = collect_evidence(finding, df)

        print(f"--- Evidence for finding #{i} ---")
        print(f"  Issue: {finding['issue']}")
        print(f"  Severity: {finding['severity'].upper()}")
        print(f"  Column: {evidence['column']}")
        print(f"  Total rows affected by this type of issue: {evidence['total_affected_in_dataset']}")
        print(f"  Affected row(s):")
        for row in evidence['affected_rows']:
            print(f"    {row}")
        if 'column_stats' in evidence:
            stats = evidence['column_stats']
            print(f"  Column stats (from clean rows): min={stats['min']}, max={stats['max']}, mean={stats['mean']}, median={stats['median']}")
        print()


if __name__ == "__main__":
    main()
