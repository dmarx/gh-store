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

# In conftest.py

@pytest.fixture
def mock_issue(mock_comment):
    """Create a mock issue with configurable attributes"""
    issues = []  # Keep track of created issues for cleanup
    
    def _make_issue(number=1, user_login="repo-owner", body=None, comments=None, labels=None):
        issue = Mock()
        issue.number = number
        issue.user = Mock(login=user_login)
        issue.body = json.dumps(body) if body else "{}"
        issue.get_comments = Mock(return_value=comments if comments is not None else [])
        issue.edit = Mock()  # For closing the issue
        
        # Set up default labels if none provided
        if labels is None:
            mock_label1 = Mock()
            mock_label1.name = "stored-object"
            mock_label2 = Mock()
            mock_label2.name = "UID:test-123"
            labels = [mock_label1, mock_label2]
        issue.labels = labels
            
        issues.append(issue)  # Track the issue
        return issue
    
    yield _make_issue
    
    # Cleanup
    for issue in issues:
        issue.reset_mock()
        
@pytest.fixture
def store(mock_config):
    """Create a store instance with a mocked GitHub repo"""
    with patch('gh_store.core.store.Github') as mock_github:
        mock_repo = Mock()
        
        # Mock the owner info
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.get_owner.return_value = owner
        
        # Mock CODEOWNERS file
        mock_content = Mock()
        mock_content.decoded_content = b"* @repo-owner"
        def get_contents_side_effect(path):
            if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
                return mock_content
            raise GithubException(404, "Not found")
        mock_repo.get_contents.side_effect = get_contents_side_effect
        
        mock_github.return_value.get_repo.return_value = mock_repo
        
        with patch('pathlib.Path.exists', return_value=False):
            store = GitHubStore(token="fake-token", repo="owner/repo")
            store.repo = mock_repo  # Attach for test access
            store.access_control.repo = mock_repo  # Ensure access control uses same mock
            store.config = mock_config  # Use the fixture's mock config
            return store
