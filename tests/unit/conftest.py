# tests/unit/conftest.py

from datetime import datetime, timezone 
import json
import os
import pytest
from unittest.mock import Mock, mock_open, patch

from gh_store.__main__ import CLI
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
    comments = []
    
    def _make_comment(user_login="repo-owner", body=None, comment_id=1, reactions=None):
        comment = Mock()
        comment.user = Mock(login=user_login)
        comment.id = comment_id
        comment.body = json.dumps(body) if body else "{}"
        comment.get_reactions.return_value = reactions or []
        comment.create_reaction = Mock()
        comments.append(comment)
        return comment
    
    yield _make_comment
    
    for comment in comments:
        comment.reset_mock()

@pytest.fixture
def mock_issue():
    """Create a mock issue with configurable attributes"""
    issues = []
    
    def _make_issue(
        number=1, 
        user_login="repo-owner", 
        body=None, 
        comments=None, 
        labels=None,
        created_at=None,
        updated_at=None
    ):
        issue = Mock()
        issue.number = number
        issue.user = Mock(login=user_login)
        issue.body = json.dumps(body) if body else "{}"
        
        # Make get_comments return a list and be iterable
        mock_comments = comments if comments is not None else []
        issue.get_comments = Mock(return_value=mock_comments)
        
        # Set up default labels if none provided
        if labels is None:
            mock_label1 = Mock(name="stored-object")
            mock_label2 = Mock(name="UID:test-123")
            labels = [mock_label1, mock_label2]
        
        # Ensure labels have proper name attribute
        issue.labels = [
            label if isinstance(label, Mock) else Mock(name=label)
            for label in labels
        ]
        
        # Set timestamps
        issue.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
        
        issue.edit = Mock()
        issues.append(issue)
        return issue
    
    yield _make_issue
    
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

mock_store = store


@pytest.fixture
def mock_config_exists():
    """Mock config file existence check"""
    with patch('gh_store.__main__.ensure_config_exists') as mock:
        yield mock

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
def mock_github():
    """Create a mock Github instance with proper configuration"""
    with patch('gh_store.core.store.Github') as mock_gh:
        mock_repo = Mock()
        
        # Mock owner info
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.owner = owner
        
        # Mock default config
        default_config = """
store:
  base_label: "stored-object"
  uid_prefix: "UID:"
  reactions:
    processed: "+1"
    initial_state: "rocket"
  retries:
    max_attempts: 3
    backoff_factor: 2
  rate_limit:
    max_requests_per_hour: 1000
  log:
    level: "INFO"
    format: "{time} | {level} | {message}"
"""
        with patch('importlib.resources.files') as mock_files:
            mock_files.return_value.joinpath.return_value.open.return_value = \
                mock_open(read_data=default_config)()
        
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo

@pytest.fixture
def cli_env_vars():
    """Set up environment variables for CLI"""
    os.environ["GITHUB_TOKEN"] = "test-token"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"
    yield
    del os.environ["GITHUB_TOKEN"]
    del os.environ["GITHUB_REPOSITORY"]

@pytest.fixture
def cli(cli_env_vars, mock_github, mock_config_exists):
    """Create CLI instance with mocked dependencies"""
    mock_gh, mock_repo = mock_github
    return CLI()
