# tests/unit/fixtures/store.py
"""Store-related fixtures for gh-store unit tests."""

from datetime import datetime, timezone
import pytest
from gh_store.core.store import GitHubStore
from gh_store.core.version import CLIENT_VERSION
from gh_store.core.exceptions import ObjectNotFound

@pytest.fixture
def store(github_mock, default_config):
    """Create GitHubStore instance with mocked dependencies.
    
    Args:
        github_mock: Fixture providing mock GitHub API
        default_config: Fixture providing default configuration
    
    Returns:
        Configured GitHubStore instance with mocked dependencies
    """
    _, mock_repo, _ = github_mock
    store = GitHubStore(token="fake-token", repo="owner/repo")
    store.repo = mock_repo  # Use mock repo
    store.access_control.repo = mock_repo  # Ensure access control uses same mock
    store.config = default_config  # Use the fixture's config
    
    def get_object_id(issue) -> str:
        """Override get_object_id_from_labels for testing."""
        for label in issue.labels:
            if hasattr(label, 'name') and label.name.startswith("UID:"):
                return label.name[4:]  # Strip "UID:" prefix
        raise ValueError(f"No UID label found for issue {issue.number}")
    
    store.issue_handler.get_object_id_from_labels = get_object_id
    return store

@pytest.fixture
def mock_store_object(default_config):
    """Create a mock store object with standard attributes."""
    def _create_object(
        object_id: str,
        data: dict,
        version: int = 1,
        created_at: datetime | None = None,
        updated_at: datetime | None = None
    ):
        obj = Mock()
        obj.meta = Mock()
        obj.meta.object_id = object_id
        obj.meta.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        obj.meta.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
        obj.meta.version = version
        obj.data = data
        return obj
    
    return _create_object

@pytest.fixture
def history_mock_comments(mock_comment_factory):
    """Create series of comments representing object history."""
    # Initial state
    comments = [
        mock_comment_factory(
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
        ),
        # First update
        mock_comment_factory(
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
        ),
        # Second update
        mock_comment_factory(
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
        )
    ]
    
    return comments
