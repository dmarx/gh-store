# tests/unit/fixtures/store.py
"""Store-related fixtures for gh-store unit tests."""

from datetime import datetime, timezone
import pytest
from gh_store.core.store import GitHubStore
from gh_store.core.version import CLIENT_VERSION
from gh_store.core.exceptions import ObjectNotFound

@pytest.fixture
def store(mock_github, default_config):
    """Create GitHubStore instance with mocked dependencies."""
    _, mock_repo = mock_github
    store = GitHubStore(token="fake-token", repo="owner/repo")
    store.repo = mock_repo  # Use mock repo
    store.access_control.repo = mock_repo  # Ensure access control uses same mock
    store.config = default_config  # Use the fixture's config
    
    def get_object_id(issue) -> str:
        """Override get_object_id_from_labels for testing."""
        for label in issue.labels:
            if hasattr(label, 'name') and label.name.startswith("UID:"):
                return label.name[4:]  # Strip "UID:" prefix
        raise ObjectNotFound(f"No UID label found for issue {issue.number}")
    
    store.issue_handler.get_object_id_from_labels = get_object_id
    return store

@pytest.fixture
def history_mock_comments(mock_comment):
    """Create series of comments representing object history."""
    comments = []
    
    # Initial state
    comments.append(mock_comment(
        user_login="repo-owner",
        body={
            "type": "initial_state",
            "_data": {"name": "test", "value": 42},
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-01T00:00:00Z",
                "update_mode": "append"
            }
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
                "client_version": CLIENT_VERSION,
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
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-03T00:00:00Z",
                "update_mode": "append"
            }
        },
        comment_id=3,
        created_at=datetime(2025, 1, 3, tzinfo=timezone.utc)
    ))
    
    return comments
