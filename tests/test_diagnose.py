import sys
import os
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from diagnose import diagnose


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


def test_parses_valid_json_response():
    fake_response = '{"root_cause": "upstream retry", "confidence": 0.85, "reasoning": "two rows share the same ID"}'

    with patch('diagnose.inference', return_value=(fake_response, 'MockBackend')):
        diagnosis, backend = diagnose(SAMPLE_EVIDENCE)

    assert backend == 'MockBackend'
    assert diagnosis['root_cause'] == 'upstream retry'
    assert diagnosis['confidence'] == 0.85
    assert diagnosis['reasoning'] == 'two rows share the same ID'


def test_parses_json_wrapped_in_code_fences():
    fake_response = '```json\n{"root_cause": "retry bug", "confidence": 0.9, "reasoning": "clear duplicate"}\n```'

    with patch('diagnose.inference', return_value=(fake_response, 'MockBackend')):
        diagnosis, backend = diagnose(SAMPLE_EVIDENCE)

    assert diagnosis['root_cause'] == 'retry bug'
    assert diagnosis['confidence'] == 0.9


def test_handles_invalid_json_without_crashing():
    fake_response = 'This is not JSON at all, sorry!'

    with patch('diagnose.inference', return_value=(fake_response, 'MockBackend')):
        diagnosis, backend = diagnose(SAMPLE_EVIDENCE)

    assert diagnosis['confidence'] == 0
    assert 'Could not parse' in diagnosis['root_cause']


@pytest.mark.skip(reason="Live API test — run manually with: pytest tests/test_diagnose.py -k live -s --no-header -rs")
def test_live_api_call():
    """Calls the real Groq/Ollama API to confirm the connection works.
    Skipped by default since it's slow and needs an API key."""
    diagnosis, backend = diagnose(SAMPLE_EVIDENCE)
    assert backend in ('Groq', 'Ollama')
    assert 'root_cause' in diagnosis
    assert 'confidence' in diagnosis
    assert 'reasoning' in diagnosis
