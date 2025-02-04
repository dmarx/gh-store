# tests/unit/test_cli.py
"""Command-line interface tests for gh-store."""

import os
from pathlib import Path
import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch
from loguru import logger

from gh_store.__main__ import CLI
from gh_store.core.exceptions import GitHubStoreError

def test_process_updates_success(mock_cli, mock_store_response):
    """Test successful processing of updates."""
    with patch('gh_store.core.store.GitHubStore.process_updates', return_value=mock_store_response):
        mock_cli.process_updates(
            issue=123,
            token="test-token",
            repo="owner/repo"
        )

def test_process_updates_error(mock_cli, mock_config, caplog):
    """Test handling of errors during update processing."""
    with patch('gh_store.core.store.GitHubStore.process_updates') as mock_process:
        # Mock error
        mock_process.side_effect = GitHubStoreError("Test error")
        
        # Run command
        with pytest.raises(SystemExit) as exc_info:
            mock_cli.process_updates(
                issue=123,
                token="test-token",
                repo="owner/repo",
                config=str(mock_config)
            )
        
        assert exc_info.value.code == 1
        assert "Failed to process updates: Test error" in caplog.text

def test_snapshot_success(mock_cli, mock_stored_objects, tmp_path):
    """Test successful creation of snapshot."""
    output_path = tmp_path / "test_snapshot.json"
    
    with patch('gh_store.core.store.GitHubStore.list_all', return_value=mock_stored_objects):
        # Run command
        mock_cli.snapshot(
            token="test-token",
            repo="owner/repo",
            output=str(output_path)
        )
        
        # Verify snapshot
        assert output_path.exists()
        snapshot = json.loads(output_path.read_text())
        assert "snapshot_time" in snapshot
        assert snapshot["repository"] == "owner/repo"
        assert "test-obj-1" in snapshot["objects"]
        assert "test-obj-2" in snapshot["objects"]

def test_update_snapshot_success(mock_cli, mock_stored_objects, mock_snapshot_file):
    """Test successful update of existing snapshot."""
    current_time = datetime(2025, 2, 1, tzinfo=timezone.utc)
    
    with patch('gh_store.core.store.GitHubStore.list_updated_since') as mock_list, \
         patch('gh_store.__main__.datetime') as mock_datetime:
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
        
        # Verify snapshot
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

def test_cli_environment_variables(monkeypatch, mock_config, mock_store_response):
    """Test CLI uses environment variables correctly."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("HOME", str(mock_config.parent.parent.parent))
    
    with patch('gh_store.core.store.Github') as MockGithub, \
         patch('gh_store.core.store.GitHubStore.process_updates', return_value=mock_store_response):
        # Mock Github instance
        mock_repo = Mock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        
        cli = CLI()
        cli.process_updates(issue=123)
        
        # Verify Github initialization
        MockGithub.assert_called_once_with("test-token")
        MockGithub.return_value.get_repo.assert_called_once_with("owner/repo")

def test_cli_custom_config_path(mock_cli, mock_config, mock_store_response):
    """Test CLI respects custom config path."""
    with patch('gh_store.core.store.Github') as MockGithub, \
         patch('gh_store.core.store.GitHubStore.process_updates', return_value=mock_store_response):
        # Mock Github instance
        mock_repo = Mock()
        MockGithub.return_value.get_repo.return_value = mock_repo
        
        # Run command
        mock_cli.process_updates(
            issue=123,
            token="test-token",
            repo="owner/repo",
            config=str(mock_config)
        )
        
        # Verify Github initialization
        MockGithub.assert_called_once_with("test-token")
        MockGithub.return_value.get_repo.assert_called_once_with("owner/repo")
