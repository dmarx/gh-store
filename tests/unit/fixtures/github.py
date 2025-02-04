# tests/unit/fixtures/github.py
"""GitHub API mocks for gh-store unit tests."""

from datetime import datetime, timezone
import json
from typing import Any, Callable
import pytest
from unittest.mock import Mock, patch
from github import GithubException


@pytest.fixture
def mock_label_factory():
    """
    Create GitHub-style label objects.
    
    Example:
        label = mock_label_factory("enhancement")
        label = mock_label_factory("bug", "fc2929")
    """
    def create_label(name: str, color: str = "0366d6") -> Mock:
        """
        Create a mock label with GitHub-like structure.
        
        Args:
            name: Name of the label
            color: Color hex code without #
        """
        label = Mock()
        label.name = name
        label.color = color
        return label
    
    return create_label

# tests/unit/fixtures/github.py - Enhanced mock_comment_factory

from datetime import datetime, timezone
from typing import Any, Literal, TypedDict
from unittest.mock import Mock
import pytest
import json

class CommentMetadata(TypedDict, total=False):
    """Metadata for comment creation."""
    client_version: str
    timestamp: str
    update_mode: Literal['append', 'replace']

class CommentBody(TypedDict, total=False):
    """Structure for comment body data."""
    _data: dict[str, Any]
    _meta: CommentMetadata
    type: Literal['initial_state'] | None

@pytest.fixture
def mock_comment_factory():
    """
    Create GitHub comment mocks with standard structure.

    This factory creates mock comment objects that mirror GitHub's API structure,
    with proper typing and validation for reactions and metadata.

    Args in create_comment:
        body: Comment body (dict will be JSON serialized)
        user_login: GitHub username of comment author
        comment_id: Unique comment ID (auto-generated if None)
        reactions: List of reaction types or mock reactions
        created_at: Comment creation timestamp
        **kwargs: Additional attributes to set on the comment

    Examples:
        # Basic comment with data
        comment = mock_comment_factory(
            body={"value": 42},
            user_login="owner"
        )

        # Comment with metadata
        comment = mock_comment_factory(
            body={
                "_data": {"value": 42},
                "_meta": {
                    "client_version": "0.5.1",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "update_mode": "append"
                }
            }
        )

        # Initial state comment
        comment = mock_comment_factory(
            body={
                "type": "initial_state",
                "_data": {"initial": "state"},
                "_meta": {
                    "client_version": "0.5.1",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "update_mode": "append"
                }
            }
        )

        # Comment with reactions
        comment = mock_comment_factory(
            body={"value": 42},
            reactions=["+1", "rocket"]
        )
    """
    def create_comment(
        body: dict[str, Any] | CommentBody,
        user_login: str = "repo-owner",
        comment_id: int | None = None,
        reactions: list[str | Mock] | None = None,
        created_at: datetime | None = None,
        **kwargs
    ) -> Mock:
        """Create a mock comment with GitHub-like structure."""
        # Validate body structure if it's meant to be a CommentBody
        if isinstance(body, dict) and "_meta" in body:
            if "update_mode" in body["_meta"] and body["_meta"]["update_mode"] not in ["append", "replace"]:
                raise ValueError("update_mode must be 'append' or 'replace'")
            if "type" in body and body["type"] not in [None, "initial_state"]:
                raise ValueError("type must be None or 'initial_state'")

        comment = Mock()
        
        # Set basic attributes
        comment.id = comment_id or 1
        comment.body = json.dumps(body)
        comment.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        
        # Set up user
        user = Mock()
        user.login = user_login
        comment.user = user
        
        # Set up reactions with validation
        mock_reactions = []
        if reactions:
            for reaction in reactions:
                if isinstance(reaction, Mock):
                    if not hasattr(reaction, 'content'):
                        raise ValueError("Mock reaction must have 'content' attribute")
                    mock_reactions.append(reaction)
                else:
                    mock_reaction = Mock()
                    mock_reaction.content = str(reaction)
                    mock_reactions.append(mock_reaction)
        
        comment.get_reactions = Mock(return_value=mock_reactions)
        comment.create_reaction = Mock()
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(comment, key, value)
        
        return comment
    
    return create_comment

# Keep backward compatibility
mock_comment = mock_comment_factory

# Keep backward compatibility
mock_comment = mock_comment_factory

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
