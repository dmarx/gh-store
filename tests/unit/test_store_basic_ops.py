# tests/unit/test_store_basic_ops.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock

from gh_store.core.exceptions import ObjectNotFound

def test_create_object_with_initial_state(store):
    """Test that creating an object stores the initial state in a comment"""
    object_id = "test-123"
    test_data = {"name": "test", "value": 42}
    
    # Mock existing labels
    mock_base_label = Mock()
    mock_base_label.name = "stored-object"
    store.repo.get_labels.return_value = [mock_base_label]
    
    # Mock issue creation
    mock_issue = Mock()
    mock_comment = Mock()
    store.repo.create_issue.return_value = mock_issue
    mock_issue.create_comment.return_value = mock_comment
    
    # Set up required attributes
    mock_issue.created_at = datetime.now(timezone.utc)
    mock_issue.updated_at = datetime.now(timezone.utc)
    mock_issue.get_comments = Mock(return_value=[])
    
    # Create object
    obj = store.create(object_id, test_data)
    
    # Verify initial state comment
    mock_issue.create_comment.assert_called_once()
    comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
    assert comment_data["type"] == "initial_state"
    assert comment_data["_data"] == test_data
    assert "_meta" in comment_data

def test_get_object(store):
    """Test retrieving an object"""
    test_data = {"name": "test", "value": 42}
    
    # Mock labels
    stored_label = Mock()
    stored_label.name = "stored-object"
    store.repo.get_labels.return_value = [stored_label]
    
    mock_issue = Mock()
    mock_issue.body = json.dumps(test_data)
    mock_issue.get_comments = Mock(return_value=[])
    mock_issue.created_at = datetime.now(timezone.utc)
    mock_issue.updated_at = datetime.now(timezone.utc)
    store.repo.get_issues.return_value = [mock_issue]
    
    obj = store.get("test-obj")
    assert obj.data == test_data

def test_get_nonexistent_object(store):
    """Test getting an object that doesn't exist"""
    store.repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.get("nonexistent")

def test_create_object_ensures_labels_exist(store):
    """Test that create_object creates any missing labels"""
    object_id = "test-123"
    test_data = {"name": "test", "value": 42}
    uid_label = f"{store.config.store.uid_prefix}{object_id}"
    
    # Mock existing labels
    mock_label = Mock()
    mock_label.name = "stored-object"
    store.repo.get_labels.return_value = [mock_label]
    
    mock_issue = Mock()
    mock_issue.created_at = datetime.now(timezone.utc)
    mock_issue.updated_at = datetime.now(timezone.utc)
    mock_issue.get_comments = Mock(return_value=[])
    store.repo.create_issue.return_value = mock_issue
    
    store.create(object_id, test_data)
    
    # Verify label creation
    store.repo.create_label.assert_called_once_with(
        name=uid_label,
        color="0366d6"
    )
    
    # Verify issue creation with both labels
    store.repo.create_issue.assert_called_once()
    call_kwargs = store.repo.create_issue.call_args[1]
    assert call_kwargs["labels"] == ["stored-object", uid_label]
