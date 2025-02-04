# tests/unit/fixtures/cli.py
"""CLI-specific fixtures for gh-store unit tests."""

from pathlib import Path
import pytest
from unittest.mock import patch
from gh_store.__main__ import CLI

@pytest.fixture
def cli_env_vars():
    """Setup environment variables for CLI testing."""
    with patch.dict('os.environ', {
        'GITHUB_TOKEN': 'test-token',
        'GITHUB_REPOSITORY': 'owner/repo'
    }):
        yield

@pytest.fixture
def mock_env_setup(monkeypatch, test_config_dir: Path):
    """Mock environment setup for CLI testing."""
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
    with patch('importlib.resources.files') as mock_files:
        mock_files.return_value.joinpath.return_value.read_bytes = \
            lambda: default_config.encode('utf-8')
        yield mock_files

@pytest.fixture
def cli(cli_env_vars, mock_github, mock_env_setup):
    """Create CLI instance with mocked dependencies."""
    return CLI()

@pytest.fixture
def mock_github_auth():
    """Mock GitHub authentication and API initialization."""
    with patch('gh_store.core.store.Github') as mock_gh:
        # Mock the repo setup
        mock_repo = Mock()
        mock_repo.get_issue.return_value = Mock(state="closed")
        mock_repo.get_issues.return_value = []
        mock_repo.owner = Mock(login="owner", type="User")
        
        # Setup the mock Github instance
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo
