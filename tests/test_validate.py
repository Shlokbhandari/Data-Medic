import sys
import os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from validate import check_no_regression, check_issue_addressed


# Shared base rows — rows that shouldn't change between baseline and patched
SHARED_ROWS = [
    {'order_id': 1003, 'customer_email': 'c@ex.com', 'price': 10.0, 'transaction_id': 'txn_003', 'order_date': '2026-08-02'},
    {'order_id': 1004, 'customer_email': 'd@ex.com', 'price': 20.0, 'transaction_id': 'txn_004', 'order_date': '2026-08-03'},
    {'order_id': 1005, 'customer_email': 'e@ex.com', 'price': 30.0, 'transaction_id': 'txn_005', 'order_date': '2026-08-04'},
]


def _make_result(rows, exit_code=0):
    """Helper to build a fake run_in_sandbox result from a list of row dicts."""
    df = pd.DataFrame(rows)
    return {
        'exit_code': exit_code,
        'stdout': '',
        'stderr': '',
        'output_csv_exists': True,
        'output_df': df,
        'flagged_csv_exists': False,
        'flagged_df': None,
    }


# --- Passing case: both checks pass ---

def test_both_checks_pass():
    # Baseline kept order_id 1001 (date Aug 5), patched kept 1002 (date Aug 1 = earlier)
    baseline_rows = SHARED_ROWS + [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 29.99, 'transaction_id': 'txn_001', 'order_date': '2026-08-05'},
    ]
    patched_rows = SHARED_ROWS + [
        {'order_id': 1002, 'customer_email': 'b@ex.com', 'price': 45.50, 'transaction_id': 'txn_001', 'order_date': '2026-08-01'},
    ]

    baseline = _make_result(baseline_rows)
    patched = _make_result(patched_rows)
    
    evidence = {'affected_rows': [{'order_id': 1001}, {'order_id': 1002}]}

    regression = check_no_regression(baseline, patched, evidence)
    assert regression['passed'] is True

    issue = check_issue_addressed('duplicate_transaction_id', baseline, patched, evidence)
    assert issue['passed'] is True


# --- Regression fails when an unrelated row changed ---

def test_regression_fails_on_unrelated_change():
    # Same rows, but an unrelated row (1004) has a changed price
    baseline_rows = SHARED_ROWS + [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 29.99, 'transaction_id': 'txn_001', 'order_date': '2026-08-05'},
    ]
    modified_shared = SHARED_ROWS.copy()
    modified_shared[1] = {**modified_shared[1], 'price': 999.99} # 1004 changed
    patched_rows = modified_shared + [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 29.99, 'transaction_id': 'txn_001', 'order_date': '2026-08-05'},
    ]

    baseline = _make_result(baseline_rows)
    patched = _make_result(patched_rows)
    
    evidence = {'affected_rows': [{'order_id': 1001}, {'order_id': 1002}]}

    regression = check_no_regression(baseline, patched, evidence)
    assert regression['passed'] is False
    assert 'order_id 1004' in regression['explanation']


# --- New Test: Blast radius check fails when unrelated row is dropped or added ---

def test_regression_fails_on_unrelated_dropped_or_added_row():
    # Baseline has 1004, patched drops 1004 and adds 1006. 1004 and 1006 are not in evidence.
    baseline_rows = SHARED_ROWS + [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 29.99, 'transaction_id': 'txn_001', 'order_date': '2026-08-05'},
    ]
    
    # 1004 is removed, 1006 is added
    patched_rows = [r for r in SHARED_ROWS if r['order_id'] != 1004] + [
        {'order_id': 1006, 'customer_email': 'new@ex.com', 'price': 10.0, 'transaction_id': 'txn_006', 'order_date': '2026-08-06'},
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 29.99, 'transaction_id': 'txn_001', 'order_date': '2026-08-05'},
    ]
    
    baseline = _make_result(baseline_rows)
    patched = _make_result(patched_rows)
    
    evidence = {'affected_rows': [{'order_id': 1001}, {'order_id': 1002}]}
    
    regression = check_no_regression(baseline, patched, evidence)
    assert regression['passed'] is False
    assert 'Unrelated rows dropped: {1004}' in regression['explanation']
    assert 'Unrelated rows added: {1006}' in regression['explanation']


# --- Issue addressed fails when wrong row kept ---

def test_issue_addressed_fails_when_wrong_row_kept():
    # Baseline kept the earlier date (1002, Aug 1), patched kept the later date (1001, Aug 5)
    baseline_rows = SHARED_ROWS + [
        {'order_id': 1002, 'customer_email': 'b@ex.com', 'price': 45.50, 'transaction_id': 'txn_001', 'order_date': '2026-08-01'},
    ]
    patched_rows = SHARED_ROWS + [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 29.99, 'transaction_id': 'txn_001', 'order_date': '2026-08-05'},
    ]

    baseline = _make_result(baseline_rows)
    patched = _make_result(patched_rows)
    
    evidence = {'affected_rows': [{'order_id': 1001}, {'order_id': 1002}]}

    issue = check_issue_addressed('duplicate_transaction_id', baseline, patched, evidence)
    assert issue['passed'] is False
    assert 'wrong row kept' in issue['explanation'].lower()


# --- Unknown finding type returns None, not pass or fail ---

def test_unknown_finding_type_returns_none():
    baseline = _make_result(SHARED_ROWS)
    patched = _make_result(SHARED_ROWS)
    evidence = {'affected_rows': []}

    result = check_issue_addressed('some_future_type', baseline, patched, evidence)
    assert result['passed'] is None
    assert 'no defined check' in result['explanation'].lower()


# --- Schema guards: missing columns return structured failures without raising exceptions ---

def test_regression_fails_gracefully_on_missing_column():
    baseline = _make_result(SHARED_ROWS)
    # Patched output is missing the price column
    bad_rows = [{'order_id': r['order_id'], 'customer_email': r['customer_email']} for r in SHARED_ROWS]
    patched = _make_result(bad_rows)
    evidence = {'affected_rows': []}

    regression = check_no_regression(baseline, patched, evidence)
    assert regression['passed'] is False
    assert "missing column" in regression['explanation'].lower()


def test_flagged_fix_fails_gracefully_on_missing_flag_reason_or_order_id():
    patched = _make_result(SHARED_ROWS)
    patched['flagged_csv_exists'] = True
    
    # Flagged DF without order_id column
    patched['flagged_df'] = pd.DataFrame([{'bad_col': 'val'}])
    evidence = {'affected_rows': [{'order_id': 999}]}
    
    res = check_issue_addressed('suspicious_zero_price', patched, patched, evidence)
    assert res['passed'] is False
    assert "missing the 'order_id' column" in res['explanation']

    # Flagged DF without flag_reason column
    patched['flagged_df'] = pd.DataFrame([{'order_id': 999}])
    res = check_issue_addressed('suspicious_zero_price', patched, patched, evidence)
    assert res['passed'] is False
    assert "missing the 'flag_reason' column" in res['explanation']


def test_duplicate_fix_fails_gracefully_on_missing_columns():
    # Patched output is missing transaction_id
    bad_rows = [{'order_id': 1001, 'order_date': '2026-08-01'}]
    baseline = _make_result(SHARED_ROWS)
    patched = _make_result(bad_rows)
    evidence = {'affected_rows': [{'order_id': 1001}]}

    res = check_issue_addressed('duplicate_transaction_id', baseline, patched, evidence)
    assert res['passed'] is False
    assert "missing the 'transaction_id' column" in res['explanation']


def test_flagged_fix_fails_when_flagged_row_not_in_evidence():
    # Setup patched result where the main pipeline properly removed the row,
    # but the evidence says no rows were affected (empty list).
    patched = _make_result(SHARED_ROWS)
    patched['flagged_csv_exists'] = True
    
    # flagged_orders.csv has row 1003 flagged properly...
    patched['flagged_df'] = pd.DataFrame([
        {'order_id': 1003, 'flag_reason': 'suspicious zero price'}
    ])
    
    # ...but evidence says 0 affected rows!
    evidence = {'affected_rows': []}
    
    # This should fail because row 1003 is flagged but not in evidence['affected_rows']
    res = check_issue_addressed('suspicious_zero_price', patched, patched, evidence)
    assert res['passed'] is False
    assert "Rows [1003] were flagged but were not part of the expected affected rows" in res['explanation']
