# tests/unit/test_store_infiltrator.py

import pytest
from unittest.mock import Mock, patch
import json
from datetime import datetime, timezone
from gh_store.core.store import GitHubStore
from gh_store.core.exceptions import AccessDeniedError

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
            mock_files.return_value.joinpath.return_value.open.return_value = Mock(
                __enter__=Mock(return_value=Mock(read=Mock(return_value=mock_config))),
                __exit__=Mock()
            )
            
            store = GitHubStore(token="fake-token", repo="owner/repo")
            store.repo = mock_repo
            return store

def test_unauthorized_updates_are_ignored(store):
    """Test that unauthorized updates are ignored during processing"""
    # Setup minimal test data
    initial_data = {"status": "original"}
    authorized_update = {"status": "updated"}
    unauthorized_update = {"status": "hacked"}
    
    # Create a basic issue with owner permissions
    issue = Mock(
        number=123,
        user=Mock(login="repo-owner"),
        body=json.dumps(initial_data),
        get_comments=Mock(return_value=[
            Mock(
                body=json.dumps(unauthorized_update),
                user=Mock(login="infiltrator")
            ),
            Mock(
                body=json.dumps(authorized_update),
                user=Mock(login="repo-owner")
            )
        ])
    )
    
    # Setup minimal repository mocking
    store.repo.get_issue.return_value = issue
    
    # Process updates
    obj = store.process_updates(123)
    
    # Verify only authorized changes were applied
    assert obj.data["status"] == "updated"
    assert obj.data.get("malicious") is None

def test_unauthorized_issue_creator_denied(mock_repo):
    """Test that updates can't be processed for issues created by unauthorized users"""
    with patch('gh_store.core.store.Github') as mock_github:
        mock_github.return_value.get_repo.return_value = mock_repo
        store = GitHubStore(token="fake-token", repo="owner/repo")
        store.repo = mock_repo
        
        # Mock an issue created by unauthorized user
        issue = Mock(
            number=456,
            user=Mock(login="infiltrator")
        )
        store.repo.get_issue.return_value = issue
        
        # Attempt to process updates should be denied
        with pytest.raises(AccessDeniedError):
            store.process_updates(456)

# uh... todo: make sure "infiltrator" comment doesn't block processing of later updates...
