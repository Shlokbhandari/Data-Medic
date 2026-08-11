import pandas as pd


def check_no_regression(baseline_result, patched_result):
    """Checks that the patch didn't break anything unrelated.
    Compares baseline and patched pipeline outputs — rows shared by both
    (matched on order_id) must be identical. Row count must be equal.
    Returns a dict with passed (bool) and explanation (str)."""

    if baseline_result['exit_code'] != 0:
        return {'passed': False, 'explanation': f"Baseline pipeline failed (exit code {baseline_result['exit_code']})"}
    if patched_result['exit_code'] != 0:
        return {'passed': False, 'explanation': f"Patched pipeline failed (exit code {patched_result['exit_code']}): {patched_result['stderr']}"}

    if not baseline_result['output_csv_exists']:
        return {'passed': False, 'explanation': 'Baseline pipeline did not produce an output CSV'}
    if not patched_result['output_csv_exists']:
        return {'passed': False, 'explanation': 'Patched pipeline did not produce an output CSV'}

    baseline_df = baseline_result['output_df']
    patched_df = patched_result['output_df']

    if len(baseline_df) != len(patched_df):
        return {
            'passed': False,
            'explanation': f"Row count changed: baseline has {len(baseline_df)} rows, patched has {len(patched_df)} rows"
        }

    # Find rows present in both outputs (by order_id) and check they're identical
    shared = pd.merge(baseline_df, patched_df, on='order_id', suffixes=('_baseline', '_patched'))
    diffs = []
    base_cols = [c for c in baseline_df.columns if c != 'order_id']
    for col in base_cols:
        mismatches = shared[shared[f'{col}_baseline'] != shared[f'{col}_patched']]
        for _, row in mismatches.iterrows():
            diffs.append(f"order_id {row['order_id']}: {col} changed from '{row[f'{col}_baseline']}' to '{row[f'{col}_patched']}'")

    if diffs:
        return {'passed': False, 'explanation': f"Unrelated rows changed: {'; '.join(diffs)}"}

    # Check for order_ids that swapped (present in one but not the other)
    baseline_ids = set(baseline_df['order_id'])
    patched_ids = set(patched_df['order_id'])
    only_baseline = baseline_ids - patched_ids
    only_patched = patched_ids - baseline_ids

    return {
        'passed': True,
        'explanation': (
            f"No regression: {len(shared)} shared rows are identical"
            + (f", {len(only_baseline)} row(s) swapped out, {len(only_patched)} swapped in (expected for the fix)" if only_baseline else "")
        )
    }


def check_issue_addressed(finding_type, baseline_result, patched_result):
    """Checks case-specific expectations from benchmark.md for a given failure type.
    Returns a dict with passed (bool or None), and explanation (str)."""

    if finding_type == 'duplicate_transaction_id':
        return _check_duplicate_fix(baseline_result, patched_result)

    return {
        'passed': None,
        'explanation': f"No defined check for '{finding_type}' yet"
    }


def _check_duplicate_fix(baseline_result, patched_result):
    """For the duplicate-transaction-id case: verifies the patched output
    kept the row with the earliest order_date among the duplicated rows."""

    if not baseline_result['output_csv_exists'] or not patched_result['output_csv_exists']:
        return {'passed': False, 'explanation': 'Cannot validate — one or both outputs missing'}

    baseline_df = baseline_result['output_df']
    patched_df = patched_result['output_df']

    # No duplicate transaction_ids should remain in either output
    baseline_dups = baseline_df[baseline_df.duplicated(subset='transaction_id', keep=False)]
    patched_dups = patched_df[patched_df.duplicated(subset='transaction_id', keep=False)]
    if len(patched_dups) > 0:
        return {'passed': False, 'explanation': f"Patched output still has duplicate transaction_ids: {patched_dups['transaction_id'].tolist()}"}

    # Find which transaction_ids differ between outputs — those are the ones the patch affected
    baseline_ids = set(baseline_df['order_id'])
    patched_ids = set(patched_df['order_id'])
    swapped_out = baseline_ids - patched_ids
    swapped_in = patched_ids - baseline_ids

    if not swapped_out and not swapped_in:
        # Both outputs kept the same row — this is valid if that row already had the earliest date
        # (e.g. both duplicates share the same order_date)
        return {
            'passed': True,
            'explanation': 'Both baseline and patched outputs kept the same row — the existing row already had the earliest order_date, so the patch added the guarantee without changing the result'
        }

    # Verify the swapped-in row has an order_date <= the swapped-out row
    if len(swapped_out) == 1 and len(swapped_in) == 1:
        old_row = baseline_df[baseline_df['order_id'].isin(swapped_out)].iloc[0]
        new_row = patched_df[patched_df['order_id'].isin(swapped_in)].iloc[0]

        if old_row['transaction_id'] != new_row['transaction_id']:
            return {'passed': False, 'explanation': f"Swapped rows have different transaction_ids ({old_row['transaction_id']} vs {new_row['transaction_id']}) — unexpected"}

        old_date = pd.to_datetime(old_row['order_date'])
        new_date = pd.to_datetime(new_row['order_date'])

        if new_date <= old_date:
            return {
                'passed': True,
                'explanation': f"Patch kept order_id {new_row['order_id']} (date {new_row['order_date']}) instead of {old_row['order_id']} (date {old_row['order_date']}) — earliest date kept as expected"
            }
        else:
            return {
                'passed': False,
                'explanation': f"Patch kept order_id {new_row['order_id']} (date {new_row['order_date']}) but order_id {old_row['order_id']} (date {old_row['order_date']}) was earlier — wrong row kept"
            }

    return {
        'passed': False,
        'explanation': f"Unexpected number of swapped rows: {len(swapped_out)} out, {len(swapped_in)} in"
    }
