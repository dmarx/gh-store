# tests/test_store.py

import pytest
from unittest.mock import Mock, patch
import json
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

# tests/unit/test_store.py

def test_create_object_ensures_labels_exist(store):
    """Test that create_object creates any missing labels"""
    # Setup
    object_id = "test-123"
    test_data = {"name": "test", "value": 42}
    
    # Mock existing labels
    mock_label = Mock()
    mock_label.name = "stored-object"
    store.repo.get_labels.return_value = [mock_label]  # Only base label exists
    
    mock_issue = Mock()
    store.repo.create_issue.return_value = mock_issue
    
    # Test
    store.create(object_id, test_data)
    
    # Verify label creation
    store.repo.create_label.assert_called_once_with(
        name=object_id,
        color="0366d6"
    )
    
    # Verify issue creation with both labels
    store.repo.create_issue.assert_called_once()
    call_kwargs = store.repo.create_issue.call_args[1]
    assert call_kwargs["labels"] == ["stored-object", object_id]
