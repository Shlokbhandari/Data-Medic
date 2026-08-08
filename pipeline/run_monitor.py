import pandas as pd
from monitor import check_data


def main():
    df = pd.read_csv('data/orders_broken.csv')
    print(f"Loaded {len(df)} rows from orders_broken.csv\n")

    findings = check_data(df)

    if not findings:
        print("No issues found.")
        return

    print(f"Found {len(findings)} issue(s):\n")
    for f in findings:
        print(f"  [Row {f['row']}] Order {f['order_id']}, column '{f['column']}':")
        print(f"    → {f['issue']}\n")


if __name__ == "__main__":
    main()
