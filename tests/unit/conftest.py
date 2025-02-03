# tests/unit/conftest.py

import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime, timezone
import json
import os
from omegaconf import OmegaConf

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
    """Create a mock issue with GitHub-like structure"""
    def _make_issue(number=1, user_login="repo-owner", body=None, labels=None):
        issue = Mock()
        issue.number = number
        user = Mock()
        user.login = user_login 
        issue.user = user
        issue.body = json.dumps(body) if body else "{}"
        issue.labels = [Mock(name=l) for l in (labels or ["stored-object", "UID:test-123"])]
        issue.get_comments = Mock(return_value=[])
        issue.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        return issue
    return _make_issue
        
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


@pytest.fixture(autouse=True)
def mock_config_path():
    """Mock all file system operations for config"""
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.write_text"), \
         patch("pathlib.Path.read_text", return_value="""
store:
  base_label: "stored-object"
  uid_prefix: "UID:"
  reactions:
    processed: "+1"
    initial_state: "rocket"
"""):
        yield

@pytest.fixture
def mock_config_exists():
    """Mock config file existence check"""
    with patch('gh_store.__main__.ensure_config_exists') as mock:
        yield mock
        
@pytest.fixture(autouse=True)
def mock_config():
    """Mock OmegaConf loading for tests"""
    config = OmegaConf.create({
        "store": {
            "base_label": "stored-object",
            "uid_prefix": "UID:",
            "reactions": {
                "processed": "+1",
                "initial_state": "rocket"
            },
            "retries": {
                "max_attempts": 3,
                "backoff_factor": 2
            },
            "rate_limit": {
                "max_requests_per_hour": 1000
            },
            "log": {
                "level": "INFO",
                "format": "{time} | {level} | {message}"
            }
        }
    })
    
    with patch('omegaconf.OmegaConf.load', return_value=config):
        yield

@pytest.fixture
def mock_github():
    """Create a mock Github instance with proper label handling"""
    with patch('gh_store.core.store.Github') as mock_gh:
        mock_repo = Mock()
        
        # Setup owner
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.owner = owner
        
        # Setup labels
        mock_labels = [Mock(name="stored-object")]
        mock_repo.get_labels.return_value = mock_labels
        
        def create_label(name, color="0366d6"):
            new_label = Mock(name=name)
            mock_labels.append(new_label)
            return new_label
        mock_repo.create_label = Mock(side_effect=create_label)
        
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
def cli(cli_env_vars, mock_github):
    """Create CLI instance with mocked dependencies"""
    return CLI()
