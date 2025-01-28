# tests/unit/conftest.py

import pytest
from unittest.mock import Mock, patch
import json

@pytest.fixture
def mock_owner():
    """Create a mock repository owner"""
    owner = Mock()
    owner.login = "repo-owner"
    owner.type = "User"
    return owner

@pytest.fixture
def mock_repo(mock_owner):
    """Create a mock repository with basic functionality"""
    repo = Mock()
    repo.get_owner.return_value = mock_owner
    return repo

@pytest.fixture
def mock_config():
    """Create a mock store configuration"""
    return Mock(
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

@pytest.fixture
def mock_comment(request):
    """Create a mock comment with configurable attributes"""
    def _make_comment(user_login="repo-owner", body=None, comment_id=1, reactions=None):
        comment = Mock()
        comment.user = Mock(login=user_login)
        comment.id = comment_id
        comment.body = json.dumps(body) if body else "{}"
        comment.get_reactions.return_value = reactions or []
        comment.create_reaction = Mock()
        return comment
    return _make_comment

@pytest.fixture
def mock_issue(request, mock_comment):
    """Create a mock issue with configurable attributes"""
    def _make_issue(number=1, user_login="repo-owner", body=None, comments=None):
        issue = Mock()
        issue.number = number
        issue.user = Mock(login=user_login)
        issue.body = json.dumps(body) if body else "{}"
        if comments is not None:
            issue.get_comments.return_value = comments
        else:
            issue.get_comments.return_value = []
        return issue
    return _make_issue

@pytest.fixture
def store(mock_repo, mock_config):
    """Create a GitHubStore instance with mocked components"""
    with patch('gh_store.core.store.Github') as mock_github:
        mock_github.return_value.get_repo.return_value = mock_repo
        
        with patch('pathlib.Path.exists', return_value=False), \
             patch('importlib.resources.files'):
            
            from gh_store.core.store import GitHubStore
            store = GitHubStore(token="fake-token", repo="owner/repo")
            store.repo = mock_repo
            store.config = mock_config
            return store
