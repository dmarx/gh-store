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
    labels=[
        mock_label_factory(name=LabelNames.GH_STORE),
        mock_label_factory(name=LabelNames.STORED_OBJECT),
    ]
    
    # Mock existing labels
    store.repo.get_labels.return_value = labels

    # .... I think this test might be mocked to the point of being useless.
    # Create a properly configured mock issue
    mock_issue = mock_issue_factory(
        number=issue_number,
        body=json.dumps(test_data),
        labels=labels+[f"{LabelNames.UID_PREFIX}{object_id}"],
    )
    
    # Set up the repo mock to return our issue when create_issue is called
    store.repo.create_issue.return_value = mock_issue
    
    # Make the create_comment method return a properly configured comment
    initial_comment = mock_comment_factory(
        comment_id=1,
        body={
            "type": "initial_state",
            "_data": test_data,
            "_meta": {
                "client_version": "1.2.3",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "update_mode": "append",
                "issue_number": issue_number
            }
        }
    )
    mock_issue.create_comment.return_value = initial_comment
    
    # Execute the method under test
    obj = store.create(object_id, test_data)
    
    # Verify issue creation
    store.repo.create_issue.assert_called_once()
    
    # Verify create_issue was called with the right arguments
    create_issue_args = store.repo.create_issue.call_args[1]
    assert create_issue_args["title"] == f"Stored Object: {object_id}"
    assert json.loads(create_issue_args["body"]) == test_data
    assert LabelNames.GH_STORE in create_issue_args["labels"]
    assert LabelNames.STORED_OBJECT in create_issue_args["labels"]
    assert f"{LabelNames.UID_PREFIX}{object_id}" in create_issue_args["labels"]
    
    # Verify initial state comment was created
    mock_issue.create_comment.assert_called_once()
    
    # Verify object metadata
    assert obj.meta.object_id == object_id
    assert obj.meta.issue_number == issue_number
    assert obj.data == test_data


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

def test_create_object_ensures_labels_exist(store, mock_issue_factory, mock_label_factory):
    pass
