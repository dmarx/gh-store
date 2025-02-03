# tests/unit/conftest.py

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import pytest 
from unittest.mock import Mock, mock_open, patch
from github import GithubException
from omegaconf import OmegaConf

from gh_store.__main__ import CLI
from gh_store.core.store import GitHubStore
from gh_store.core.exceptions import GitHubStoreError

# System-wide test fixtures
@pytest.fixture(autouse=True)
def mock_config():
    """Mock configuration with consistent default values"""
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
    
    with patch('omegaconf.OmegaConf.load', return_value=config) as mock_load, \
         patch('importlib.resources.files') as mock_files:
        # Mock both OmegaConf loading and default config file
        mock_files.return_value.joinpath.return_value.open.return_value = \
            mock_open(read_data=OmegaConf.to_yaml(config))()
        yield mock_load

@pytest.fixture
def mock_github():
    """Create a mock Github instance with proper repository structure"""
    with patch('gh_store.core.store.Github') as mock_gh:
        # Setup mock repo
        mock_repo = Mock()
        
        # Setup owner with proper attributes
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.owner = owner
        
        # Setup label management
        mock_labels = [Mock(name="stored-object")]
        mock_repo.get_labels = Mock(return_value=mock_labels)
        
        def create_label(name, color="0366d6"):
            new_label = Mock(name=name)
            mock_labels.append(new_label)
            return new_label
        mock_repo.create_label = Mock(side_effect=create_label)
        
        # Mock CODEOWNERS file access
        mock_content = Mock()
        mock_content.decoded_content = b"* @repo-owner"
        def get_contents_side_effect(path):
            if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
                return mock_content
            raise GithubException(404, "Not found")
        mock_repo.get_contents = Mock(side_effect=get_contents_side_effect)
        
        # Setup the mock Github instance
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo

@pytest.fixture
def mock_issue():
    """Create a mock issue with proper GitHub-like structure"""
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
        
        # Basic attributes
        issue.number = number
        issue.state = state
        
        # User setup
        user = Mock()
        user.login = user_login
        issue.user = user
        
        # Proper body serialization
        issue.body = json.dumps(body) if body else "{}"
        
        # Default timestamps
        issue.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
        issue.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
        
        # Label handling
        if labels is None:
            labels = ["stored-object", "UID:test-123"]
        issue.labels = [
            label if isinstance(label, Mock) else Mock(name=label)
            for label in labels
        ]
        
        # Comments setup
        mock_comments = comments if comments is not None else []
        issue.get_comments = Mock(return_value=mock_comments)
        issue.create_comment = Mock()
        
        return issue
    
    return _make_issue

@pytest.fixture
def cli_env_vars():
    """Setup environment variables for CLI"""
    os.environ["GITHUB_TOKEN"] = "test-token"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"
    yield
    del os.environ["GITHUB_TOKEN"]
    del os.environ["GITHUB_REPOSITORY"]

@pytest.fixture
def cli(cli_env_vars, mock_github, mock_config):
    """Create a CLI instance with all dependencies mocked"""
    return CLI()

@pytest.fixture 
def mock_config_exists():
    """Mock config file existence check"""
    with patch('gh_store.__main__.ensure_config_exists') as mock:
        yield mock
