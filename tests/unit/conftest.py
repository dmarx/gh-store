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


@pytest.fixture(autouse=True)
def mock_config_file():
    """Mock OmegaConf config loading"""
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
    
    with patch('omegaconf.OmegaConf.load', return_value=config) as mock_load:
        yield mock_load

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
    """Create a mock comment with configurable attributes"""
    comments = []
    
    def _make_comment(
        user_login="repo-owner",
        body=None,
        comment_id=1,
        reactions=None,
        created_at=None  # Added support for created_at
    ):
        comment = Mock()
        
        # Set up user properly
        user = Mock()
        user.login = user_login
        comment.user = user
        
        # Handle body serialization
        comment.body = json.dumps(body) if body else "{}"
        comment.id = comment_id
        
        # Set up reactions
        comment.get_reactions = Mock(return_value=reactions or [])
        comment.create_reaction = Mock()
        
        # Set timestamp
        comment.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        
        comments.append(comment)
        return comment
    
    yield _make_comment
    
    # Cleanup
    for comment in comments:
        comment.reset_mock()

@pytest.fixture
def mock_label_factory():
    """Create GitHub-style label objects"""
    def create_label(name: str):
        label = Mock()
        label.name = name
        return label
    return create_label

def wrap_in_list(val_or_list):
    """Helper to ensure value is a list"""
    if val_or_list is None:
        return []
    return val_or_list if isinstance(val_or_list, (list, tuple)) else [val_or_list]

@pytest.fixture
def mock_issue(mock_label_factory):
    """Create a mock issue with complete GitHub-like structure"""
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
        
        # Handle body serialization properly
        issue.body = json.dumps(body) if body not in (None, "") else "{}"
        
        # Set up comments with proper wrapper
        mock_comments = wrap_in_list(comments)
        issue.get_comments = Mock(return_value=mock_comments)
        issue.create_comment = Mock()
        
        # Set up default labels if none provided
        default_labels = [
            mock_label_factory("stored-object"),
            mock_label_factory("UID:test-123")
        ]
        # Handle both string and Mock label inputs
        if labels is not None:
            issue.labels = [
                label if isinstance(label, Mock) else mock_label_factory(label)
                for label in wrap_in_list(labels)
            ]
        else:
            issue.labels = default_labels
        
        # Set timestamps
        issue.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
        
        # Set up edit method
        issue.edit = Mock()
        
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
    
    # Add the override inside the fixture function
    def get_object_id(issue) -> str:
        """Override get_object_id_from_labels for testing"""
        for label in issue.labels:
            if hasattr(label, 'name') and label.name.startswith("UID:"):
                return label.name[4:]  # Strip "UID:" prefix
        return "test-123"  # Default ID for testing
    
    # Override the method
    store.issue_handler.get_object_id_from_labels = get_object_id
    
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

# Add these fixtures to your conftest.py

@pytest.fixture
def history_mock_comments(mock_comment):
    """Create series of comments representing object history"""
    comments = []
    
    # Initial state
    comments.append(mock_comment(
        user_login="repo-owner",
        body={
            "type": "initial_state",
            "_data": {"name": "test", "value": 42},
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-01T00:00:00Z",
                "update_mode": "append"
            }
        },
        comment_id=1,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
    ))
    
    # First update
    comments.append(mock_comment(
        user_login="repo-owner",
        body={
            "_data": {"value": 43},
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-02T00:00:00Z",
                "update_mode": "append"
            }
        },
        comment_id=2,
        created_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
    ))
    
    # Second update
    comments.append(mock_comment(
        user_login="repo-owner",
        body={
            "_data": {"value": 44},
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-03T00:00:00Z",
                "update_mode": "append"
            }
        },
        comment_id=3,
        created_at=datetime(2025, 1, 3, tzinfo=timezone.utc)
    ))
    
    return comments

# Add to the existing store fixture in conftest.py to make this method available:
# Inside the store fixture, before the return:
store.issue_handler.get_object_id_from_labels = lambda issue: "test-123"  # Override for testing
