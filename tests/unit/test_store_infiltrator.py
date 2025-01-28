# tests/unit/test_store_infiltrator.py

import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch, mock_open

import pytest
from gh_store.core.store import GitHubStore

@pytest.fixture
def mock_repo():
    repo = Mock()
    # Mock the owner info
    owner = Mock()
    owner.login = "repo-owner"
    owner.type = "User"
    repo.get_owner.return_value = owner
    return repo

@pytest.fixture
def store(mock_repo):
    """Create a store instance with mocked components"""
    with patch('gh_store.core.store.Github') as mock_github:
        mock_github.return_value.get_repo.return_value = mock_repo
        
        # Mock the default config
        mock_config = """
        store:
            base_label: "stored-object"
            uid_prefix: "UID:"
            reactions:
                processed: "+1"
                initial_state: "rocket"
            retries:
                max_attempts: 3
                backoff_factor: 2
            rate_limit:
                max_requests_per_hour: 1000
            log:
                level: "INFO"
                format: "{time} | {level} | {message}"
        """
        with patch('pathlib.Path.exists', return_value=False), \
             patch('importlib.resources.files') as mock_files:
            mock_files.return_value.joinpath.return_value.open.return_value = mock_open(read_data=mock_config)()
            
            store = GitHubStore(token="fake-token", repo="owner/repo")
            store.repo = mock_repo
            return store

def test_process_updates_with_infiltrator_comments(store):
    """Test that unauthorized/infiltrating comments don't block valid updates"""
    # Mock the issue setup
    issue = Mock()
    issue.number = 123
    issue.user.login = "repo-owner"  # Issue created by owner
    
    # Ensure both store and access_control use the same mock repo
    mock_repo = Mock()
    mock_repo.get_issue.return_value = issue
    store.repo = mock_repo
    store.access_control.repo = mock_repo
    
    # Mock the repository owner info - ADD THIS
    store.access_control._owner_info = {
        'login': 'repo-owner',
        'type': 'User'
    }
    
    # Create a mix of valid and infiltrator comments
    comments = [
        # Infiltrator comment - valid JSON but unauthorized
        Mock(
            id=1,
            body='{"malicious": "update"}',
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            user=Mock(login="infiltrator"),
            get_reactions=Mock(return_value=[])  # No reactions yet
        ),
        # Infiltrator comment - not even JSON
        Mock(
            id=2,
            body='Just some random comment!',
            created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            user=Mock(login="infiltrator"),
            get_reactions=Mock(return_value=[])
        ),
        # Valid update from owner
        Mock(
            id=3,
            body='{"status": "updated"}',
            created_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
            user=Mock(login="repo-owner"),
            get_reactions=Mock(return_value=[])
        )
    ]
    
    issue.get_comments.return_value = comments
    
    # Mock current state
    current_data = {"status": "original"}
    issue.body = json.dumps(current_data)
    
    # Mock the access control
    store.access_control._find_codeowners_file = Mock(return_value=None)
    
    # Process updates
    updated_obj = store.process_updates(123)
    
    # Verify only the authorized update was applied
    assert updated_obj.data["status"] == "updated"
    
    # Verify infiltrator comments were not marked as processed
    comments[0].create_reaction.assert_not_called()  # First infiltrator comment
    comments[1].create_reaction.assert_not_called()  # Second infiltrator comment
    
    # But valid update was marked as processed
    assert any(call.args[0] == '+1' for call in comments[2].create_reaction.call_args_list)
