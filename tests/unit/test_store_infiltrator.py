# tests/unit/test_store_infiltrator.py

import pytest
from gh_store.core.exceptions import AccessDeniedError
from unittest.mock import Mock


def test_unauthorized_updates_are_ignored(store, mock_issue, mock_comment):
    """Test that unauthorized updates are ignored during processing"""
    # Create test comments
    unauthorized_comment = mock_comment(
        user_login="infiltrator",
        body={"status": "compromised", "hacked":"true"},
        comment_id=1
    )
    authorized_comment = mock_comment(
        user_login="repo-owner",
        body={"status": "updated"},
        comment_id=2
    )
    
    # Create mock labels
    mock_base_label = Mock()
    mock_base_label.name = "stored-object"
    mock_uid_label = Mock()
    mock_uid_label.name = "UID:test-123"
    
    # Create issue with both comments and labels
    issue = mock_issue(
        number=123,
        body={"status": "original"},
        comments=[unauthorized_comment, authorized_comment],
        labels=[mock_base_label, mock_uid_label]
    )
    
    # Setup issue retrieval
    store.repo.get_issue.return_value = issue
    
    # Process updates
    obj = store.process_updates(123)
    
    # Verify only authorized changes were applied
    assert obj.data["status"] == "updated"
    assert obj.data.get("hacked") is None
    
    # Verify reaction handling
    unauthorized_comment.create_reaction.assert_not_called()
    authorized_comment.create_reaction.assert_called_with("+1")

def test_unauthorized_issue_creator_denied(store, mock_issue):
    """Test that updates can't be processed for issues created by unauthorized users"""
    # Create unauthorized issue
    issue = mock_issue(
        number=456,
        user_login="infiltrator"
    )
    store.repo.get_issue.return_value = issue
    
    # Attempt to process updates should be denied
    with pytest.raises(AccessDeniedError):
        store.process_updates(456)
