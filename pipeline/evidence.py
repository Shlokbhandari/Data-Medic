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

    return evidence
