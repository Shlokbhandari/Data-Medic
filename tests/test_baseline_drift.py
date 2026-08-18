import sys
import os
import tempfile
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from monitor import check_data
from evidence import collect_evidence
from validate import check_issue_addressed


CLEAN_CSV = os.path.join(os.path.dirname(__file__), '..', 'data', 'orders.csv')


def _write_temp_csv(rows):
    """Write rows to a temp CSV file and return the path."""
    df = pd.DataFrame(rows)
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    df.to_csv(f.name, index=False)
    return f.name


def _make_result(rows, exit_code=0, flagged_rows=None):
    df = pd.DataFrame(rows)
    result = {
        'exit_code': exit_code,
        'stdout': '',
        'stderr': '',
        'output_csv_exists': True,
        'output_df': df,
        'flagged_csv_exists': flagged_rows is not None,
        'flagged_df': pd.DataFrame(flagged_rows) if flagged_rows else None,
    }
    return result


# --- Monitor tests ---

def test_no_drift_on_clean_data():
    """Running the monitor on the clean baseline itself should produce zero drift findings."""
    df = pd.read_csv(CLEAN_CSV)
    findings = check_data(df, baseline_path=CLEAN_CSV)
    drift_findings = [f for f in findings if 'Baseline drift' in f.get('issue', '')]
    assert len(drift_findings) == 0


def test_drift_detected_single_null_in_email():
    """One null in customer_email (baseline has 0%) triggers a drift finding."""
    df = pd.read_csv(CLEAN_CSV)
    df.loc[3, 'customer_email'] = None

    findings = check_data(df, baseline_path=CLEAN_CSV)
    drift_findings = [f for f in findings if 'Baseline drift' in f.get('issue', '')]

    assert len(drift_findings) == 1
    assert drift_findings[0]['column'] == 'customer_email'
    assert drift_findings[0]['affected_row_indices'] == [3]
    assert drift_findings[0]['severity'] == 'high'


def test_drift_detected_multiple_nulls_in_one_column():
    """Multiple nulls in one column produce ONE finding with ALL affected indices."""
    df = pd.read_csv(CLEAN_CSV)
    df.loc[2, 'customer_email'] = None
    df.loc[7, 'customer_email'] = None
    df.loc[15, 'customer_email'] = None

    findings = check_data(df, baseline_path=CLEAN_CSV)
    drift_findings = [f for f in findings if 'Baseline drift' in f.get('issue', '')]

    assert len(drift_findings) == 1
    f = drift_findings[0]
    assert f['column'] == 'customer_email'
    assert sorted(f['affected_row_indices']) == [2, 7, 15]
    assert '15.0%' in f['issue']


def test_drift_skips_price_column():
    """Nulls in price should NOT trigger a drift finding (price has dedicated checks)."""
    df = pd.read_csv(CLEAN_CSV)
    df.loc[5, 'price'] = None

    findings = check_data(df, baseline_path=CLEAN_CSV)
    drift_findings = [f for f in findings if 'Baseline drift' in f.get('issue', '')]

    assert len(drift_findings) == 0


def test_drift_across_two_columns():
    """Nulls in two different columns produce TWO separate findings."""
    df = pd.read_csv(CLEAN_CSV)
    df.loc[1, 'customer_email'] = None
    df.loc[4, 'order_date'] = None

    findings = check_data(df, baseline_path=CLEAN_CSV)
    drift_findings = [f for f in findings if 'Baseline drift' in f.get('issue', '')]

    assert len(drift_findings) == 2
    drifted_cols = {f['column'] for f in drift_findings}
    assert drifted_cols == {'customer_email', 'order_date'}


def test_drift_does_not_fire_when_baseline_missing():
    """If the baseline file doesn't exist, drift detection silently produces no findings."""
    df = pd.read_csv(CLEAN_CSV)
    df.loc[0, 'customer_email'] = None

    findings = check_data(df, baseline_path='/nonexistent/path.csv')
    drift_findings = [f for f in findings if 'Baseline drift' in f.get('issue', '')]

    assert len(drift_findings) == 0


# --- Evidence tests ---

def test_evidence_captures_all_affected_rows_from_indices():
    """Evidence for a multi-row drift finding must include ALL rows, not just the first."""
    df = pd.read_csv(CLEAN_CSV)
    df.loc[2, 'customer_email'] = None
    df.loc[7, 'customer_email'] = None
    df.loc[15, 'customer_email'] = None

    findings = check_data(df, baseline_path=CLEAN_CSV)
    drift_finding = [f for f in findings if 'Baseline drift' in f.get('issue', '')][0]

    evidence = collect_evidence(drift_finding, df)
    assert len(evidence['affected_rows']) == 3
    assert evidence['total_affected_in_dataset'] == 3

    affected_order_ids = {r['order_id'] for r in evidence['affected_rows']}
    expected_ids = {df.loc[2, 'order_id'], df.loc[7, 'order_id'], df.loc[15, 'order_id']}
    assert affected_order_ids == expected_ids


# --- Validation tests ---

def test_validation_passes_when_all_drifted_rows_flagged():
    """_check_flagged_fix passes when all drifted rows are in flagged_orders.csv with correct reason."""
    clean_rows = [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 10.0, 'transaction_id': 'txn_001', 'order_date': '2026-08-01'},
        {'order_id': 1002, 'customer_email': 'b@ex.com', 'price': 20.0, 'transaction_id': 'txn_002', 'order_date': '2026-08-02'},
    ]
    flagged_rows = [
        {'order_id': 1003, 'customer_email': None, 'price': 30.0, 'transaction_id': 'txn_003', 'order_date': '2026-08-03', 'flag_reason': 'baseline drift: unexpected nulls in customer_email'},
        {'order_id': 1004, 'customer_email': None, 'price': 40.0, 'transaction_id': 'txn_004', 'order_date': '2026-08-04', 'flag_reason': 'baseline drift: unexpected nulls in customer_email'},
    ]

    patched = _make_result(clean_rows, flagged_rows=flagged_rows)
    evidence = {
        'column': 'customer_email',
        'affected_rows': [{'order_id': 1003}, {'order_id': 1004}],
    }

    result = check_issue_addressed('baseline_drift', patched, patched, evidence)
    assert result['passed'] is True


def test_validation_fails_when_one_drifted_row_missing_from_flagged():
    """If one of the affected rows is not in flagged_orders.csv, validation fails."""
    clean_rows = [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 10.0, 'transaction_id': 'txn_001', 'order_date': '2026-08-01'},
    ]
    flagged_rows = [
        {'order_id': 1003, 'customer_email': None, 'price': 30.0, 'transaction_id': 'txn_003', 'order_date': '2026-08-03', 'flag_reason': 'baseline drift: unexpected nulls in customer_email'},
    ]

    patched = _make_result(clean_rows, flagged_rows=flagged_rows)
    evidence = {
        'column': 'customer_email',
        'affected_rows': [{'order_id': 1003}, {'order_id': 1004}],
    }

    result = check_issue_addressed('baseline_drift', patched, patched, evidence)
    assert result['passed'] is False
    assert '1004' in str(result['explanation'])
