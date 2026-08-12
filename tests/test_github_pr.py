import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
from github_pr import push_and_create_pr
from github import GithubException


@pytest.fixture
def mock_env():
    """Mock the environment variable for GITHUB_TOKEN."""
    with patch.dict(os.environ, {'GITHUB_TOKEN': 'fake_test_token'}):
        yield


@pytest.fixture
def sample_data():
    patch_result = {'explanation': 'Sorted duplicates by date so the oldest is kept.'}
    diagnosis = {
        'root_cause': 'Upstream system occasionally resends the exact same transaction ID.',
        'confidence': 0.9,
        'reasoning': 'Same transaction_id seen on multiple rows'
    }
    evidence = {
        'finding': {'issue': "Duplicate transaction_id 'txn_001'"},
        'total_affected_in_dataset': 2
    }
    finding_type = 'duplicate_transaction_id'
    validation_result = {
        'regression_check': {'passed': True, 'explanation': 'No unrelated rows changed.'},
        'issue_check': {'passed': True, 'explanation': 'Earliest date kept successfully.'}
    }
    
    return patch_result, diagnosis, evidence, finding_type, validation_result


def test_push_and_create_pr_success(mock_env, sample_data):
    patch_result, diagnosis, evidence, finding_type, validation_result = sample_data
    
    with patch('subprocess.run') as mock_subprocess:
        # Mock git remote get-url output
        mock_subprocess.return_value.stdout = 'https://github.com/FakeOwner/Data-Medic.git\n'
        
        with patch('github_pr.Github') as mock_github_class:
            mock_github_instance = MagicMock()
            mock_github_class.return_value = mock_github_instance
            
            mock_repo = MagicMock()
            mock_github_instance.get_repo.return_value = mock_repo
            
            mock_pr = MagicMock()
            mock_pr.html_url = 'https://github.com/FakeOwner/Data-Medic/pull/42'
            mock_repo.create_pull.return_value = mock_pr
            
            # Run the function
            url = push_and_create_pr('test-branch', patch_result, diagnosis, evidence, finding_type, validation_result)
            
            # Assertions
            assert url == 'https://github.com/FakeOwner/Data-Medic/pull/42'
            
            # Ensure push happened
            mock_subprocess.assert_any_call(['git', 'push', '-u', 'origin', 'test-branch'], check=True, capture_output=True)
            
            # Ensure PR was created with right args
            mock_repo.create_pull.assert_called_once()
            kwargs = mock_repo.create_pull.call_args[1]
            
            assert 'Fix: duplicate_transaction_id' in kwargs['title']
            assert 'Sorted duplicates by date' in kwargs['title']
            
            # Check body components
            body = kwargs['body']
            assert "Duplicate transaction_id 'txn_001'" in body
            assert "2" in body  # rows affected
            assert "Upstream system occasionally resends" in body
            assert "0.9" in body  # confidence
            assert "Same transaction_id seen on multiple rows" in body # reasoning
            assert "✅ PASS" in body
            assert "No unrelated rows changed." in body
            assert "Earliest date kept successfully." in body


def test_missing_token_raises_error(sample_data):
    patch_result, diagnosis, evidence, finding_type, validation_result = sample_data
    
    # Ensure environment is strictly empty for GITHUB_TOKEN
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="GITHUB_TOKEN environment variable not set"):
            push_and_create_pr('test-branch', patch_result, diagnosis, evidence, finding_type, validation_result)


def test_auth_failure_raises_permission_error(mock_env, sample_data):
    patch_result, diagnosis, evidence, finding_type, validation_result = sample_data
    
    with patch('subprocess.run') as mock_subprocess:
        mock_subprocess.return_value.stdout = 'https://github.com/FakeOwner/Data-Medic.git\n'
        
        with patch('github_pr.Github') as mock_github_class:
            mock_github_instance = MagicMock()
            mock_github_class.return_value = mock_github_instance
            
            # Mock an authentication failure exception
            mock_github_instance.get_repo.side_effect = GithubException(401, 'Bad credentials')
            
            with pytest.raises(PermissionError, match="GITHUB_TOKEN is invalid or expired"):
                push_and_create_pr('test-branch', patch_result, diagnosis, evidence, finding_type, validation_result)


def test_no_access_failure_raises_permission_error(mock_env, sample_data):
    patch_result, diagnosis, evidence, finding_type, validation_result = sample_data
    
    with patch('subprocess.run') as mock_subprocess:
        mock_subprocess.return_value.stdout = 'git@github.com:FakeOwner/Data-Medic.git\n'
        
        with patch('github_pr.Github') as mock_github_class:
            mock_github_instance = MagicMock()
            mock_github_class.return_value = mock_github_instance
            
            # Mock a 404 Not Found exception (repo doesn't exist or token lacks scope)
            mock_github_instance.get_repo.side_effect = GithubException(404, 'Not Found')
            
            with pytest.raises(PermissionError, match="GITHUB_TOKEN does not have access to repo"):
                push_and_create_pr('test-branch', patch_result, diagnosis, evidence, finding_type, validation_result)
