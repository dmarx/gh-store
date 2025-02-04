# tests/unit/test_cli.py
"""Command-line interface tests for gh-store."""

import os
import sys
from pathlib import Path
import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch
from loguru import logger

from gh_store.__main__ import CLI
from gh_store.core.exceptions import GitHubStoreError

@pytest.fixture(autouse=True)
def setup_loguru():
    """Configure loguru for testing."""
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level="INFO")  # Add test handler
    yield
    logger.remove()  # Clean up

@pytest.fixture
def mock_cli():
    """Mock CLI with test configuration."""
    with patch('gh_store.__main__.ensure_config_exists') as mock_ensure:
        cli = CLI()
        yield cli

def test_process_updates_success(mock_cli, mock_issue):
    """Test successful processing of updates."""
    issue_number = 123
    
    with patch('gh_store.core.store.Github') as MockGithub, \
         patch('gh_store.core.store.GitHubStore.process_updates') as mock_process:
        # Mock Github instance
        mock_repo = Mock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        
        # Mock process_updates
        mock_process.return_value = Mock(meta=Mock(object_id="test-123"))
        
        # Run command
        mock_cli.process_updates(
            issue=issue_number,
            token="test-token",
            repo="owner/repo"
        )
        
        # Verify process_updates was called
        mock_process.assert_called_once_with(issue_number)

def test_process_updates_error(mock_cli, caplog):
    """Test handling of errors during update processing."""
    with patch('gh_store.core.store.Github') as MockGithub, \
         patch('gh_store.core.store.GitHubStore.process_updates') as mock_process:
        # Mock Github instance
        mock_repo = Mock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        
        # Mock process_updates to raise error
        mock_process.side_effect = GitHubStoreError("Test error")
        
        # Run command and verify it exits with error
        with pytest.raises(SystemExit) as exc_info:
            mock_cli.process_updates(
                issue=123,
                token="test-token",
                repo="owner/repo"
            )
        
        assert exc_info.value.code == 1
        assert "Failed to process updates: Test error" in caplog.text

def test_snapshot_success(mock_cli, mock_stored_objects, tmp_path):
    """Test successful creation of snapshot."""
    output_path = tmp_path / "test_snapshot.json"
    
    with patch('gh_store.core.store.Github') as MockGithub, \
         patch('gh_store.core.store.GitHubStore.list_all') as mock_list:
        # Mock Github instance
        mock_repo = Mock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        
        # Mock list_all
        mock_list.return_value = mock_stored_objects
        
        # Run command
        mock_cli.snapshot(
            token="test-token",
            repo="owner/repo",
            output=str(output_path)
        )
        
        # Verify snapshot was created
        assert output_path.exists()
        snapshot = json.loads(output_path.read_text())
        assert "snapshot_time" in snapshot
        assert snapshot["repository"] == "owner/repo"
        assert "test-obj-1" in snapshot["objects"]
        assert "test-obj-2" in snapshot["objects"]

def test_update_snapshot_success(mock_cli, mock_stored_objects, mock_snapshot_file):
    """Test successful update of existing snapshot."""
    current_time = datetime(2025, 2, 1, tzinfo=timezone.utc)
    
    with patch('gh_store.core.store.Github') as MockGithub, \
         patch('gh_store.core.store.GitHubStore.list_updated_since') as mock_list, \
         patch('datetime.datetime') as mock_datetime:
        # Mock Github instance
        mock_repo = Mock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        
        # Mock list_updated_since
        mock_list.return_value = {"test-obj-1": mock_stored_objects["test-obj-1"]}
        
        # Mock datetime
        mock_datetime.now.return_value = current_time
        mock_datetime.fromisoformat = datetime.fromisoformat
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        
        # Run command
        mock_cli.update_snapshot(
            token="test-token",
            repo="owner/repo",
            snapshot_path=str(mock_snapshot_file)
        )
        
        # Verify snapshot was updated
        updated_snapshot = json.loads(mock_snapshot_file.read_text())
        assert updated_snapshot["snapshot_time"] == current_time.isoformat()
        assert "test-obj-1" in updated_snapshot["objects"]

def test_init_creates_config(mock_cli, tmp_path, caplog):
    """Test initialization of new config file."""
    config_path = tmp_path / "new_config.yml"
    
    # Run command
    mock_cli.init(config=str(config_path))
    
    # Verify config creation was attempted
    from gh_store.__main__ import ensure_config_exists
    ensure_config_exists.assert_called_once_with(config_path)

def test_init_existing_config(mock_cli, tmp_path, caplog):
    """Test init command with existing config."""
    config_path = tmp_path / "existing_config.yml"
    config_path.touch()
    
    with patch('gh_store.__main__.logger.warning') as mock_warning:
        # Run command
        mock_cli.init(config=str(config_path))
        
        # Verify warning was logged
        mock_warning.assert_called_once_with(f"Configuration file already exists at {config_path}")

def test_cli_environment_variables(tmp_path, monkeypatch):
    """Test CLI uses environment variables correctly."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    
    with patch('gh_store.core.store.Github') as MockGithub, \
         patch('gh_store.core.store.GitHubStore.process_updates') as mock_process:
        # Mock Github instance
        mock_repo = Mock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        
        # Mock process_updates
        mock_process.return_value = Mock(meta=Mock(object_id="test-123"))
        
        cli = CLI()
        cli.process_updates(issue=123)
        
        # Verify Github was initialized with correct args
        MockGithub.assert_called_once_with("test-token")
        MockGithub.return_value.get_repo.assert_called_once_with("owner/repo")

def test_cli_custom_config_path(mock_cli, tmp_path):
    """Test CLI respects custom config path."""
    config_path = tmp_path / "custom_config.yml"
    
    with patch('gh_store.core.store.Github') as MockGithub, \
         patch('gh_store.core.store.GitHubStore.process_updates') as mock_process:
        # Mock Github instance
        mock_repo = Mock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        
        # Mock process_updates
        mock_process.return_value = Mock(meta=Mock(object_id="test-123"))
        
        # Run command with custom config
        mock_cli.process_updates(
            issue=123,
            token="test-token",
            repo="owner/repo",
            config=str(config_path)
        )
        
        # Verify store was initialized with custom config
        MockGithub.assert_called_once_with("test-token")
        MockGithub.return_value.get_repo.assert_called_once_with("owner/repo")
