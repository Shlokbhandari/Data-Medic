import sys
import os
from unittest.mock import patch, MagicMock
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from retry_controller import generate_and_validate_with_retry


SAMPLE_DIAGNOSIS = {
    'root_cause': 'upstream duplicate',
    'confidence': 0.85,
    'reasoning': 'two rows share same transaction_id'
}

SAMPLE_EVIDENCE = {
    'finding': {
        'row': 1, 'order_id': 1002, 'column': 'transaction_id',
        'severity': 'high', 'issue': "Duplicate transaction_id 'txn_001'"
    },
    'column': 'transaction_id',
    'affected_rows': [{'order_id': 1001}, {'order_id': 1002}],
    'total_affected_in_dataset': 2,
}

GOOD_CODE = "import pandas as pd\nprint('hello')\n"
CURRENT_CODE = "import pandas as pd\nprint('original')\n"

# Shared rows for mock validation results
SHARED_ROWS = [
    {'order_id': 1003, 'customer_email': 'c@ex.com', 'price': 10.0, 'transaction_id': 'txn_003', 'order_date': '2026-08-02'},
    {'order_id': 1004, 'customer_email': 'd@ex.com', 'price': 20.0, 'transaction_id': 'txn_004', 'order_date': '2026-08-03'},
]

def _good_patch():
    return {
        'explanation': 'good fix',
        'patched_code': GOOD_CODE,
        'risk_notes': 'none',
        'syntax_valid': True,
        'syntax_error': None,
    }

def _bad_syntax_patch():
    return {
        'explanation': 'broken',
        'patched_code': 'def foo(:\n',
        'risk_notes': 'none',
        'syntax_valid': False,
        'syntax_error': 'Line 1: expected something',
    }

def _make_sandbox_result(rows, exit_code=0):
    return {
        'exit_code': exit_code,
        'stdout': '', 'stderr': '',
        'output_csv_exists': True,
        'output_df': pd.DataFrame(rows),
    }


def test_succeeds_first_try_no_retry():
    baseline_rows = SHARED_ROWS + [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 29.99, 'transaction_id': 'txn_001', 'order_date': '2026-08-05'},
    ]
    patched_rows = SHARED_ROWS + [
        {'order_id': 1002, 'customer_email': 'b@ex.com', 'price': 45.50, 'transaction_id': 'txn_001', 'order_date': '2026-08-01'},
    ]

    with patch('retry_controller.generate_patch', return_value=(_good_patch(), 'Mock')) as mock_gen, \
         patch('retry_controller.create_sandbox', return_value={'sandbox_path': '/tmp/fake', 'target_file': 'pipeline/run_pipeline.py', 'original_code': '', 'patched_code': ''}), \
         patch('retry_controller.run_in_sandbox', side_effect=[_make_sandbox_result(baseline_rows), _make_sandbox_result(patched_rows)]), \
         patch('retry_controller.cleanup_sandbox'):

        result = generate_and_validate_with_retry(SAMPLE_DIAGNOSIS, SAMPLE_EVIDENCE, CURRENT_CODE, 'duplicate_transaction_id')

    assert result['success'] is True
    assert result['total_attempts'] == 1
    assert mock_gen.call_count == 1


def test_fails_once_then_succeeds():
    baseline_rows = SHARED_ROWS + [
        {'order_id': 1001, 'customer_email': 'a@ex.com', 'price': 29.99, 'transaction_id': 'txn_001', 'order_date': '2026-08-05'},
    ]
    patched_rows = SHARED_ROWS + [
        {'order_id': 1002, 'customer_email': 'b@ex.com', 'price': 45.50, 'transaction_id': 'txn_001', 'order_date': '2026-08-01'},
    ]

    # First call returns bad syntax, second returns good patch
    with patch('retry_controller.generate_patch', side_effect=[
            (_bad_syntax_patch(), 'Mock'),
            (_good_patch(), 'Mock'),
         ]) as mock_gen, \
         patch('retry_controller.create_sandbox', return_value={'sandbox_path': '/tmp/fake', 'target_file': 'pipeline/run_pipeline.py', 'original_code': '', 'patched_code': ''}), \
         patch('retry_controller.run_in_sandbox', side_effect=[_make_sandbox_result(baseline_rows), _make_sandbox_result(patched_rows)]), \
         patch('retry_controller.cleanup_sandbox'):

        result = generate_and_validate_with_retry(SAMPLE_DIAGNOSIS, SAMPLE_EVIDENCE, CURRENT_CODE, 'duplicate_transaction_id')

    assert result['success'] is True
    assert result['total_attempts'] == 2
    assert mock_gen.call_count == 2
    assert result['attempts'][0]['failure_reason'] is not None
    assert 'Syntax error' in result['attempts'][0]['failure_reason']


def test_all_attempts_fail_returns_escalation():
    with patch('retry_controller.generate_patch', return_value=(_bad_syntax_patch(), 'Mock')) as mock_gen:

        result = generate_and_validate_with_retry(
            SAMPLE_DIAGNOSIS, SAMPLE_EVIDENCE, CURRENT_CODE,
            'duplicate_transaction_id', max_attempts=3
        )

    assert result['success'] is False
    assert result['total_attempts'] == 3
    assert mock_gen.call_count == 3
    assert 'escalation_reason' in result
    assert len(result['attempts']) == 3
    for attempt in result['attempts']:
        assert attempt['failure_reason'] is not None


def test_unparseable_diagnosis_escalates_immediately():
    """A diagnosis that failed to parse (confidence=0) must be blocked by the confidence gate immediately."""
    unparseable_diagnosis = {
        'root_cause': 'Could not parse LLM response',
        'confidence': 0,
        'reasoning': 'Raw response: invalid json syntax'
    }

    with patch('retry_controller.generate_patch') as mock_gen:
        result = generate_and_validate_with_retry(
            unparseable_diagnosis, SAMPLE_EVIDENCE, CURRENT_CODE, 'duplicate_transaction_id'
        )

    assert result['success'] is False
    assert result['total_attempts'] == 0
    assert mock_gen.call_count == 0
    assert 'Confidence gate refused to proceed' in result['escalation_reason']
    assert 'below the 0.7 threshold' in result['escalation_reason']


def test_low_confidence_diagnosis_escalates_immediately():
    """A diagnosis with confidence below threshold must not generate patches."""
    low_conf_diagnosis = {
        'root_cause': 'Uncertain possibility',
        'confidence': 0.5,
        'reasoning': 'Not enough evidence'
    }

    with patch('retry_controller.generate_patch') as mock_gen:
        result = generate_and_validate_with_retry(
            low_conf_diagnosis, SAMPLE_EVIDENCE, CURRENT_CODE, 'duplicate_transaction_id'
        )

    assert result['success'] is False
    assert result['total_attempts'] == 0
    assert mock_gen.call_count == 0
    assert 'Confidence gate refused to proceed' in result['escalation_reason']
