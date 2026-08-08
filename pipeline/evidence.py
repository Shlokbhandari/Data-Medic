import pandas as pd


def collect_evidence(finding, df):
    """Gathers raw facts about a single finding from the monitor.
    Returns a structured dict with the affected rows, column, scope of the issue,
    and the monitor's original description. No reasoning or diagnosis happens here."""

    column = finding['column']
    evidence = {
        'finding': finding,
        'column': column,
        'affected_rows': [],
        'total_affected_in_dataset': 0,
    }

    if finding['severity'] == 'high' and column == 'transaction_id':
        # Grab all rows that share this duplicated value
        dup_value = df.loc[finding['row'], 'transaction_id']
        matching = df[df['transaction_id'] == dup_value]
        evidence['affected_rows'] = matching.to_dict('records')
        evidence['total_affected_in_dataset'] = int(df.duplicated(subset=['transaction_id'], keep=False).sum())

    elif column == 'price' and pd.isna(df.loc[finding['row'], 'price']):
        evidence['affected_rows'] = [df.loc[finding['row']].to_dict()]
        evidence['total_affected_in_dataset'] = int(df['price'].isna().sum())

    elif column == 'price' and df.loc[finding['row'], 'price'] == 0:
        zero_rows = df[df['price'] == 0]
        evidence['affected_rows'] = zero_rows.to_dict('records')
        evidence['total_affected_in_dataset'] = len(zero_rows)

    # Include summary stats for the column from clean rows, so the diagnosis
    # step can see what "normal" looks like and compare against the flagged value
    if column in df.columns and pd.api.types.is_numeric_dtype(df[column]):
        clean = df[column].dropna()
        clean = clean[clean != 0] if finding.get('issue', '').startswith('Price is exactly 0') else clean
        if not clean.empty:
            evidence['column_stats'] = {
                'min': round(float(clean.min()), 2),
                'max': round(float(clean.max()), 2),
                'mean': round(float(clean.mean()), 2),
                'median': round(float(clean.median()), 2),
            }

    return evidence
