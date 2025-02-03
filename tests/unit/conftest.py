# tests/unit/conftest.py

import os
from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from unittest.mock import Mock, mock_open, patch
from omegaconf import OmegaConf
from github import GithubException

from gh_store.core.store import GitHubStore, DEFAULT_CONFIG_PATH
from gh_store.core.version import CLIENT_VERSION

@pytest.fixture
def default_config():
    """Create a consistent default config for testing"""
    return OmegaConf.create({
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

@pytest.fixture
def mock_env_setup(monkeypatch, test_config_dir):
    """Mock environment and config setup for tests"""
    # Mock HOME directory to control config location
    monkeypatch.setenv("HOME", str(test_config_dir.parent.parent))
    
    # Mock default config access
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
    with patch('pathlib.Path.write_text') as mock_write, \
         patch('importlib.resources.files') as mock_files:
        mock_files.return_value.joinpath.return_value.read_bytes = lambda: default_config.encode('utf-8')
        yield mock_files

@pytest.fixture
def test_config_dir(tmp_path):
    """Create temporary config directory"""
    config_dir = tmp_path / ".config" / "gh-store"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

@pytest.fixture
def test_config_file(test_config_dir):
    """Create test config file"""
    config_path = test_config_dir / "config.yml"
    config_path.write_text("""
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
""")
    return config_path

@pytest.fixture
def mock_comment():
    """Create a mock comment with GitHub-like structure"""
    comments = []
    
    def _make_comment(user_login="repo-owner", body=None, comment_id=1, reactions=None):
        comment = Mock()
        # Set up user properly
        user = Mock()
        user.login = user_login
        comment.user = user
        
        # Proper body handling
        comment.body = json.dumps(body) if body else "{}"
        comment.id = comment_id
        
        # Set up reactions
        comment.get_reactions = Mock(return_value=reactions or [])
        comment.create_reaction = Mock()
        
        comments.append(comment)
        return comment
    
    yield _make_comment
    
    # Cleanup
    for comment in comments:
        comment.reset_mock()

@pytest.fixture
def mock_issue():
    """Create a mock issue with GitHub-like structure"""
    def _make_issue(
        number=1,
        user_login="repo-owner",
        body=None,
        comments=None,
        labels=None,
        created_at=None,
        updated_at=None,
        state="closed"
    ):
        issue = Mock()
        issue.number = number
        issue.state = state
        
        # Set up user properly
        user = Mock()
        user.login = user_login
        issue.user = user
        
        # Handle body serialization
        issue.body = json.dumps(body) if body else "{}"
        
        # Set up comments
        issue.get_comments = Mock(return_value=comments or [])
        issue.create_comment = Mock()
        
        # Set up labels with proper structure
        issue.labels = [
            label if isinstance(label, Mock) else Mock(name=label)
            for label in (labels or ["stored-object", "UID:test-123"])
        ]
        
        # Set timestamps
        issue.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
        
        return issue
    
    return _make_issue

@pytest.fixture
def mock_github():
    """Create a mock Github instance with proper structure"""
    with patch('gh_store.core.store.Github') as mock_gh:
        # Setup mock repo
        mock_repo = Mock()
        
        # Setup owner
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.owner = owner
        mock_repo.get_owner = Mock(return_value=owner)
        
        # Setup labels
        mock_labels = [Mock(name="stored-object")]
        mock_repo.get_labels = Mock(return_value=mock_labels)
        
        def create_label(name, color="0366d6"):
            new_label = Mock(name=name)
            mock_labels.append(new_label)
            return new_label
        mock_repo.create_label = Mock(side_effect=create_label)
        
        # Mock CODEOWNERS access
        mock_content = Mock()
        mock_content.decoded_content = b"* @repo-owner"
        def get_contents_side_effect(path):
            if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
                return mock_content
            raise GithubException(404, "Not found")
        mock_repo.get_contents = Mock(side_effect=get_contents_side_effect)
        
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo

@pytest.fixture
def store(mock_github, default_config):
    """Create GitHubStore instance with mocked dependencies"""
    _, mock_repo = mock_github
    store = GitHubStore(token="fake-token", repo="owner/repo")
    store.repo = mock_repo  # Use mock repo
    store.access_control.repo = mock_repo  # Ensure access control uses same mock
    store.config = default_config  # Use the fixture's config
    return store

@pytest.fixture
def cli_env_vars():
    """Setup environment variables for CLI"""
    os.environ["GITHUB_TOKEN"] = "test-token"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"
    yield
    del os.environ["GITHUB_TOKEN"]
    del os.environ["GITHUB_REPOSITORY"]

@pytest.fixture
def cli(cli_env_vars, mock_github, mock_env_setup):
    """Create CLI instance with mocked dependencies"""
    return CLI()
