import sys
import os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from monitor import check_data
from evidence import collect_evidence

BROKEN_CSV = os.path.join(os.path.dirname(__file__), '..', 'data', 'orders_broken.csv')


def load_broken_data():
    return pd.read_csv(BROKEN_CSV)


def get_findings_and_df():
    df = load_broken_data()
    findings = check_data(df)
    return findings, df


def test_duplicate_evidence_returns_both_rows():
    findings, df = get_findings_and_df()
    dup_finding = [f for f in findings if f['column'] == 'transaction_id'][0]
    evidence = collect_evidence(dup_finding, df)
    assert len(evidence['affected_rows']) == 2


def test_missing_price_evidence_has_column_stats():
    findings, df = get_findings_and_df()
    null_finding = [f for f in findings if 'missing' in f['issue'].lower()][0]
    evidence = collect_evidence(null_finding, df)
    assert 'column_stats' in evidence
    for key in ['min', 'max', 'mean', 'median']:
        assert key in evidence['column_stats']


def test_zero_price_evidence_has_column_stats():
    findings, df = get_findings_and_df()
    zero_finding = [f for f in findings if 'exactly 0' in f['issue']][0]
    evidence = collect_evidence(zero_finding, df)
    assert 'column_stats' in evidence
    for key in ['min', 'max', 'mean', 'median']:
        assert key in evidence['column_stats']


def test_zero_price_stats_exclude_flagged_rows():
    """Stats for the zero-price finding should not include the 0 value itself."""
    findings, df = get_findings_and_df()
    zero_finding = [f for f in findings if 'exactly 0' in f['issue']][0]
    evidence = collect_evidence(zero_finding, df)
    assert evidence['column_stats']['min'] > 0
