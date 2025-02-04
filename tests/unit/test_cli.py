# tests/unit/test_cli.py
"""Command-line interface tests for gh-store."""

from pathlib import Path
import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch
from loguru import logger

from gh_store.__main__ import CLI, GitHubStoreError

def test_process_updates_success(cli, mock_issue):
    """Test successful processing of updates."""
    # Setup test data
    issue_number = 123
    test_data = {"name": "test", "value": 42}
    
    # Create mock issue
    issue = mock_issue(
        number=issue_number,
        user_login="repo-owner",
        body=test_data,
        state="open"
    )
    
    with patch('gh_store.core.store.GitHubStore.process_updates') as mock_process:
        # Run command
        cli.process_updates(
            issue=issue_number,
            token="test-token",
            repo="owner/repo"
        )
        
        # Verify process_updates was called
        mock_process.assert_called_once_with(issue_number)

def test_process_updates_error(cli, caplog):
    """Test handling of errors during update processing."""
    with patch('gh_store.core.store.GitHubStore.process_updates') as mock_process:
        # Mock process_updates to raise an error
        mock_process.side_effect = GitHubStoreError("Test error")
        
        # Run command and verify it exits with error
        with pytest.raises(SystemExit) as exc_info:
            cli.process_updates(
                issue=123,
                token="test-token",
                repo="owner/repo"
            )
        
        assert exc_info.value.code == 1
        assert "Failed to process updates: Test error" in caplog.text

def test_snapshot_success(cli, mock_stored_objects, tmp_path):
    """Test successful creation of snapshot."""
    output_path = tmp_path / "test_snapshot.json"
    
    with patch('gh_store.core.store.GitHubStore.list_all') as mock_list:
        # Setup mock data
        mock_list.return_value = mock_stored_objects
        
        # Run command
        cli.snapshot(
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

def test_update_snapshot_success(cli, mock_stored_objects, mock_snapshot_file, mock_snapshot_data):
    """Test successful update of existing snapshot."""
    with patch('gh_store.core.store.GitHubStore.list_updated_since') as mock_list:
        # Setup mock data for updated objects
        mock_list.return_value = {k: v for k, v in mock_stored_objects.items() if k == "test-obj-1"}
        
        # Run command
        cli.update_snapshot(
            token="test-token",
            repo="owner/repo",
            snapshot_path=str(mock_snapshot_file)
        )
        
        # Verify snapshot was updated
        updated_snapshot = json.loads(mock_snapshot_file.read_text())
        assert len(updated_snapshot["objects"]) == 2  # Should retain both objects
        assert datetime.fromisoformat(updated_snapshot["objects"]["test-obj-1"]["meta"]["updated_at"]) > \
               datetime.fromisoformat(updated_snapshot["snapshot_time"])

def test_init_creates_config(cli, tmp_path, caplog):
    """Test initialization of new config file."""
    config_path = tmp_path / "new_config.yml"
    
    # Run command
    cli.init(config=str(config_path))
    
    # Verify config was created
    assert config_path.exists()
    assert "Configuration initialized" in caplog.text

def test_init_existing_config(cli, mock_env_setup, caplog):
    """Test init command with existing config."""
    # Run command using existing config path
    cli.init(config=str(mock_env_setup))
    
    # Verify warning was logged
    assert "Configuration file already exists" in caplog.text

def test_cli_environment_variables(monkeypatch):
    """Test CLI uses environment variables correctly."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    
    with patch('gh_store.core.store.GitHubStore') as mock_store:
        cli = CLI()
        cli.process_updates(issue=123)
        
        # Verify store was initialized with env vars
        mock_store.assert_called_once()
        call_args = mock_store.call_args[1]
        assert call_args["token"] == "test-token"
        assert call_args["repo"] == "owner/repo"

def test_cli_custom_config_path(cli, tmp_path):
    """Test CLI respects custom config path."""
    config_path = tmp_path / "custom_config.yml"
    
    with patch('gh_store.core.store.GitHubStore') as mock_store:
        # Run command with custom config
        cli.process_updates(
            issue=123,
            token="test-token",
            repo="owner/repo",
            config=str(config_path)
        )
        
        # Verify store was initialized with custom config
        mock_store.assert_called_once()
        call_args = mock_store.call_args[1]
        assert call_args["config_path"] == config_path
