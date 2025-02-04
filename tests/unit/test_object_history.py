# tests/unit/test_object_history.py

from datetime import datetime, timezone
import json
import pytest
from unittest.mock import Mock

from gh_store.core.exceptions import ObjectNotFound

@pytest.fixture
def history_mock_comments(mock_comment):
    """Create series of comments representing object history"""
    comments = []
    
    # Initial state
    comments.append(mock_comment(
        user_login="repo-owner",
        body={
            "type": "initial_state",
            "data": {"name": "test", "value": 42},
            "timestamp": "2025-01-01T00:00:00Z"
        },
        comment_id=1,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
    ))
    
    # First update
    comments.append(mock_comment(
        user_login="repo-owner",
        body={
            "_data": {"value": 43},
            "_meta": {
                "client_version": "0.5.1",
                "timestamp": "2025-01-02T00:00:00Z",
                "update_mode": "append"
            }
        },
        comment_id=2,
        created_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
    ))
    
    # Second update
    comments.append(mock_comment(
        user_login="repo-owner",
        body={
            "_data": {"value": 44},
            "_meta": {
                "client_version": "0.5.1",
                "timestamp": "2025-01-03T00:00:00Z",
                "update_mode": "append"
            }
        },
        comment_id=3,
        created_at=datetime(2025, 1, 3, tzinfo=timezone.utc)
    ))
    
    return comments

def test_get_object_history_initial_state(store, mock_issue, history_mock_comments):
    """Test that initial state is correctly extracted from history"""
    issue = mock_issue(
        number=1,
        comments=history_mock_comments
    )
    store.repo.get_issues.return_value = [issue]
    
    history = store.issue_handler.get_object_history("test-123")
    
    initial_state = history[0]
    assert initial_state["type"] == "initial_state"
    assert initial_state["data"] == {"name": "test", "value": 42}
    assert initial_state["comment_id"] == 1

def test_get_object_history_updates_sequence(store, mock_issue, history_mock_comments):
    """Test that updates are returned in correct chronological order"""
    issue = mock_issue(
        number=1,
        comments=history_mock_comments
    )
    store.repo.get_issues.return_value = [issue]
    
    history = store.issue_handler.get_object_history("test-123")
    
    # Verify updates sequence
    assert len(history) == 3
    assert [entry["data"].get("value") for entry in history if "value" in entry["data"]] == [42, 43, 44]
    assert [entry["comment_id"] for entry in history] == [1, 2, 3]

def test_get_object_history_metadata_handling(store, mock_issue, history_mock_comments):
    """Test that metadata is correctly preserved in history"""
    issue = mock_issue(
        number=1,
        comments=history_mock_comments
    )
    store.repo.get_issues.return_value = [issue]
    
    history = store.issue_handler.get_object_history("test-123")
    
    # Check metadata for updates
    update = history[1]
    assert "metadata" in update
    assert update["metadata"]["client_version"] == "0.5.1"
    assert update["metadata"]["update_mode"] == "append"

def test_get_object_history_legacy_format(store, mock_issue, mock_comment):
    """Test handling of legacy format comments in history"""
    legacy_comment = mock_comment(
        user_login="repo-owner",
        body={"value": 43},  # Legacy format without metadata
        comment_id=1,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    
    issue = mock_issue(
        number=1,
        comments=[legacy_comment]
    )
    store.repo.get_issues.return_value = [issue]
    
    history = store.issue_handler.get_object_history("test-123")
    
    assert len(history) == 1
    assert history[0]["type"] == "update"
    assert history[0]["data"] == {"value": 43}
    assert history[0]["metadata"]["client_version"] == "legacy"

def test_comment_history_json_handling(store, mock_issue, mock_comment):
    """Test processing of valid JSON comments in history"""
    comments = [
        # First comment
        mock_comment(
            user_login="repo-owner",
            body={"value": 42},
            comment_id=1
        ),
        # Second comment
        mock_comment(
            user_login="repo-owner",
            body={"value": 43},
            comment_id=2
        ),
        # Third comment
        mock_comment(
            user_login="repo-owner",
            body={"value": 44},
            comment_id=3
        )
    ]
    
    issue = mock_issue(
        number=1,
        comments=comments
    )
    store.repo.get_issues.return_value = [issue]
    
    history = store.issue_handler.get_object_history("test-123")
    
    # Verify all valid comments are processed
    assert len(history) == 3
    assert [entry["data"]["value"] for entry in history] == [42, 43, 44]
    assert [entry["comment_id"] for entry in history] == [1, 2, 3]

def test_get_object_history_nonexistent(store):
    """Test retrieving history for nonexistent object"""
    store.repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.issue_handler.get_object_history("nonexistent")
