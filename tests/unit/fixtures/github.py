# tests/unit/fixtures/github.py
"""GitHub API mocks for gh-store unit tests."""

from datetime import datetime, timezone
from typing import Any
import pytest
from unittest.mock import Mock, patch
from github import GithubException

from .common import (
    create_base_mock,
    create_github_issue,
    create_github_comment,
    create_update_payload
)
from .test_data import SAMPLE_CONFIGS

class MockGitHubAPI:
    """Helper class to manage GitHub API mocking."""
    
    def __init__(self, owner_login: str = "repo-owner", owner_type: str = "User"):
        self.owner_login = owner_login
        self.owner_type = owner_type
        self.labels: list[Mock] = []
        self.issues: list[Mock] = []
        self._setup_base_labels()
    
    def _setup_base_labels(self) -> None:
        """Initialize default labels."""
        self.create_label("stored-object", "0366d6")
    
    def create_label(self, name: str, color: str = "0366d6") -> Mock:
        """Create a mock label with standard attributes."""
        label = create_base_mock(
            id=f"label_{name}",
            name=name,
            color=color
        )
        self.labels.append(label)
        return label
    
    def get_label(self, name: str) -> Mock | None:
        """Get a label by name."""
        return next((l for l in self.labels if l.name == name), None)
    
    def create_issue(
        self,
        number: int,
        title: str,
        body: dict[str, Any] | str,
        labels: list[str] | None = None
    ) -> Mock:
        """Create a mock issue with standard structure."""
        issue = create_github_issue(
            number=number,
            user_login=self.owner_login,
            body=body,
            labels=labels or ["stored-object"],
            state="open"
        )
        self.issues.append(issue)
        return issue
    
    def setup_mock_repo(self) -> Mock:
        """Create a mock repository with standard configuration."""
        repo = create_base_mock(id="mock_repo")
        
        # Set up owner
        owner = create_base_mock(
            id="owner",
            login=self.owner_login,
            type=self.owner_type
        )
        repo.owner = owner
        
        # Set up label management
        repo.get_labels = Mock(return_value=self.labels)
        repo.create_label = Mock(side_effect=self.create_label)
        
        # Set up issue management
        repo.get_issues = Mock(return_value=self.issues)
        repo.create_issue = Mock(side_effect=self.create_issue)
        repo.get_issue = Mock(side_effect=lambda number: next(
            (i for i in self.issues if i.number == number),
            None
        ))
        
        # Set up CODEOWNERS handling
        repo.get_contents = Mock(side_effect=self._mock_codeowners_handler)
        
        return repo
    
    def _mock_codeowners_handler(self, path: str) -> Mock:
        """Handle CODEOWNERS file requests."""
        if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
            content = create_base_mock(
                id="codeowners",
                decoded_content=f"* @{self.owner_login}".encode()
            )
            return content
        raise GithubException(404, "Not found")

@pytest.fixture
def github_mock():
    """Create a standard GitHub API mock."""
    mock_api = MockGitHubAPI()
    
    with patch('gh_store.core.store.Github') as mock_gh:
        mock_repo = mock_api.setup_mock_repo()
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo, mock_api

@pytest.fixture
def org_github_mock():
    """Create a GitHub API mock for organization repositories."""
    mock_api = MockGitHubAPI(
        owner_login="test-org",
        owner_type="Organization"
    )
    
    with patch('gh_store.core.store.Github') as mock_gh:
        mock_repo = mock_api.setup_mock_repo()
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo, mock_api

@pytest.fixture
def mock_issue_factory(github_mock):
    """Create a factory for mock issues with proper GitHub structure."""
    _, _, mock_api = github_mock
    
    def create_test_issue(
        number: int,
        body: dict[str, Any] | str | None = None,
        labels: list[str] | None = None,
        state: str = "closed",
        **kwargs
    ) -> Mock:
        """Create a test issue with standard configuration."""
        issue = create_github_issue(
            number=number,
            user_login=mock_api.owner_login,
            body=body,
            labels=labels or ["stored-object"],
            state=state,
            **kwargs
        )
        mock_api.issues.append(issue)
        return issue
    
    return create_test_issue

@pytest.fixture
def mock_comment_factory():
    """Create a factory for mock comments with proper GitHub structure."""
    def create_test_comment(
        body: dict[str, Any] | str,
        user_login: str = "repo-owner",
        comment_id: int | None = None,
        reactions: list[str] | None = None,
        **kwargs
    ) -> Mock:
        """Create a test comment with standard configuration."""
        return create_github_comment(
            user_login=user_login,
            body=body,
            comment_id=comment_id or len(kwargs.get("comments", [])) + 1,
            reactions=reactions,
            **kwargs
        )
    
    return create_test_comment

# Example usage in tests:
"""
def test_process_update(github_mock, mock_issue_factory, mock_comment_factory):
    _, mock_repo, _ = github_mock
    
    # Create test issue with comments
    issue = mock_issue_factory(
        number=123,
        body={"initial": "state"},
        comments=[
            mock_comment_factory(
                body=create_update_payload({"value": 42}),
                user_login="repo-owner"
            )
        ]
    )
    
    # Test update processing
    ...
"""
