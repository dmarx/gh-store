# tests/unit/test_store_infiltrator.py

import pytest
from unittest.mock import Mock, patch
import json
from datetime import datetime, timezone
from gh_store.core.store import GitHubStore
from gh_store.core.exceptions import AccessDeniedError

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
    store.access_control._get_owner_info.return_value = {
        'login': 'repo-owner',
        'type': 'User'
    }
    
    # Process updates
    obj = store.process_updates(123)
    
    # Verify only authorized changes were applied
    assert obj.data["status"] == "updated"
    assert obj.data.get("malicious") is None

def test_unauthorized_issue_creator_denied():
    """Test that updates can't be processed for issues created by unauthorized users"""
    with patch('gh_store.core.store.Github'):
        store = GitHubStore(token="fake-token", repo="owner/repo")
        
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
