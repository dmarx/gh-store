# tests/unit/conftest.py

import pytest
from unittest.mock import Mock, mock_open, patch
import json

from gh_store.core.store import GitHubStore

@pytest.fixture
def mock_owner():
    """Create a mock repository owner"""
    owner = Mock()
    owner.login = "repo-owner"
    owner.type = "User"
    yield owner

@pytest.fixture
def mock_repo(mock_owner):
    """Create a mock repository with basic functionality"""
    repo = Mock()
    repo.get_owner.return_value = mock_owner
    yield repo

@pytest.fixture
def mock_config():
    """Create a mock store configuration"""
    config = Mock(
        store=Mock(
            base_label="stored-object",
            uid_prefix="UID:",
            reactions=Mock(
                processed="+1",
                initial_state="rocket"
            ),
            retries=Mock(
                max_attempts=3,
                backoff_factor=2
            ),
            rate_limit=Mock(
                max_requests_per_hour=1000
            ),
            log=Mock(
                level="INFO",
                format="{time} | {level} | {message}"
            )
        )
    )
    yield config

@pytest.fixture
def mock_comment():
    """Create a mock comment with configurable attributes"""
    comments = []  # Keep track of created comments for cleanup
    
    def _make_comment(user_login="repo-owner", body=None, comment_id=1, reactions=None):
        comment = Mock()
        comment.user = Mock(login=user_login)
        comment.id = comment_id
        comment.body = json.dumps(body) if body else "{}"
        comment.get_reactions.return_value = reactions or []
        comment.create_reaction = Mock()
        comments.append(comment)  # Track the comment
        return comment
    
    yield _make_comment
    
    # Cleanup
    for comment in comments:
        comment.reset_mock()

@pytest.fixture
def mock_issue(mock_comment):
    """Create a mock issue with configurable attributes"""
    issues = []  # Keep track of created issues for cleanup
    
    def _make_issue(number=1, user_login="repo-owner", body=None, comments=None):
        issue = Mock()
        issue.number = number
        issue.user = Mock(login=user_login)
        issue.body = json.dumps(body) if body else "{}"
        issue.get_comments = Mock(return_value=comments if comments is not None else [])
        issue.edit = Mock()  # For closing the issue
        issues.append(issue)  # Track the issue
        return issue
    
    yield _make_issue
    
    # Cleanup
    for issue in issues:
        issue.reset_mock()
        
@pytest.fixture
def store(mock_repo, mock_config):
    """Create a GitHubStore instance with mocked components"""
    with patch('gh_store.core.store.Github') as mock_github:
        # Setup Github mock to return our mock_repo
        mock_github.return_value.get_repo.return_value = mock_repo
        
        with patch('pathlib.Path.exists', return_value=False), \
             patch('importlib.resources.files'):
            
            from gh_store.core.store import GitHubStore
            store = GitHubStore(token="fake-token", repo="owner/repo")
            
            # Ensure store's repo and access_control use our mock_repo
            store.repo = mock_repo
            store.access_control.repo = mock_repo
            store.config = mock_config
            
            return store
