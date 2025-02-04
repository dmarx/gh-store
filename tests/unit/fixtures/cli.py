# tests/unit/fixtures/cli.py
"""CLI-specific fixtures for gh-store unit tests."""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
import json
import pytest
from unittest.mock import Mock, patch
from loguru import logger

@pytest.fixture(autouse=True)
def setup_test_logging():
    """Configure logging for tests without using loguru's internal handlers."""
    # Remove any existing handlers
    logger.remove()
    
    # Create a simple format that won't cause recursion
    format_string = "{message}"
    
    # Add a simple handler that writes to stdout
    logger.add(sys.stdout, format=format_string, level="INFO")
    
    yield
    
    # Cleanup
    logger.remove()

@pytest.fixture
def mock_github_api():
    """Create a MockGitHubAPI instance with proper issue creation."""
    class MockGitHubAPI:
        def __init__(self):
            self.labels = []
            self.issues = []
            self._next_issue_number = 1
            self._setup_base_labels()
        
        def _setup_base_labels(self):
            self.create_label("stored-object", "0366d6")
        
        def create_label(self, name: str, color: str = "0366d6") -> Mock:
            label = Mock()
            label.name = name
            label.color = color
            self.labels.append(label)
            return label
        
        def create_issue(
            self,
            title: str | None = None,
            body: dict | str | None = None,
            labels: list[str] | None = None
        ) -> Mock:
            """Create a mock issue with auto-incrementing number."""
            issue = Mock()
            issue.number = self._next_issue_number
            self._next_issue_number += 1
            
            # Set basic attributes
            issue.title = title or f"Issue {issue.number}"
            issue.body = json.dumps(body) if isinstance(body, dict) else (body or "{}")
            
            # Set up labels
            issue_labels = []
            if labels:
                for label_name in labels:
                    label = next(
                        (l for l in self.labels if l.name == label_name),
                        self.create_label(label_name)
                    )
                    issue_labels.append(label)
            issue.labels = issue_labels
            
            # Set up other attributes
            issue.state = "open"
            issue.created_at = datetime.now(timezone.utc)
            issue.updated_at = datetime.now(timezone.utc)
            issue.get_comments = Mock(return_value=[])
            issue.create_comment = Mock()
            issue.edit = Mock()
            
            self.issues.append(issue)
            return issue
    
    return MockGitHubAPI()

@pytest.fixture
def github_mock(mock_github_api):
    """Create GitHub mock with proper repo setup."""
    with patch('gh_store.core.store.Github') as mock_gh:
        # Setup mock repo
        mock_repo = Mock()
        
        # Setup owner
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.owner = owner
        
        # Setup labels
        mock_repo.get_labels = Mock(return_value=mock_github_api.labels)
        mock_repo.create_label = mock_github_api.create_label
        
        # Setup issue management
        mock_repo.create_issue = mock_github_api.create_issue
        mock_repo.get_issues = Mock(return_value=mock_github_api.issues)
        mock_repo.get_issue = Mock(
            side_effect=lambda number: next(
                (i for i in mock_github_api.issues if i.number == number),
                None
            )
        )
        
        # Setup CODEOWNERS
        def mock_codeowners(path):
            if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
                content = Mock()
                content.decoded_content = b"* @repo-owner"
                return content
            raise GithubException(404, "Not found")
        
        mock_repo.get_contents = Mock(side_effect=mock_codeowners)
        
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo, mock_github_api

# Update the store fixture to use the new github_mock
@pytest.fixture
def store(github_mock, default_config):
    """Create GitHubStore instance with proper mocking."""
    _, mock_repo, _ = github_mock
    store = GitHubStore(token="fake-token", repo="owner/repo")
    store.repo = mock_repo
    store.access_control.repo = mock_repo
    store.config = default_config
    return store
