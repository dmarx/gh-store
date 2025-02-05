# tests/unit/test_store_update_ops.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock

from gh_store.core.exceptions import ConcurrentUpdateError, ObjectNotFound
from gh_store.core.version import CLIENT_VERSION

def test_process_update(store):
    """Test processing an update"""
    test_data = {"name": "test", "value": 42}
    mock_issue = Mock()
    mock_issue.body = json.dumps(test_data)
    mock_issue.get_comments = Mock(return_value=[])
    mock_issue.number = 123
    
    def get_issues_side_effect(**kwargs):
        if kwargs.get("state") == "open":
            return []  # No issues being processed
        return [mock_issue]
    
    store.repo.get_issues.side_effect = get_issues_side_effect
    store.repo.get_issue.return_value = mock_issue
    
    # Test update
    update_data = {"value": 43}
    store.update("test-obj", update_data)
    
    # Verify update comment
    mock_issue.create_comment.assert_called_once()
    comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
    assert comment_data["_data"] == update_data
    assert "_meta" in comment_data
    assert all(key in comment_data["_meta"] for key in ["client_version", "timestamp", "update_mode"])
    
    # Verify issue reopened
    mock_issue.edit.assert_called_with(state="open")

def test_concurrent_update_prevention(store):
    """Test that concurrent updates are prevented"""
    mock_issue = Mock()
    
    def get_issues_side_effect(**kwargs):
        if kwargs.get("state") == "open":
            return [mock_issue]  # Return open issue to simulate processing
        return []
    
    store.repo.get_issues.side_effect = get_issues_side_effect
    
    with pytest.raises(ConcurrentUpdateError):
        store.update("test-obj", {"value": 43})

def test_update_metadata_structure(store):
    """Test that updates include properly structured metadata"""
    mock_issue = Mock()
    mock_issue.body = json.dumps({"initial": "data"})
    mock_issue.get_comments = Mock(return_value=[])
    mock_issue.number = 123
    mock_issue.user = Mock()
    mock_issue.user.login = "repo-owner"  # Set authorized user
    
    def get_issues_side_effect(**kwargs):
        if kwargs.get("state") == "open":
            return []  # No concurrent processing
        return [mock_issue]
    
    store.repo.get_issues.side_effect = get_issues_side_effect
    store.repo.get_issue.return_value = mock_issue
    
    update_data = {"new": "value"}
    store.update("test-obj", update_data)
    
    # Verify comment structure
    mock_issue.create_comment.assert_called_once()
    comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
    
    assert "_data" in comment_data
    assert "_meta" in comment_data
    assert comment_data["_meta"]["client_version"] == CLIENT_VERSION
    assert comment_data["_meta"]["update_mode"] == "append"
    assert "timestamp" in comment_data["_meta"]

def test_update_closes_issue(store, mock_issue):
    """Test that process_updates closes the issue when complete"""
    test_data = {"initial": "state"}
    
    issue = mock_issue(
        number=123,
        user_login="repo-owner",  # Match authorized user from store fixture
        body=test_data,
        comments=[],  # Empty list for proper iteration
        labels=["stored-object", "UID:test-123"]
    )
    store.repo.get_issue.return_value = issue
    
    store.process_updates(123)
    
    issue.edit.assert_called_with(
        body=json.dumps(test_data, indent=2),
        state="closed"
    )

def test_update_nonexistent_object(store):
    """Test updating an object that doesn't exist"""
    store.repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.update("nonexistent", {"value": 43})

def test_update_closes_issue(store, mock_issue):
    """Test that process_updates closes the issue when complete"""
    test_data = {"initial": "state"}
    
    # Create mock issue with proper authorization
    issue = mock_issue(
        number=123,
        user_login="repo-owner",  # Set authorized user
        body=test_data,  # Pass raw data - mock_issue will handle JSON encoding
        comments=[],  # Explicitly set empty comments
        labels=["stored-object", f"UID:foo"],
    )
    store.repo.get_issue.return_value = issue
    
    store.process_updates(123)
    
    # Verify issue closed with formatted body
    issue.edit.assert_called_with(
        body=json.dumps(test_data, indent=2),
        state="closed"
    )


def test_update_preserves_metadata(store, mock_issue, mock_comment):
    """Test that updates preserve existing metadata"""
    existing_data = {
        "value": 42,
        "_meta": {
            "preserved": "data"
        }
    }
    
    update = mock_comment(
        user_login="repo-owner",  # Match authorized user
        body={
            "_data": {
                "value": 43,
                "_meta": {
                    "new": "metadata"
                }
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-01T00:00:00Z",
                "update_mode": "append"
            }
        }
    )
    
    issue = mock_issue(
        user_login="repo-owner",  # Match authorized user
        body=existing_data,
        comments=[update],  # List for proper iteration
        labels=["stored-object", "UID:test-123"]
    )
    store.repo.get_issue.return_value = issue
    
    obj = store.process_updates(123)
    
    assert obj.data["_meta"]["preserved"] == "data"
    assert obj.data["_meta"]["new"] == "metadata"
