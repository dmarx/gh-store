# tests/unit/test_store_update_ops.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock

from gh_store.core.constants import LabelNames
from gh_store.core.exceptions import ConcurrentUpdateError, ObjectNotFound
from gh_store.core.version import CLIENT_VERSION

def test_process_update(store, mock_issue_factory):
    """Test processing an update"""
    test_data = {"name": "test", "value": 42}
    mock_issue = mock_issue_factory(body=test_data, number=123, labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, f"{LabelNames.UID_PREFIX}:test-obj"])
    
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

# tests/unit/test_store_update_ops.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch

from gh_store.core.constants import LabelNames
from gh_store.core.exceptions import ConcurrentUpdateError, ObjectNotFound
from gh_store.core.version import CLIENT_VERSION

def test_concurrent_update_prevention(store, mock_issue_factory, mock_comment_factory):
    """Test that concurrent updates are prevented"""
    # Create mock comments that will be returned by the get_comments method
    mock_comments_1 = [
        mock_comment_factory(
            body={"value": 42},
            comment_id=1,
            # Make sure these comments don't appear "processed" by not having the processed reaction
            reactions=[]
        )
    ]
    
    mock_comments_2 = [
        mock_comment_factory(
            body={"value": 42},
            comment_id=i,
            reactions=[]
        ) for i in range(1, 3)  # 2 comments
    ]
    
    mock_comments_3 = [
        mock_comment_factory(
            body={"value": 42},
            comment_id=i,
            reactions=[]
        ) for i in range(1, 4)  # 3 comments
    ]
    
    # Create a mock issue that will be returned by get_issue
    mock_issue = mock_issue_factory(
        state="open",
        number=123,
        labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, f"{LabelNames.UID_PREFIX}test-obj"]
    )
    
    # Setup for get_issues to return the open issue
    def get_issues_side_effect(**kwargs):
        if kwargs.get("state") == "open":
            return [mock_issue]
        return []
    
    store.repo.get_issues.side_effect = get_issues_side_effect
    
    # First attempt: 1 comment pending processing
    mock_issue.get_comments.return_value = mock_comments_1
    store.repo.get_issue.return_value = mock_issue
    store.update("test-obj", {"value": 43})
    
    # Second attempt: 2 comments pending processing 
    mock_issue.get_comments.return_value = mock_comments_2
    store.update("test-obj", {"value": 44})
    
    # Third attempt: 3 comments pending processing - should exceed threshold and fail
    mock_issue.get_comments.return_value = mock_comments_3
    with pytest.raises(ConcurrentUpdateError):
        store.update("test-obj", {"value": 45})

def test_update_metadata_structure(store, mock_issue_factory):
    """Test that updates include properly structured metadata"""
    # mock_issue = Mock()
    # mock_issue.body = json.dumps({"initial": "data"})
    # mock_issue.get_comments = Mock(return_value=[])
    # mock_issue.number = 123
    # mock_issue.user = Mock()
    # mock_issue.user.login = "repo-owner"  # Set authorized user
    mock_issue = mock_issue_factory(
        number = 123,
        body={"initial": "data"}, 
        labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, f"{LabelNames.UID_PREFIX}test-obj"]
    )
    
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


def test_update_nonexistent_object(store):
    """Test updating an object that doesn't exist"""
    store.repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.update("nonexistent", {"value": 43})
