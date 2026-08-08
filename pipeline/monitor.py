import pandas as pd


def check_data(df):
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

    return findings
