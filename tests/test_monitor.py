import sys
import os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from monitor import check_data

BROKEN_CSV = os.path.join(os.path.dirname(__file__), '..', 'data', 'orders_broken.csv')


def load_broken_data():
    return pd.read_csv(BROKEN_CSV)


def test_finds_exactly_three_issues():
    df = load_broken_data()
    findings = check_data(df)
    assert len(findings) == 3


def test_duplicate_transaction_id_found_with_high_severity():
    df = load_broken_data()
    findings = check_data(df)
    dup_findings = [f for f in findings if f['column'] == 'transaction_id']
    assert len(dup_findings) == 1
    assert dup_findings[0]['severity'] == 'high'
    assert 'txn_89321' in dup_findings[0]['issue']


def test_missing_price_found_with_high_severity():
    df = load_broken_data()
    findings = check_data(df)
    null_findings = [f for f in findings if 'missing' in f['issue'].lower()]
    assert len(null_findings) == 1
    assert null_findings[0]['severity'] == 'high'
    assert null_findings[0]['column'] == 'price'


def test_zero_price_found_with_medium_severity():
    df = load_broken_data()
    findings = check_data(df)
    zero_findings = [f for f in findings if 'exactly 0' in f['issue']]
    assert len(zero_findings) == 1
    assert zero_findings[0]['severity'] == 'medium'
    assert zero_findings[0]['column'] == 'price'
