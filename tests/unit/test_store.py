# tests/test_store.py

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from unittest.mock import Mock, patch

from gh_store.core.store import GitHubStore
from gh_store.core.exceptions import ObjectNotFound


@pytest.fixture
def store():
    """Create a store instance with a mocked GitHub repo"""
    with patch('gh_store.core.store.Github') as mock_github:
        mock_repo = Mock()
        mock_github.return_value.get_repo.return_value = mock_repo
        store = GitHubStore(token="fake-token", repo="owner/repo")
        store.repo = mock_repo  # Attach for test access
        return store

def test_get_object(store):
    """Test retrieving an object"""
    # Setup
    test_data = {"name": "test", "value": 42}
    mock_issue = Mock()
    mock_issue.body = json.dumps(test_data)
    mock_issue.get_comments = Mock(return_value=[])  # Return empty list of comments
    store.repo.get_issues.return_value = [mock_issue]
    
    # Test
    obj = store.get("test-obj")
    
    # Verify
    assert obj.data == test_data
    store.repo.get_issues.assert_called_once()

def test_get_nonexistent_object(store):
    """Test getting an object that doesn't exist"""
    store.repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.get("nonexistent")

def test_process_update(store):
    """Test processing an update"""
    # Setup initial state
    test_data = {"name": "test", "value": 42}
    mock_issue = Mock()
    mock_issue.body = json.dumps(test_data)
    mock_issue.get_comments = Mock(return_value=[])
    mock_issue.number = 123
    
    # Handle different query states
    def get_issues_side_effect(**kwargs):
        if kwargs.get("state") == "open":
            return []  # No issues being processed
        return [mock_issue]
    
    store.repo.get_issues.side_effect = get_issues_side_effect
    store.repo.get_issue.return_value = mock_issue
    
    # Test update by adding a comment
    update_data = {"value": 43}
    store.update("test-obj", update_data)
    
    # Basic verification
    mock_issue.create_comment.assert_called_once()  # Comment created with update data
    comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
    assert comment_data == update_data
    mock_issue.edit.assert_called_with(state="open")  # Issue reopened to trigger processing

def test_create_object_ensures_labels_exist(store):
    """Test that create_object creates any missing labels"""
    # Setup
    object_id = "test-123"
    test_data = {"name": "test", "value": 42}
    uid_label = f"{store.config.store.uid_prefix}{object_id}"  # Get expected label with prefix
    
    # Mock existing labels
    mock_label = Mock()
    mock_label.name = "stored-object"
    store.repo.get_labels.return_value = [mock_label]  # Only base label exists
    
    mock_issue = Mock()
    store.repo.create_issue.return_value = mock_issue
    
    # Test
    store.create(object_id, test_data)
    
    # Verify label creation with UID prefix
    store.repo.create_label.assert_called_once_with(
        name=uid_label,  # Should include prefix
        color="0366d6"
    )
    
    # Verify issue creation with both labels
    store.repo.create_issue.assert_called_once()
    call_kwargs = store.repo.create_issue.call_args[1]
    assert call_kwargs["labels"] == ["stored-object", uid_label]

def test_list_updated_since(store):
    """Test fetching objects updated since timestamp"""
    # Setup
    timestamp = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
    object_id = "test-123"
    uid_label = f"{store.config.store.uid_prefix}{object_id}"
    
    # Create properly configured mock labels
    stored_label = Mock()
    stored_label.name = "stored-object"
    uid_mock_label = Mock()
    uid_mock_label.name = uid_label
    
    mock_issue = Mock()
    mock_issue.labels = [stored_label, uid_mock_label]
    mock_issue.number = 1
    mock_issue.created_at = timestamp - timedelta(minutes=30)
    mock_issue.updated_at = timestamp + timedelta(minutes=30)
    
    store.repo.get_issues.return_value = [mock_issue]
    
    # Mock the object retrieval
    mock_obj = Mock()
    mock_obj.meta.updated_at = timestamp + timedelta(minutes=30)
    
    # Mock the get_object_by_number method
    store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    
    # Test
    updated = store.list_updated_since(timestamp)
    
    # Verify
    store.repo.get_issues.assert_called_once()
    call_kwargs = store.repo.get_issues.call_args[1]
    assert call_kwargs["since"] == timestamp
    assert object_id in updated
    assert len(updated) == 1
    assert updated[object_id] == mock_obj

def test_list_updated_since_no_updates(store):
    """Test when no updates since timestamp"""
    # Setup
    timestamp = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
    object_id = "test-123"
    uid_label = f"{store.config.store.uid_prefix}{object_id}"
    
    # Create properly configured mock labels
    stored_label = Mock()
    stored_label.name = "stored-object"
    uid_mock_label = Mock()
    uid_mock_label.name = uid_label
    
    mock_issue = Mock()
    mock_issue.labels = [stored_label, uid_mock_label]
    mock_issue.number = 1
    mock_issue.created_at = timestamp - timedelta(minutes=30)
    mock_issue.updated_at = timestamp - timedelta(minutes=30)  # Updated before timestamp
    
    store.repo.get_issues.return_value = [mock_issue]
    
    # Mock the object retrieval
    mock_obj = Mock()
    mock_obj.meta.updated_at = timestamp - timedelta(minutes=30)
    
    # Mock the get_object_by_number method
    store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    
    # Test
    updated = store.list_updated_since(timestamp)
    
    # Verify
    assert len(updated) == 0
