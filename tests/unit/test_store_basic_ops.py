# tests/unit/test_store_basic_ops.py
"""Basic CRUD operation tests for GitHubStore."""

from datetime import datetime, timezone
import pytest

from gh_store.core.exceptions import ObjectNotFound
from gh_store.core.version import CLIENT_VERSION
from .fixtures.test_data import DEFAULT_TEST_DATA, create_test_object

def test_create_object_with_initial_state(store, github_mock, mock_comment_factory):
    """Test creating an object with initial state."""
    _, _, mock_api = github_mock
    object_id = "test-123"
    test_data = DEFAULT_TEST_DATA.copy()
    
    # Create the object
    obj = store.create(object_id, test_data)
    
    # Verify issue creation
    create_calls = mock_api.issues
    assert len(create_calls) == 1
    created_issue = create_calls[0]
    
    # Verify labels
    label_names = [label.name for label in created_issue.labels]
    assert "stored-object" in label_names
    assert f"UID:{object_id}" in label_names
    
    # Verify initial state comment
    comment_calls = created_issue.create_comment.call_args_list
    assert len(comment_calls) == 1
    initial_state = comment_calls[0][0][0]
    assert "type" in initial_state
    assert initial_state["type"] == "initial_state"
    assert initial_state["_data"] == test_data
    assert "_meta" in initial_state
    assert initial_state["_meta"]["client_version"] == CLIENT_VERSION

def test_get_object(store, mock_issue_factory):
    """Test retrieving an existing object."""
    # Create test object
    test_data = DEFAULT_TEST_DATA.copy()
    mock_issue_factory(
        number=1,
        body=test_data,
        labels=["stored-object", "UID:test-obj"]
    )
    
    # Retrieve the object
    obj = store.get("test-obj")
    
    # Verify object data
    assert obj.data == test_data
    assert obj.meta.object_id == "test-obj"

def test_get_nonexistent_object(store, github_mock):
    """Test that getting a nonexistent object raises ObjectNotFound."""
    _, mock_repo, _ = github_mock
    mock_repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.get("nonexistent")

def test_create_object_ensures_labels_exist(store, github_mock):
    """Test that create_object creates any missing labels."""
    _, _, mock_api = github_mock
    object_id = "test-123"
    test_data = DEFAULT_TEST_DATA.copy()
    uid_label = f"UID:{object_id}"
    
    # Create object
    store.create(object_id, test_data)
    
    # Verify labels were created
    labels = [label.name for label in mock_api.labels]
    assert "stored-object" in labels
    assert uid_label in labels

def test_create_object_with_metadata(store, github_mock, mock_comment_factory):
    """Test creating an object with metadata."""
    object_id = "test-123"
    test_data = {
        "name": "test",
        "value": 42,
        "_meta": {
            "custom": "metadata"
        }
    }
    
    # Create object
    obj = store.create(object_id, test_data)
    
    # Verify metadata preserved
    assert obj.data["_meta"]["custom"] == "metadata"

def test_get_object_with_history(store, mock_issue_factory, mock_comment_factory):
    """Test getting an object with update history."""
    # Create test object with history
    initial_state = DEFAULT_TEST_DATA.copy()
    updates = [
        {"value": 43},
        {"value": 44}
    ]
    
    comments = []
    # Add initial state comment
    comments.append(mock_comment_factory(
        body={
            "type": "initial_state",
            "_data": initial_state,
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-01T00:00:00Z",
                "update_mode": "append"
            }
        }
    ))
    
    # Add update comments
    for i, update in enumerate(updates, start=1):
        comments.append(mock_comment_factory(
            body={
                "_data": update,
                "_meta": {
                    "client_version": CLIENT_VERSION,
                    "timestamp": f"2025-01-0{i+1}T00:00:00Z",
                    "update_mode": "append"
                }
            }
        ))
    
    mock_issue_factory(
        number=1,
        body=initial_state,
        labels=["stored-object", "UID:test-obj"],
        comments=comments
    )
    
    # Get object
    obj = store.get("test-obj")
    
    # Verify final state
    assert obj.data["value"] == 44  # Should have latest value
    assert obj.meta.object_id == "test-obj"

def test_create_duplicate_object(store, mock_issue_factory):
    """Test that creating a duplicate object fails appropriately."""
    # Create initial object
    mock_issue_factory(
        number=1,
        body=DEFAULT_TEST_DATA.copy(),
        labels=["stored-object", "UID:test-obj"]
    )
    
    # Attempt to create duplicate
    with pytest.raises(ValueError, match="Object.*already exists"):
        store.create("test-obj", DEFAULT_TEST_DATA.copy())

def test_get_object_preserves_metadata(store, mock_issue_factory):
    """Test that getting an object preserves any existing metadata."""
    # Create test object with metadata
    test_data = {
        "name": "test",
        "value": 42,
        "_meta": {
            "custom": "metadata",
            "version": "1.0"
        }
    }
    
    mock_issue_factory(
        number=1,
        body=test_data,
        labels=["stored-object", "UID:test-obj"]
    )
    
    # Get object
    obj = store.get("test-obj")
    
    # Verify metadata preserved
    assert obj.data["_meta"]["custom"] == "metadata"
    assert obj.data["_meta"]["version"] == "1.0"

def test_create_object_with_empty_data(store, github_mock):
    """Test creating an object with empty data."""
    object_id = "test-123"
    
    # Create object with empty dict
    obj = store.create(object_id, {})
    
    # Verify minimal structure
    assert obj.data == {}
    assert obj.meta.object_id == object_id

def test_get_object_with_special_chars(store, mock_issue_factory):
    """Test handling objects with special characters in ID."""
    special_id = "test/123:456"
    test_data = DEFAULT_TEST_DATA.copy()
    
    # Create test object
    mock_issue_factory(
        number=1,
        body=test_data,
        labels=["stored-object", f"UID:{special_id}"]
    )
    
    # Get object
    obj = store.get(special_id)
    
    # Verify correct retrieval
    assert obj.meta.object_id == special_id
    assert obj.data == test_data
