# tests/unit/test_store_basic_ops.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock

from gh_store.core.constants import LabelNames
from gh_store.core.exceptions import ObjectNotFound


def test_create_object_with_initial_state(store, mock_label_factory, mock_comment_factory, mock_issue_factory):
    """Test that creating an object stores the initial state in a comment"""
    object_id = "test-123"
    test_data = {"name": "test", "value": 42}
    issue_number = 456  # Define issue number
    
    # Mock existing labels
    store.repo.get_labels.return_value = [
        mock_label_factory(name=LabelNames.GH_STORE),
        mock_label_factory(name=LabelNames.STORED_OBJECT),
    ]
    
    # Mock issue creation
    # mock_issue = Mock()
    # mock_issue.number = issue_number  # Set issue number
    # mock_comment = Mock()
    # store.repo.create_issue.return_value = mock_issue
    # mock_issue.create_comment.return_value = mock_comment
    
    # # Set up required attributes
    # mock_issue.created_at = datetime.now(timezone.utc)
    # mock_issue.updated_at = datetime.now(timezone.utc)
    # mock_issue.get_comments = Mock(return_value=[])
    mock_issue = mock_issue_factory(number=issue_number)
    
    # Create object
    obj = store.create(object_id, test_data)
    
    # Verify initial state comment
    mock_issue.create_comment.assert_called_once()
    comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
    assert comment_data["type"] == "initial_state"
    assert comment_data["_data"] == test_data
    assert "_meta" in comment_data
    assert "issue_number" in comment_data["_meta"]  # Verify issue_number in metadata
    assert comment_data["_meta"]["issue_number"] == issue_number  # Verify issue_number value
    
    # Verify object metadata
    assert obj.meta.issue_number == issue_number  # Verify issue_number in object metadata

def test_get_object(store):
    """Test retrieving an object"""
    test_data = {"name": "test", "value": 42}
    issue_number = 42  # Define issue number
    
    # Mock labels - should include both stored-object and gh-store
    stored_label = Mock()
    stored_label.name = "stored-object"
    gh_store_label = Mock()
    gh_store_label.name = LabelNames.GH_STORE
    uid_label = Mock()
    uid_label.name = "UID:test-obj"
    
    store.repo.get_labels.return_value = [stored_label, gh_store_label, uid_label]
    
    mock_issue = Mock()
    mock_issue.number = issue_number  # Set issue number
    mock_issue.body = json.dumps(test_data)
    mock_issue.get_comments = Mock(return_value=[])
    mock_issue.created_at = datetime.now(timezone.utc)
    mock_issue.updated_at = datetime.now(timezone.utc)
    mock_issue.labels = [stored_label, gh_store_label, uid_label]
    store.repo.get_issues.return_value = [mock_issue]
    
    obj = store.get("test-obj")
    assert obj.data == test_data
    assert obj.meta.issue_number == issue_number  # Verify issue_number in metadata
    
    # Verify correct query was made (now checking for all three labels)
    store.repo.get_issues.assert_called_with(
        labels=[LabelNames.GH_STORE, "stored-object", "UID:test-obj"],
        state="closed"
    )

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
    issue_number = 789  # Define issue number
    
    # Mock existing labels
    mock_label = Mock()
    mock_label.name = "stored-object"
    store.repo.get_labels.return_value = [mock_label]
    
    mock_issue = Mock()
    mock_issue.number = issue_number  # Set issue number
    mock_issue.created_at = datetime.now(timezone.utc)
    mock_issue.updated_at = datetime.now(timezone.utc)
    mock_issue.get_comments = Mock(return_value=[])
    store.repo.create_issue.return_value = mock_issue
    
    obj = store.create(object_id, test_data)
    
    # Verify issue_number in object metadata
    assert obj.meta.issue_number == issue_number
    
    # Verify label creation - should include gh-store label
    # store.repo.create_label might be called multiple times, so we can't assert_called_once
    # Update assertion to verify the uid_label was created
    create_label_calls = store.repo.create_label.call_args_list
    print(create_label_calls)
    #created_labels = [call_args[0][0] for call_args in create_label_calls]
    created_labels = [call.kwargs['name'] for call in create_label_calls]
    assert uid_label in created_labels
    
    # Verify issue creation with all required labels (now includes gh-store)
    store.repo.create_issue.assert_called_once()
    call_kwargs = store.repo.create_issue.call_args[1]
    assert "gh-store" in call_kwargs["labels"]
    assert "stored-object" in call_kwargs["labels"]
    assert uid_label in call_kwargs["labels"]
