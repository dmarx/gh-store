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

def test_create_object(store):
    """Test basic object creation"""
    # Setup
    test_data = {"name": "test", "value": 42}
    mock_issue = Mock()
    store.repo.create_issue.return_value = mock_issue
    
    # Test
    store.create("test-obj", test_data)
    
    # Basic verification
    store.repo.create_issue.assert_called_once()
    call_args = store.repo.create_issue.call_args[1]
    assert "test-obj" in call_args["labels"]
    assert json.loads(call_args["body"]) == test_data

def test_get_object(store):
    """Test retrieving an object"""
    # Setup
    test_data = {"name": "test", "value": 42}
    mock_issue = Mock()
    mock_issue.body = json.dumps(test_data)
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

def test_update_object(store):
    """Test basic update flow"""
    # Setup initial state
    test_data = {"name": "test", "value": 42}
    mock_issue = Mock()
    mock_issue.body = json.dumps(test_data)
    store.repo.get_issues.return_value = [mock_issue]
    
    # Test update
    update_data = {"value": 43}
    store.update("test-obj", update_data)
    
    # Basic verification
    mock_issue.create_comment.assert_called_once()
    assert json.loads(mock_issue.create_comment.call_args[0][0]) == update_data
    mock_issue.edit.assert_called_with(state="open")
