import os
import pandas as pd


BASELINE_CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'orders.csv')

COLUMNS_WITH_DEDICATED_CHECKS = {'price'}


def check_data(df, baseline_path=None):
    """Scans a DataFrame for common data problems and returns a list of findings.
    Each finding is a dict with: row index, order_id, column, severity, and a plain-English description.
    Nothing is dropped or modified — this only observes and reports."""

    findings = []

    # Duplicates: keep the first occurrence, flag the rest
    dup_mask = df.duplicated(subset=['transaction_id'], keep='first')
    for idx in df[dup_mask].index:
        row = df.loc[idx]
        findings.append({
            'row': int(idx),
            'order_id': row['order_id'],
            'column': 'transaction_id',
            'severity': 'high',
            'issue': f"Duplicate transaction_id '{row['transaction_id']}' — this row repeats a transaction that already appears earlier"
        })

    # Null prices
    null_mask = df['price'].isna()
    for idx in df[null_mask].index:
        row = df.loc[idx]
        findings.append({
            'row': int(idx),
            'order_id': row['order_id'],
            'column': 'price',
            'severity': 'high',
            'issue': 'Price is missing (null/empty)'
        })

    # Zero prices — suspicious but not necessarily wrong, so just flagged
    zero_mask = df['price'] == 0
    for idx in df[zero_mask].index:
        row = df.loc[idx]
        findings.append({
            'row': int(idx),
            'order_id': row['order_id'],
            'column': 'price',
            'severity': 'medium',
            'issue': 'Price is exactly 0, which is unusual and may indicate a parsing bug or bad source data'
        })

    # Baseline null-rate drift: compare against the known-clean reference dataset
    baseline_findings = _check_baseline_null_drift(df, baseline_path or BASELINE_CSV_PATH)
    findings.extend(baseline_findings)

    return findings


def _check_baseline_null_drift(df, baseline_path):
    """Compares per-column null rates in the incoming data against the known-clean
    baseline. Only checks columns not already covered by dedicated checks.
    Returns one finding per drifted column, with all affected row indices included."""

    findings = []

    if not os.path.exists(baseline_path):
        return findings

    baseline_df = pd.read_csv(baseline_path)

    for col in df.columns:
        if col in COLUMNS_WITH_DEDICATED_CHECKS:
            continue

        baseline_null_rate = baseline_df[col].isna().mean() if col in baseline_df.columns else 0.0
        current_null_rate = df[col].isna().mean()

        if current_null_rate > baseline_null_rate:
            null_indices = df.index[df[col].isna()].tolist()

            first_idx = null_indices[0]
            total_nulls = len(null_indices)
            total_rows = len(df)

            findings.append({
                'row': int(first_idx),
                'order_id': df.loc[first_idx, 'order_id'],
                'column': col,
                'severity': 'high',
                'issue': f"Baseline drift: null rate in '{col}' is {current_null_rate:.1%} ({total_nulls}/{total_rows} rows), expected {baseline_null_rate:.1%} from baseline",
                'affected_row_indices': [int(i) for i in null_indices],
            })

    return findings

