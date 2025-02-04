# tests/unit/test_store_update_ops.py
"""Update operation tests for GitHubStore."""

from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import Mock

from gh_store.core.exceptions import ConcurrentUpdateError, ObjectNotFound, AccessDeniedError
from gh_store.core.version import CLIENT_VERSION
from tests.unit.fixtures.test_data import DEFAULT_TEST_DATA, create_test_object

def test_process_single_update(store, mock_issue_factory, mock_comment_factory):
    """Test processing a single update."""
    # Create test issue with initial state
    initial_data = DEFAULT_TEST_DATA.copy()
    update_data = {"value": 43}
    
    issue = mock_issue_factory(
        number=123,
        body=initial_data,
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    
    # Add update comment
    update_comment = mock_comment_factory(
        body={
            "_data": update_data,
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-02T00:00:00Z",
                "update_mode": "append"
            }
        },
        user_login="repo-owner"
    )
    issue.get_comments.return_value = [update_comment]
    
    # Process update
    result = store.process_updates(123)
    
    # Verify result
    assert result.data["value"] == 43
    assert result.meta.object_id == "test-obj"
    
    # Verify issue closed
    issue.edit.assert_called_with(state="closed")

def test_process_multiple_updates(store, mock_issue_factory, mock_comment_factory):
    """Test processing multiple updates in sequence."""
    initial_data = DEFAULT_TEST_DATA.copy()
    updates = [
        {"value": 43},
        {"value": 44},
        {"new_field": "test"}
    ]
    
    # Create test issue
    issue = mock_issue_factory(
        number=123,
        body=initial_data,
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    
    # Create update comments
    comments = []
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    
    for i, update in enumerate(updates):
        comments.append(mock_comment_factory(
            body={
                "_data": update,
                "_meta": {
                    "client_version": CLIENT_VERSION,
                    "timestamp": (base_time + timedelta(days=i+1)).isoformat(),
                    "update_mode": "append"
                }
            },
            user_login="repo-owner",
            created_at=base_time + timedelta(days=i+1)
        ))
    
    issue.get_comments.return_value = comments
    
    # Process updates
    result = store.process_updates(123)
    
    # Verify final state
    assert result.data["value"] == 44
    assert result.data["new_field"] == "test"
    assert result.meta.object_id == "test-obj"

def test_concurrent_update_prevention(store, mock_issue_factory):
    """Test that concurrent updates are prevented."""
    # Create two open issues for same object
    mock_issue_factory(
        number=123,
        body=DEFAULT_TEST_DATA.copy(),
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    mock_issue_factory(
        number=124,
        body=DEFAULT_TEST_DATA.copy(),
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    
    # Attempt update
    with pytest.raises(ConcurrentUpdateError):
        store.update("test-obj", {"value": 43})

def test_update_nonexistent_object(store, github_mock):
    """Test updating a nonexistent object."""
    _, mock_repo, _ = github_mock
    mock_repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.update("nonexistent", {"value": 43})

def test_update_metadata_preservation(store, mock_issue_factory, mock_comment_factory):
    """Test that updates preserve existing metadata."""
    # Create initial state with metadata
    initial_data = {
        "value": 42,
        "_meta": {
            "preserved": "data"
        }
    }
    
    # Create test issue
    issue = mock_issue_factory(
        number=123,
        body=initial_data,
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    
    # Create update with new metadata
    update_comment = mock_comment_factory(
        body={
            "_data": {
                "value": 43,
                "_meta": {
                    "new": "metadata"
                }
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-02T00:00:00Z",
                "update_mode": "append"
            }
        },
        user_login="repo-owner"
    )
    issue.get_comments.return_value = [update_comment]
    
    # Process update
    result = store.process_updates(123)
    
    # Verify metadata
    assert result.data["_meta"]["preserved"] == "data"
    assert result.data["_meta"]["new"] == "metadata"

def test_update_authorization(store, mock_issue_factory, mock_comment_factory):
    """Test that updates from unauthorized users are rejected."""
    # Create test issue
    issue = mock_issue_factory(
        number=123,
        body=DEFAULT_TEST_DATA.copy(),
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    
    # Create unauthorized update
    unauthorized_comment = mock_comment_factory(
        body={
            "_data": {"value": 43},
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-02T00:00:00Z",
                "update_mode": "append"
            }
        },
        user_login="unauthorized-user"
    )
    issue.get_comments.return_value = [unauthorized_comment]
    
    # Process updates - should ignore unauthorized comment
    result = store.process_updates(123)
    assert result.data == DEFAULT_TEST_DATA  # No changes applied

def test_update_reactions(store, mock_issue_factory, mock_comment_factory):
    """Test that processed updates receive reactions."""
    # Create test issue
    issue = mock_issue_factory(
        number=123,
        body=DEFAULT_TEST_DATA.copy(),
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    
    # Create update comment
    update_comment = mock_comment_factory(
        body={
            "_data": {"value": 43},
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-02T00:00:00Z",
                "update_mode": "append"
            }
        },
        user_login="repo-owner"
    )
    issue.get_comments.return_value = [update_comment]
    
    # Process update
    store.process_updates(123)
    
    # Verify reaction added
    update_comment.create_reaction.assert_called_with("+1")

def test_process_updates_invalid_json(store, mock_issue_factory, mock_comment_factory):
    """Test handling of invalid JSON in update comments."""
    # Create test issue
    issue = mock_issue_factory(
        number=123,
        body=DEFAULT_TEST_DATA.copy(),
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    
    # Create invalid update comment
    invalid_comment = mock_comment_factory(
        body="not valid json",
        user_login="repo-owner"
    )
    issue.get_comments.return_value = [invalid_comment]
    
    # Process updates - should ignore invalid comment
    result = store.process_updates(123)
    assert result.data == DEFAULT_TEST_DATA  # No changes applied

def test_update_mode_replace(store, mock_issue_factory, mock_comment_factory):
    """Test update with replace mode."""
    initial_data = {
        "value": 42,
        "preserved": "field"
    }
    
    # Create test issue
    issue = mock_issue_factory(
        number=123,
        body=initial_data,
        labels=["stored-object", "UID:test-obj"],
        state="open"
    )
    
    # Create replace update
    update_comment = mock_comment_factory(
        body={
            "_data": {"value": 43},
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-02T00:00:00Z",
                "update_mode": "replace"
            }
        },
        user_login="repo-owner"
    )
    issue.get_comments.return_value = [update_comment]
    
    # Process update
    result = store.process_updates(123)
    
    # Verify complete replacement
    assert result.data == {"value": 43}
    assert "preserved" not in result.data
