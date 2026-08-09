import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from patch import generate_patch


SAMPLE_DIAGNOSIS = {
    'root_cause': 'Duplicate transaction caused by upstream retry',
    'confidence': 0.85,
    'reasoning': 'Two rows share the same transaction_id'
}

SAMPLE_EVIDENCE = {
    'finding': {
        'row': 1,
        'order_id': 1002,
        'column': 'transaction_id',
        'severity': 'high',
        'issue': "Duplicate transaction_id 'txn_89321'"
    },
    'column': 'transaction_id',
    'affected_rows': [
        {'order_id': 1001, 'transaction_id': 'txn_89321'},
        {'order_id': 1002, 'transaction_id': 'txn_89321'},
    ],
    'total_affected_in_dataset': 2,
}

SAMPLE_CODE = "import pandas as pd\ndf = pd.read_csv('data.csv')\n"


def test_parses_valid_json_response():
    fake_response = '{"explanation": "Added dedup logic", "patched_code": "import pandas\\ndf = df.drop_duplicates()", "risk_notes": "Check column name"}'

    with patch('patch.inference', return_value=(fake_response, 'MockBackend')):
        result, backend = generate_patch(SAMPLE_DIAGNOSIS, SAMPLE_EVIDENCE, SAMPLE_CODE)

    assert backend == 'MockBackend'
    assert result['explanation'] == 'Added dedup logic'
    assert 'drop_duplicates' in result['patched_code']
    assert result['risk_notes'] == 'Check column name'


def test_parses_json_wrapped_in_code_fences():
    fake_response = '```json\n{"explanation": "fix", "patched_code": "code", "risk_notes": "none"}\n```'

    with patch('patch.inference', return_value=(fake_response, 'MockBackend')):
        result, backend = generate_patch(SAMPLE_DIAGNOSIS, SAMPLE_EVIDENCE, SAMPLE_CODE)

    assert result['explanation'] == 'fix'
    assert result['patched_code'] == 'code'


def test_handles_invalid_json_without_crashing():
    fake_response = 'This is totally not JSON!'

    with patch('patch.inference', return_value=(fake_response, 'MockBackend')):
        result, backend = generate_patch(SAMPLE_DIAGNOSIS, SAMPLE_EVIDENCE, SAMPLE_CODE)

    assert 'Could not parse' in result['explanation']
    assert result['patched_code'] == SAMPLE_CODE
