# tests/unit/fixtures/github.py
"""GitHub API mocks for gh-store unit tests."""

from datetime import datetime, timezone
import json
from typing import Any, Callable
import pytest
from unittest.mock import Mock, patch
from github import GithubException

@pytest.fixture
def mock_label_factory() -> Callable[[str], Mock]:
    """Create GitHub-style label objects."""
    def create_label(name: str) -> Mock:
        label = Mock()
        label.name = name
        return label
    return create_label

@pytest.fixture
def mock_comment():
    """Create a mock comment with configurable attributes."""
    def _make_comment(
        user_login: str = "repo-owner",
        body: dict | None = None,
        comment_id: int = 1,
        reactions: list | None = None,
        created_at: datetime | None = None
    ) -> Mock:
        comment = Mock()
        
        # Set up user
        user = Mock()
        user.login = user_login
        comment.user = user
        
        # Handle body serialization
        comment.body = json.dumps(body) if body else "{}"
        comment.id = comment_id
        
        # Set up reactions
        comment.get_reactions = Mock(return_value=reactions or [])
        comment.create_reaction = Mock()
        
        # Set timestamp
        comment.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        
        return comment
    return _make_comment

@pytest.fixture
def mock_issue(mock_label_factory: Callable[[str], Mock]):
    """Create a mock issue with complete GitHub-like structure."""
    def _make_issue(
        number: int = 1,
        user_login: str = "repo-owner",
        body: dict | None = None,
        comments: list | None = None,
        labels: list | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        state: str = "closed"
    ) -> Mock:
        issue = Mock()
        
        # Set basic attributes
        issue.number = number
        issue.state = state
        
        # Set up user
        user = Mock()
        user.login = user_login
        issue.user = user
        
        # Handle body serialization
        issue.body = json.dumps(body) if body not in (None, "") else "{}"
        
        # Set up comments
        issue.get_comments = Mock(return_value=comments or [])
        issue.create_comment = Mock()
        
        # Set up labels
        default_labels = [
            mock_label_factory("stored-object"),
            mock_label_factory("UID:test-123")
        ]
        if labels is not None:
            issue.labels = [
                label if isinstance(label, Mock) else mock_label_factory(label)
                for label in (labels if isinstance(labels, (list, tuple)) else [labels])
            ]
        else:
            issue.labels = default_labels
            
        # Set timestamps
        issue.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
        
        issue.edit = Mock()
        return issue
    return _make_issue

@pytest.fixture
def mock_github():
    """Create a mock Github instance with proper repository structure."""
    with patch('gh_store.core.store.Github') as mock_gh:
        # Setup mock repo
        mock_repo = Mock()
        
        # Setup owner
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.owner = owner
        
        # Setup labels
        mock_labels = [Mock(name="stored-object")]
        mock_repo.get_labels = Mock(return_value=mock_labels)
        
        def create_label(name: str, color: str = "0366d6") -> Mock:
            new_label = Mock(name=name)
            mock_labels.append(new_label)
            return new_label
        mock_repo.create_label = Mock(side_effect=create_label)
        
        # Mock CODEOWNERS access
        mock_content = Mock()
        mock_content.decoded_content = b"* @repo-owner"
        def get_contents_side_effect(path: str) -> Mock:
            if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
                return mock_content
            raise GithubException(404, "Not found")
        mock_repo.get_contents = Mock(side_effect=get_contents_side_effect)
        
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo
