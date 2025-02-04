# tests/unit/test_store_list_ops.py
"""List operation tests for GitHubStore."""

from datetime import datetime, timezone, timedelta
import pytest
from typing import Any

from gh_store.core.exceptions import ObjectNotFound
from gh_store.core.version import CLIENT_VERSION
from .fixtures.test_data import DEFAULT_TEST_DATA, create_test_object

def test_list_all_objects(store, mock_issue_factory):
    """Test listing all objects in store."""
    # Create multiple test objects
    objects = [
        ("test-1", {"name": "first", "value": 42}),
        ("test-2", {"name": "second", "value": 43}),
        ("test-3", {"name": "third", "value": 44})
    ]
    
    for obj_id, data in objects:
        mock_issue_factory(
            number=len(objects),
            body=data,
            labels=["stored-object", f"UID:{obj_id}"],
            state="closed"
        )
    
    # List all objects
    result = store.list_all()
    
    # Verify results
    assert len(result) == len(objects)
    for obj_id, data in objects:
        assert obj_id in result
        assert result[obj_id].data == data

def test_list_updated_since(store, mock_issue_factory):
    """Test fetching objects updated since timestamp."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    query_time = base_time + timedelta(days=1)
    
    # Create objects with different update times
    objects = [
        # Updated after query time
        ("test-1", base_time + timedelta(days=2)),
        # Updated after query time
        ("test-2", base_time + timedelta(days=1, hours=12)),
        # Updated before query time (shouldn't be returned)
        ("test-3", base_time)
    ]
    
    for obj_id, update_time in objects:
        mock_issue_factory(
            number=len(objects),
            body=DEFAULT_TEST_DATA.copy(),
            labels=["stored-object", f"UID:{obj_id}"],
            state="closed",
            updated_at=update_time
        )
    
    # Get updates
    updated = store.list_updated_since(query_time)
    
    # Verify only objects updated after query time are returned
    assert len(updated) == 2
    assert "test-1" in updated
    assert "test-2" in updated
    assert "test-3" not in updated

def test_list_updated_since_no_updates(store, mock_issue_factory):
    """Test when no updates exist since timestamp."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    query_time = base_time + timedelta(days=2)
    
    # Create objects all updated before query time
    for i in range(3):
        mock_issue_factory(
            number=i+1,
            body=DEFAULT_TEST_DATA.copy(),
            labels=["stored-object", f"UID:test-{i}"],
            state="closed",
            updated_at=base_time
        )
    
    # Get updates
    updated = store.list_updated_since(query_time)
    
    # Verify no results
    assert len(updated) == 0

def test_list_all_skips_archived(store, mock_issue_factory):
    """Test that archived objects are skipped in listing."""
    # Create mix of archived and active objects
    objects = [
        ("test-1", ["stored-object", "UID:test-1"]),  # Active
        ("test-2", ["stored-object", "UID:test-2", "archived"]),  # Archived
        ("test-3", ["stored-object", "UID:test-3"])  # Active
    ]
    
    for obj_id, labels in objects:
        mock_issue_factory(
            number=len(objects),
            body=DEFAULT_TEST_DATA.copy(),
            labels=labels,
            state="closed"
        )
    
    # List objects
    result = store.list_all()
    
    # Verify only active objects returned
    assert len(result) == 2
    assert "test-1" in result
    assert "test-2" not in result
    assert "test-3" in result

def test_list_all_handles_invalid_labels(store, mock_issue_factory):
    """Test handling of issues with invalid label structure."""
    # Create issues with various label combinations
    test_cases = [
        # Valid labels
        (1, ["stored-object", "UID:test-1"]),
        # Missing UID label
        (2, ["stored-object"]),
        # Missing stored-object label
        (3, ["UID:test-3"]),
        # Extra labels
        (4, ["stored-object", "UID:test-4", "extra-label"])
    ]
    
    for number, labels in test_cases:
        mock_issue_factory(
            number=number,
            body=DEFAULT_TEST_DATA.copy(),
            labels=labels,
            state="closed"
        )
    
    # List objects
    result = store.list_all()
    
    # Verify only valid objects returned
    assert len(result) == 2  # Only issues 1 and 4 have valid label combinations
    assert "test-1" in result
    assert "test-4" in result

def test_list_updated_since_with_processing(store, mock_issue_factory):
    """Test that list_updated_since handles objects being processed."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    query_time = base_time + timedelta(days=1)
    
    # Create mix of open and closed issues
    objects = [
        # Closed issue, updated after query time
        ("test-1", "closed", base_time + timedelta(days=2)),
        # Open issue (being processed), updated after query time
        ("test-2", "open", base_time + timedelta(days=1, hours=12)),
        # Closed issue, updated before query time
        ("test-3", "closed", base_time)
    ]
    
    for obj_id, state, update_time in objects:
        mock_issue_factory(
            number=len(objects),
            body=DEFAULT_TEST_DATA.copy(),
            labels=["stored-object", f"UID:{obj_id}"],
            state=state,
            updated_at=update_time
        )
    
    # Get updates
    updated = store.list_updated_since(query_time)
    
    # Verify results
    assert len(updated) == 2
    assert "test-1" in updated
    assert "test-2" in updated
    assert "test-3" not in updated

def test_list_all_with_comments(store, mock_issue_factory, mock_comment_factory):
    """Test listing objects with comment history."""
    # Create object with update history
    comments = [
        # Initial state
        mock_comment_factory(
            body={
                "type": "initial_state",
                "_data": {"value": 42},
                "_meta": {
                    "client_version": CLIENT_VERSION,
                    "timestamp": "2025-01-01T00:00:00Z",
                    "update_mode": "append"
                }
            }
        ),
        # Update
        mock_comment_factory(
            body={
                "_data": {"value": 43},
                "_meta": {
                    "client_version": CLIENT_VERSION,
                    "timestamp": "2025-01-02T00:00:00Z",
                    "update_mode": "append"
                }
            }
        )
    ]
    
    mock_issue_factory(
        number=1,
        body={"value": 43},  # Final state
        labels=["stored-object", "UID:test-1"],
        state="closed",
        comments=comments
    )
    
    # List objects
    result = store.list_all()
    
    # Verify object state reflects final update
    assert len(result) == 1
    assert result["test-1"].data["value"] == 43

def test_list_all_empty_store(store, github_mock):
    """Test listing when store is empty."""
    _, mock_repo, _ = github_mock
    mock_repo.get_issues.return_value = []
    
    result = store.list_all()
    assert len(result) == 0

def test_list_updated_since_with_invalid_objects(store, mock_issue_factory):
    """Test that list_updated_since properly handles invalid objects."""
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    query_time = base_time + timedelta(days=1)
    
    # Create mix of valid and invalid objects
    objects = [
        # Valid object updated after query time
        (1, ["stored-object", "UID:test-1"], base_time + timedelta(days=2)),
        # Invalid labels but recent update
        (2, ["stored-object"], base_time + timedelta(days=1, hours=12)),
        # Valid object with old update
        (3, ["stored-object", "UID:test-3"], base_time)
    ]
    
    for number, labels, update_time in objects:
        mock_issue_factory(
            number=number,
            body=DEFAULT_TEST_DATA.copy(),
            labels=labels,
            state="closed",
            updated_at=update_time
        )
    
    # Get updates
    updated = store.list_updated_since(query_time)
    
    # Verify only valid, recent objects returned
    assert len(updated) == 1
    assert "test-1" in updated
