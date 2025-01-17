# tests/unit/test_config.py

from pathlib import Path
import pytest
from unittest.mock import patch, mock_open
import yaml

from gh_store.core.store import GitHubStore, DEFAULT_CONFIG_PATH

@pytest.fixture
def mock_github():
    with patch('gh_store.core.store.Github') as mock:
        mock_repo = mock.return_value.get_repo.return_value
        yield mock, mock_repo

def test_store_uses_default_config_when_no_path_provided(mock_github):
    """Test that store uses packaged default config when no config exists"""
    _, mock_repo = mock_github
    
    # Mock the default config path to not exist
    with patch('pathlib.Path.exists', return_value=False):
        # Mock the packaged default config
        mock_config = """
store:
  base_label: "stored-object"
  uid_prefix: "UID:"
  reactions:
    processed: "📝"
    initial_state: "🔰"
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
            mock_files.return_value.joinpath.return_value.open.return_value = mock_open(read_data=mock_config)()
            
            store = GitHubStore(token="fake-token", repo="owner/repo")
            
            # Verify config was loaded from packaged default
            assert store.config.store.base_label == "stored-object"
            assert store.config.store.reactions.processed == "📝"

def test_store_uses_provided_config_path(mock_github, tmp_path):
    """Test that store uses provided config path when it exists"""
    _, mock_repo = mock_github
    
    # Create a test config file
    config_path = tmp_path / "test_config.yml"
    test_config = {
        "store": {
            "base_label": "test-label",
            "uid_prefix": "TEST:",
            "reactions": {
                "processed": "✅",
                "initial_state": "🆕"
            }
        }
    }
    config_path.write_text(yaml.dump(test_config))
    
    store = GitHubStore(token="fake-token", repo="owner/repo", config_path=config_path)
    
    # Verify config was loaded from provided path
    assert store.config.store.base_label == "test-label"
    assert store.config.store.reactions.processed == "✅"

def test_store_raises_error_for_nonexistent_custom_config(mock_github):
    """Test that store raises error when custom config path doesn't exist"""
    _, mock_repo = mock_github
    
    with pytest.raises(FileNotFoundError):
        GitHubStore(
            token="fake-token",
            repo="owner/repo",
            config_path=Path("/nonexistent/config.yml")
        )

def test_default_config_path_is_in_user_config_dir():
    """Test that default config path is in user's config directory"""
    expected_path = Path.home() / ".config" / "gh-store" / "config.yml"
    assert DEFAULT_CONFIG_PATH == expected_path
