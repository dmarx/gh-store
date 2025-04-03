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

# tests/unit/test_store_update_ops.py - Add debugging

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch

from gh_store.core.constants import LabelNames
from gh_store.core.exceptions import ConcurrentUpdateError, ObjectNotFound
from gh_store.core.version import CLIENT_VERSION

def test_concurrent_update_prevention(store, mock_issue_factory, mock_comment_factory):
    """Test that concurrent updates are prevented with debugging"""
    
    # Add debug patch for CommentHandler.get_unprocessed_updates
    original_get_unprocessed = store.comment_handler.get_unprocessed_updates
    
    def debug_get_unprocessed(issue_number):
        print(f"DEBUG: get_unprocessed_updates called with issue_number {issue_number}")
        issue = store.repo.get_issue(issue_number)
        print(f"DEBUG: get_issue returned {type(issue)}")
        comments = issue.get_comments()
        print(f"DEBUG: get_comments returned {type(comments)}")
        
        # Try to iterate and see what happens
        try:
            print(f"DEBUG: Attempting to iterate over comments")
            comment_list = list(comments)  # Force iteration
            print(f"DEBUG: Successfully got {len(comment_list)} comments")
        except Exception as e:
            print(f"DEBUG: Iteration failed with error: {type(e).__name__}: {str(e)}")
        
        # Call the original to see the actual error
        try:
            return original_get_unprocessed(issue_number)
        except Exception as e:
            print(f"DEBUG: Original method failed with: {type(e).__name__}: {str(e)}")
            raise
    
    store.comment_handler.get_unprocessed_updates = debug_get_unprocessed
    
    try:
        # Create comments for our mock issue
        comments = [
            mock_comment_factory(
                body={"value": 42},
                comment_id=i,
                reactions=[]
            ) for i in range(1)
        ]
        
        # Create the mock issue
        mock_issue = mock_issue_factory(
            state="open",
            number=123,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, f"{LabelNames.UID_PREFIX}test-obj"]
        )
        
        # Print debug info about our mock issue
        print(f"DEBUG: Created mock_issue: {mock_issue}")
        print(f"DEBUG: mock_issue.get_comments is {mock_issue.get_comments}")
        
        # Set up the mock return values
        store.repo.get_issue.return_value = mock_issue
        
        # Make sure get_comments returns a list not a Mock
        mock_issue.get_comments.return_value = comments
        
        # Check what get_comments returns now
        print(f"DEBUG: mock_issue.get_comments() returns {mock_issue.get_comments()}")
        
        # Set up get_issues to return our mock issue
        def get_issues_side_effect(**kwargs):
            if kwargs.get("state") == "open":
                return [mock_issue]
            return []
        
        store.repo.get_issues.side_effect = get_issues_side_effect
        
        # Test an update
        print("DEBUG: Testing update...")
        store.update("test-obj", {"value": 43})
        print("DEBUG: Update successful")
        
    finally:
        # Restore original method
        store.comment_handler.get_unprocessed_updates = original_get_unprocessed

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
