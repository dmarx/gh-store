# tests/unit/test_cli.py
"""Command-line interface tests for gh-store."""

from pathlib import Path
import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch, mock_open
from loguru import logger

from gh_store.__main__ import CLI
from gh_store.core.exceptions import GitHubStoreError

def test_process_updates_success(cli, mock_issue, mock_github):
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
    _, mock_repo = mock_github
    mock_repo.get_issue.return_value = issue
    
    # Run command
    cli.process_updates(
        issue=issue_number,
        token="test-token",
        repo="owner/repo"
    )
    
    # Verify issue was processed and closed
    issue.edit.assert_called_with(
        body=json.dumps(test_data, indent=2),
        state="closed"
    )

def test_process_updates_error(cli, mock_github, caplog):
    """Test handling of errors during update processing."""
    # Mock GitHubStore to raise an error
    _, mock_repo = mock_github
    mock_repo.get_issue.side_effect = GitHubStoreError("Test error")
    
    # Run command and verify it exits with error
    with pytest.raises(SystemExit) as exc_info:
        cli.process_updates(
            issue=123,
            token="test-token",
            repo="owner/repo"
        )
    
    assert exc_info.value.code == 1
    assert "Failed to process updates: Test error" in caplog.text

def test_snapshot_success(cli, mock_github, tmp_path):
    """Test successful creation of snapshot."""
    test_data = {
        "test-obj": {
            "data": {"name": "test", "value": 42},
            "meta": {
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
                "version": 1
            }
        }
    }
    
    # Mock store.list_all() to return test data
    with patch('gh_store.core.store.GitHubStore.list_all') as mock_list:
        mock_obj = Mock()
        mock_obj.data = test_data["test-obj"]["data"]
        mock_obj.meta.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_obj.meta.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        mock_obj.meta.version = 1
        mock_list.return_value = {"test-obj": mock_obj}
        
        # Create output path
        output_path = tmp_path / "test_snapshot.json"
        
        # Run command
        cli.snapshot(
            token="test-token",
            repo="owner/repo",
            output=str(output_path)
        )
        
        # Verify snapshot file was created with correct content
        assert output_path.exists()
        snapshot = json.loads(output_path.read_text())
        assert "snapshot_time" in snapshot
        assert snapshot["repository"] == "owner/repo"
        assert "test-obj" in snapshot["objects"]

def test_update_snapshot_success(cli, mock_github, tmp_path):
    """Test successful update of existing snapshot."""
    # Create initial snapshot
    initial_snapshot = {
        "snapshot_time": "2025-01-01T00:00:00Z",
        "repository": "owner/repo",
        "objects": {
            "test-obj": {
                "data": {"name": "test", "value": 42},
                "meta": {
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "version": 1
                }
            }
        }
    }
    
    snapshot_path = tmp_path / "test_snapshot.json"
    snapshot_path.write_text(json.dumps(initial_snapshot))
    
    # Mock store.list_updated_since() to return updated object
    with patch('gh_store.core.store.GitHubStore.list_updated_since') as mock_list:
        mock_obj = Mock()
        mock_obj.data = {"name": "test", "value": 43}
        mock_obj.meta.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_obj.meta.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        mock_obj.meta.version = 2
        mock_list.return_value = {"test-obj": mock_obj}
        
        # Run command
        cli.update_snapshot(
            token="test-token",
            repo="owner/repo",
            snapshot_path=str(snapshot_path)
        )
        
        # Verify snapshot was updated
        updated_snapshot = json.loads(snapshot_path.read_text())
        assert updated_snapshot["objects"]["test-obj"]["data"]["value"] == 43
        assert updated_snapshot["objects"]["test-obj"]["meta"]["version"] == 2

def test_init_creates_config(cli, tmp_path, caplog):
    """Test initialization of new config file."""
    config_path = tmp_path / "config.yml"
    
    # Mock default config content
    default_config = """
store:
  base_label: "stored-object"
  uid_prefix: "UID:"
"""
    
    with patch('gh_store.__main__.importlib.resources.files') as mock_files:
        mock_files.return_value.joinpath.return_value.open.return_value = mock_open(
            read_data=default_config.encode()
        )()
        
        # Run command
        cli.init(config=str(config_path))
        
        # Verify config file was created
        assert config_path.exists()
        assert "Configuration initialized" in caplog.text

def test_init_existing_config(cli, tmp_path, caplog):
    """Test init command with existing config."""
    config_path = tmp_path / "config.yml"
    config_path.touch()  # Create empty config file
    
    # Run command
    cli.init(config=str(config_path))
    
    # Verify warning was logged
    assert "Configuration file already exists" in caplog.text

def test_cli_environment_variables(monkeypatch):
    """Test CLI uses environment variables correctly."""
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    
    cli = CLI()
    
    with patch('gh_store.core.store.GitHubStore') as mock_store:
        # Run command using env vars
        cli.process_updates(issue=123)
        
        # Verify store was initialized with env vars
        mock_store.assert_called_with(
            token="test-token",
            repo="owner/repo",
            config_path=cli.default_config_path
        )

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
        mock_store.assert_called_with(
            token="test-token",
            repo="owner/repo",
            config_path=config_path
        )
