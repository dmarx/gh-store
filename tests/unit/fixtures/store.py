# tests/unit/fixtures/store.py
"""Store-related fixtures for gh-store unit tests."""

from datetime import datetime, timezone
from typing import Sequence
from unittest.mock import Mock, patch

import pytest

from gh_store.core.constants import LabelNames
from gh_store.core.exceptions import ObjectNotFound
from gh_store.core.store import GitHubStore
from gh_store.core.version import CLIENT_VERSION


def setup_mock_auth(store, authorized_users: Sequence[str] | None = None):
    """Set up mocked authorization for testing.
    
    Args:
        store: GitHubStore instance to configure
        authorized_users: List of usernames to authorize (defaults to ['repo-owner'])
    """
    if authorized_users is None:
        authorized_users = ['repo-owner']
    
    # Pre-populate owner info cache
    store.access_control._owner_info = {
        'login': 'repo-owner',
        'type': 'User'
    }
    
    # If we have additional authorized users via CODEOWNERS
    if len(authorized_users) > 1:
        # Mock CODEOWNERS content
        codeowners_content = "* " + " ".join(f"@{user}" for user in authorized_users)
        mock_content = Mock()
        mock_content.decoded_content = codeowners_content.encode()
        store.repo.get_contents = Mock(return_value=mock_content)
        
        # Clear codeowners cache to force reload
        store.access_control._codeowners = None


@pytest.fixture
def store(mock_repo_factory, default_config):
    """Create GitHubStore instance with mocked dependencies."""
    repo = mock_repo_factory(
        name="owner/repo",
        owner_login="repo-owner",
        owner_type="User",
        labels=[LabelNames.GH_STORE.value, LabelNames.STORED_OBJECT.value]
    )
    
    with patch('gh_store.core.store.Github') as mock_gh:
        mock_gh.return_value.get_repo.return_value = repo
        
        store = GitHubStore(token="fake-token", repo="owner/repo")
        store.repo = repo
        store.access_control.repo = repo
        store.config = default_config
        
        # Set up default authorization
        setup_mock_auth(store)
        
        return store

@pytest.fixture
def authorized_store(store):
    """Create store with additional authorized users for testing."""
    def _authorized_store(authorized_users: Sequence[str]):
        setup_mock_auth(store, authorized_users=authorized_users)
        return store
    return _authorized_store


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
                "update_mode": "append",
                "issue_number": 123,
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
                "update_mode": "append",
                "issue_number": 123,
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
                "update_mode": "append",
                "issue_number": 123,
            }
        },
        comment_id=3,
        created_at=datetime(2025, 1, 3, tzinfo=timezone.utc)
    ))
    
    return comments
