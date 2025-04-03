# tests/unit/fixtures/github.py
"""GitHub API mocks for gh-store unit tests."""

from datetime import datetime, timezone
import json
from typing import Any, Callable, Literal, TypedDict
import pytest
from unittest.mock import Mock, patch
from github import GithubException

from gh_store.core.constants import LabelNames

@pytest.fixture
def mock_label_factory():
    """
    Create GitHub-style label objects.
    
    Example:
        label = mock_label_factory("enhancement")
        label = mock_label_factory("bug", "fc2929")
        label = mock_label_factory("bug", "fc2929", "Bug description")
    """
    def create_label(name: str, color: str = "0366d6", description: str = None) -> Mock:
        """
        Create a mock label with GitHub-like structure.
        
        Args:
            name: Name of the label
            color: Color hex code without #
            description: Optional description for the label
        """
        label = Mock()
        label.name = name
        label.color = color
        label.description = description
        return label
    
    return create_label

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


mock_comment = mock_comment_factory


@pytest.fixture
def mock_issue_factory(mock_comment_factory, mock_label_factory):
    """
    Create GitHub issue mocks with standard structure.

    Examples:
        # Basic issue
        issue = mock_issue_factory(
            body={"test": "data"}
        )

        # Issue with explicit number
        issue = mock_issue_factory(
            number=123,
            labels=["stored-object", "UID:test-123"]
        )

        # Issue with comments
        issue = mock_issue_factory(
            comments=[
                mock_comment_factory(
                    body={"value": 42},
                    comment_id=1
                )
            ]
        )
    """
    def create_issue(
        number: int | None = None,
        body: dict[str, Any] | str | None = None,
        labels: list[str] | None = None,
        comments: list[Mock] | None = None,
        state: str = "closed",
        user_login: str = "repo-owner",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        **kwargs
    ) -> Mock:
        """
        Create a mock issue with GitHub-like structure.

        Args:
            number: Issue number (defaults to 1 if not provided)
            body: Issue body content (dict will be JSON serialized)
            labels: List of label names to add
            comments: List of mock comments
            state: Issue state (open/closed)
            user_login: GitHub username of issue creator
            created_at: Issue creation timestamp
            updated_at: Issue last update timestamp
            **kwargs: Additional attributes to set
        """
        issue = Mock()
        
        # Set basic attributes
        issue.number = number or 1  # Default to 1 if not provided
        issue.body = json.dumps(body) if isinstance(body, dict) else (body or "{}")
        issue.state = state
        issue.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
        
        # Set up user
        user = Mock()
        user.login = user_login
        issue.user = user
        
        # Set up labels
        issue_labels = []
        issue.labels = issue_labels
        if labels:
            for label_name in labels:
                issue.labels.append(mock_label_factory(label_name))
                #issue.labels.append(label_name)
        
        
        # Set up comments
        mock_comments = list(comments) if comments is not None else []
        issue.get_comments = Mock(return_value=mock_comments)
        issue.create_comment = Mock()

        # Set up proper owner permissions
        repo = Mock()
        owner = Mock()
        owner.login = user_login
        owner.type = "User"
        repo.owner = owner
        issue.repository = repo  # Needed for access control checks
        
        # Set up issue editing
        issue.edit = Mock()
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(issue, key, value)
        
        return issue
    
    return create_issue

# Keep backward compatibility
mock_issue = mock_issue_factory


@pytest.fixture
def mock_repo_factory(mock_label_factory):
    """
    Create GitHub repository mocks with standard structure.
    
    Note: Creates basic repository structure. Labels, issues, and permissions
    should be explicitly set up in tests where they matter.
    """
    def create_repo(
        name: str = "owner/repo",
        owner_login: str = "repo-owner",
        owner_type: str = "User",
        labels: list[str] | None = None,
        issues: list[Mock] | None = None,
        **kwargs
    ) -> Mock:
        """
        Create a mock repository with GitHub-like structure.
        Args:
            name: Repository name in owner/repo format
            owner_login: Repository owner's login
            owner_type: Owner type ("User" or "Organization")
            labels: Initial repository labels
            issues: Initial repository issues
            **kwargs: Additional attributes to set
        """
        repo = Mock()
        
        # Set basic attributes
        repo.full_name = name
        
        # Set up owner - making it more explicit
        owner = Mock(spec=['login', 'type'])  # Specify expected attributes
        owner.login = owner_login
        owner.type = owner_type
        repo.owner = owner
        
        # Set up labels - include gh-store by default unless specified otherwise
        repo_labels = []
        if labels:
            default_labels = [LabelNames.GH_STORE.value, LabelNames.STORED_OBJECT.value] \
                                if LabelNames.GH_STORE.value not in labels and LabelNames.STORED_OBJECT.value not in labels else []
            for name in default_labels + labels:
                repo_labels.append(mock_label_factory(name))
        repo.get_labels = Mock(return_value=repo_labels)
        
        # Set up label creation
        def create_label(name: str, color: str = "0366d6", description: str = None) -> Mock:
            label = mock_label_factory(name, color, description)
            repo_labels.append(label)
            return label
        repo.create_label = Mock(side_effect=create_label)
        
        # Set up issues
        repo_issues = issues or []
        def get_issue(number):
            matching = [i for i in repo_issues if i.number == number]
            if matching:
                return matching[0]
            mock_issue = Mock()
            mock_issue.state = "closed"
            return mock_issue
        repo.get_issue = Mock(side_effect=get_issue)
        repo.get_issues = Mock(return_value=repo_issues)
        
        # Set up CODEOWNERS handling
        def get_contents(path: str) -> Mock:
            if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
                content = Mock()
                content.decoded_content = f"* @{owner_login}".encode()
                return content
            raise GithubException(404, "Not found")
        repo.get_contents = Mock(side_effect=get_contents)
        
        # Add any additional attributes
        for key, value in kwargs.items():
            setattr(repo, key, value)
        
        return repo
    
    return create_repo

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
        mock_labels = [Mock(name=LabelNames.STORED_OBJECT.value), Mock(name=LabelNames.GH_STORE.value)]
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
