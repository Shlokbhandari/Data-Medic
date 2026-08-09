import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from confidence_gate import should_proceed


def test_above_threshold_returns_proceed():
    diagnosis = {'root_cause': 'duplicate', 'confidence': 0.85, 'reasoning': 'clear match'}
    result = should_proceed(diagnosis)
    assert result['decision'] == 'proceed'


def test_below_threshold_returns_escalate():
    diagnosis = {'root_cause': 'unknown', 'confidence': 0.5, 'reasoning': 'not enough info'}
    result = should_proceed(diagnosis)
    assert result['decision'] == 'escalate'


def test_exactly_at_threshold_returns_proceed():
    diagnosis = {'root_cause': 'likely bug', 'confidence': 0.7, 'reasoning': 'borderline'}
    result = should_proceed(diagnosis)
    assert result['decision'] == 'proceed'


def test_missing_confidence_returns_escalate():
    diagnosis = {'root_cause': 'unknown', 'reasoning': 'no confidence given'}
    result = should_proceed(diagnosis)
    assert result['decision'] == 'escalate'
