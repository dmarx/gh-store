# tests/unit/test_store_update_ops.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock

from gh_store.core.exceptions import ConcurrentUpdateError, ObjectNotFound

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
    
    store.repo.get_issues.return_value = [mock_issue]
    store.repo.get_issue.return_value = mock_issue
    
    update_data = {"new": "value"}
    store.update("test-obj", update_data)
    
    # Verify comment structure
    mock_issue.create_comment.assert_called_once()
    comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
    
    assert "_data" in comment_data
    assert "_meta" in comment_data
    assert all(key in comment_data["_meta"] for key in ["client_version", "timestamp", "update_mode"])

def test_update_nonexistent_object(store):
    """Test updating an object that doesn't exist"""
    store.repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.update("nonexistent", {"value": 43})

def test_update_closes_issue(store, mock_issue):
    """Test that process_updates closes the issue when complete"""
    issue = mock_issue(
        body={"status": "initial"},
        comments=[]
    )
    store.repo.get_issue.return_value = issue
    
    store.process_updates(123)
    
    issue.edit.assert_called_with(
        body=json.dumps({"status": "initial"}, indent=2),
        state="closed"
    )
