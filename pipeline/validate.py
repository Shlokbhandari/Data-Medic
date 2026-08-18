import pandas as pd


def check_no_regression(baseline_result, patched_result, evidence):
    """Checks that the patch didn't break anything unrelated.
    Only rows listed in evidence['affected_rows'] are permitted to differ, disappear, or appear."""

    if baseline_result.get('exit_code') != 0:
        return {'passed': False, 'explanation': f"Baseline pipeline failed (exit code {baseline_result.get('exit_code')})"}
    if patched_result.get('exit_code') != 0:
        return {'passed': False, 'explanation': f"Patched pipeline failed (exit code {patched_result.get('exit_code')}): {patched_result.get('stderr', '')}"}

    if not baseline_result.get('output_csv_exists'):
        return {'passed': False, 'explanation': 'Baseline pipeline did not produce an output CSV'}
    if not patched_result.get('output_csv_exists'):
        return {'passed': False, 'explanation': 'Patched pipeline did not produce an output CSV'}

    baseline_df = baseline_result.get('output_df')
    patched_df = patched_result.get('output_df')

    if baseline_df is None or not isinstance(baseline_df, pd.DataFrame):
        return {'passed': False, 'explanation': 'Baseline pipeline output dataframe is missing or invalid'}
    if patched_df is None or not isinstance(patched_df, pd.DataFrame):
        return {'passed': False, 'explanation': 'Patched pipeline output dataframe is missing or invalid'}

    evidence = evidence or {}
    affected_ids = {row['order_id'] for row in evidence.get('affected_rows', []) if isinstance(row, dict) and 'order_id' in row}

    if 'order_id' not in baseline_df.columns:
        return {'passed': False, 'explanation': "Baseline output is missing the 'order_id' column"}
    if 'order_id' not in patched_df.columns:
        return {'passed': False, 'explanation': "Patched pipeline output (processed_orders.csv) is missing the 'order_id' column"}

    missing_cols = set(baseline_df.columns) - set(patched_df.columns)
    if missing_cols:
        return {'passed': False, 'explanation': f"Patched pipeline output is missing column(s): {', '.join(sorted(missing_cols))}"}

    # Find rows present in both outputs (by order_id) and check they're identical
    shared = pd.merge(baseline_df, patched_df, on='order_id', suffixes=('_baseline', '_patched'))
    diffs = []
    base_cols = [c for c in baseline_df.columns if c != 'order_id']
    for col in base_cols:
        col_base = f'{col}_baseline'
        col_patch = f'{col}_patched'
        if col_base in shared.columns and col_patch in shared.columns:
            mismatches = shared[shared[col_base] != shared[col_patch]]
            for _, row in mismatches.iterrows():
                if row['order_id'] not in affected_ids:
                    diffs.append(f"order_id {row['order_id']}: {col} changed from '{row[col_base]}' to '{row[col_patch]}'")

    if diffs:
        return {'passed': False, 'explanation': f"Unrelated rows changed: {'; '.join(diffs)}"}

    # Check for order_ids that swapped (present in one but not the other)
    baseline_ids = set(baseline_df['order_id'])
    patched_ids = set(patched_df['order_id'])
    
    only_baseline = baseline_ids - patched_ids
    only_patched = patched_ids - baseline_ids
    
    unrelated_swapped_out = only_baseline - affected_ids
    unrelated_swapped_in = only_patched - affected_ids
    
    if unrelated_swapped_out or unrelated_swapped_in:
        msg = []
        if unrelated_swapped_out:
            msg.append(f"Unrelated rows dropped: {unrelated_swapped_out}")
        if unrelated_swapped_in:
            msg.append(f"Unrelated rows added: {unrelated_swapped_in}")
        return {'passed': False, 'explanation': "; ".join(msg)}

    return {
        'passed': True,
        'explanation': (
            f"No regression: {len(shared)} shared rows are identical"
            + (f", {len(only_baseline)} expected row(s) swapped out, {len(only_patched)} expected swapped in" if (only_baseline or only_patched) else "")
        )
    }


def check_issue_addressed(finding_type, baseline_result, patched_result, evidence=None):
    """Checks case-specific expectations from benchmark.md for a given failure type.
    Returns a dict with passed (bool or None), and explanation (str)."""

    if finding_type == 'duplicate_transaction_id':
        return _check_duplicate_fix(baseline_result, patched_result)
    elif finding_type == 'suspicious_zero_price':
        return _check_flagged_fix(patched_result, evidence, expected_reason="suspicious zero price")
    elif finding_type == 'missing_price':
        return _check_flagged_fix(patched_result, evidence, expected_reason="missing price")
    elif finding_type == 'baseline_drift':
        col = evidence.get('column', 'unknown') if evidence else 'unknown'
        return _check_flagged_fix(patched_result, evidence, expected_reason=f"baseline drift: unexpected nulls in {col}")

    return {
        'passed': None,
        'explanation': f"No defined check for '{finding_type}' yet"
    }


def _check_flagged_fix(patched_result, evidence, expected_reason):
    """Verifies the affected rows are removed from processed_orders.csv and written to flagged_orders.csv with the correct flag_reason."""
    
    if not patched_result.get('output_csv_exists'):
        return {'passed': False, 'explanation': 'Cannot validate — output missing'}
        
    patched_df = patched_result.get('output_df')
    if patched_df is None or not isinstance(patched_df, pd.DataFrame):
        return {'passed': False, 'explanation': 'Cannot validate — output DataFrame missing'}

    evidence = evidence or {}
    affected_ids = {row['order_id'] for row in evidence.get('affected_rows', []) if isinstance(row, dict) and 'order_id' in row}

    if 'order_id' not in patched_df.columns:
        return {'passed': False, 'explanation': "Patched pipeline output (processed_orders.csv) is missing the 'order_id' column"}
    
    # 1. Verify rows are removed from main output
    remaining_affected = set(patched_df['order_id']).intersection(affected_ids)
    if remaining_affected:
        return {'passed': False, 'explanation': f"Failed to exclude affected rows from main output: {remaining_affected} still present"}
        
    # 2. Verify flagged_orders.csv exists and contains them
    if not patched_result.get('flagged_csv_exists'):
        return {'passed': False, 'explanation': "data/flagged_orders.csv was not created"}
        
    flagged_df = patched_result.get('flagged_df')
    if flagged_df is None or not isinstance(flagged_df, pd.DataFrame):
        return {'passed': False, 'explanation': "data/flagged_orders.csv could not be loaded as a valid DataFrame"}

    if 'order_id' not in flagged_df.columns:
        return {'passed': False, 'explanation': "data/flagged_orders.csv is missing the 'order_id' column (was it written without headers?)"}
    flagged_ids = set(flagged_df['order_id'])
    
    missing_from_flagged = affected_ids - flagged_ids
    if missing_from_flagged:
        return {'passed': False, 'explanation': f"Rows {missing_from_flagged} were dropped entirely and not preserved in flagged_orders.csv"}
        
    # 3. Verify the flag_reason is correct
    if 'flag_reason' not in flagged_df.columns:
        return {'passed': False, 'explanation': "data/flagged_orders.csv is missing the 'flag_reason' column"}
        
    invalid_reasons = flagged_df[~flagged_df['order_id'].isin(affected_ids)]
    if not invalid_reasons.empty:
        return {'passed': False, 'explanation': f"Rows {invalid_reasons['order_id'].tolist()} were flagged but were not part of the expected affected rows"}
        
    wrong_reason = flagged_df[flagged_df['flag_reason'] != expected_reason]
    if not wrong_reason.empty:
        return {'passed': False, 'explanation': f"Rows were flagged with incorrect reason. Expected '{expected_reason}'"}

    return {
        'passed': True,
        'explanation': f"Affected rows properly excluded from processed_orders.csv and preserved in flagged_orders.csv with reason '{expected_reason}'"
    }


def _check_duplicate_fix(baseline_result, patched_result):
    """For the duplicate-transaction-id case: verifies the patched output
    kept the row with the earliest order_date among the duplicated rows."""

    if not baseline_result.get('output_csv_exists') or not patched_result.get('output_csv_exists'):
        return {'passed': False, 'explanation': 'Cannot validate — one or both outputs missing'}

    baseline_df = baseline_result.get('output_df')
    patched_df = patched_result.get('output_df')

    if baseline_df is None or not isinstance(baseline_df, pd.DataFrame) or patched_df is None or not isinstance(patched_df, pd.DataFrame):
        return {'passed': False, 'explanation': 'Cannot validate — one or both output DataFrames missing'}

    for col in ['order_id', 'transaction_id', 'order_date']:
        if col not in baseline_df.columns:
            return {'passed': False, 'explanation': f"Baseline output is missing the '{col}' column"}
        if col not in patched_df.columns:
            return {'passed': False, 'explanation': f"Patched pipeline output is missing the '{col}' column"}

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
