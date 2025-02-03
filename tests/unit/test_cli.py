# tests/unit/test_cli.py

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

from gh_store.__main__ import CLI
from gh_store.core.exceptions import GitHubStoreError

def test_init_creates_default_config(mock_env_setup, test_config_dir):
    """Test that init creates default config in expected location"""
    cli = CLI()
    
    # Config shouldn't exist yet
    config_path = test_config_dir / "config.yml"
    assert not config_path.exists()
    
    # Run init
    cli.init()
    
    # Verify config was created
    assert config_path.exists()
    assert "store:" in config_path.read_text()

def test_init_skips_existing_config(test_config_file):
    """Test that init doesn't overwrite existing config"""
    original_content = test_config_file.read_text()
    
    cli = CLI()
    cli.init()
    
    assert test_config_file.read_text() == original_content

def test_process_updates_with_default_config(mock_github, mock_env_setup, test_config_file):
    """Test processing updates using default config location"""
    _, mock_repo = mock_github
    
    # Setup mock issue
    mock_issue = Mock()
    mock_issue.user = Mock(login="repo-owner")
    mock_repo.get_issue.return_value = mock_issue
    
    cli = CLI()
    cli.process_updates(
        issue=123,
        token="fake-token",
        repo="owner/repo"
    )
    
    # Verify issue was processed
    mock_repo.get_issue.assert_called_with(123)

def test_process_updates_with_custom_config(mock_github, tmp_path):
    """Test processing updates with custom config path"""
    _, mock_repo = mock_github
    
    # Create custom config
    config_path = tmp_path / "custom_config.yml"
    # Use the same reaction values as fixture but with custom label
    config_path.write_text("""
store:
  base_label: "custom-label"
  uid_prefix: "TEST:"
  reactions:
    processed: "+1"
    initial_state: "rocket"
    """)
    
    # Setup mock issue
    mock_issue = Mock()
    mock_issue.user = Mock(login="repo-owner")
    mock_repo.get_issue.return_value = mock_issue
    
    cli = CLI()
    cli.process_updates(
        issue=123,
        token="fake-token",
        repo="owner/repo",
        config=str(config_path)
    )
    
    # Verify issue was processed
    mock_repo.get_issue.assert_called_with(123)

def test_snapshot_creation(mock_github, mock_issue, test_config_file, tmp_path):
    """Test creating a snapshot of all objects"""
    _, mock_repo = mock_github
    
    # Setup mock issues with data
    issues = [
        mock_issue(
            number=1,
            body={"data": "test1"},
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
        ),
        mock_issue(
            number=2,
            body={"data": "test2"},
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
        )
    ]
    mock_repo.get_issues.return_value = issues
    
    # Create snapshot
    output_path = tmp_path / "snapshot.json"
    cli = CLI()
    cli.snapshot(
        token="fake-token",
        repo="owner/repo",
        output=str(output_path)
    )
    
    # Verify snapshot contents
    assert output_path.exists()
    snapshot = json.loads(output_path.read_text())
    assert "snapshot_time" in snapshot
    assert "objects" in snapshot
    assert len(snapshot["objects"]) == 2

def test_update_snapshot(mock_github, mock_issue, test_config_file, tmp_path):
    """Test updating an existing snapshot"""
    _, mock_repo = mock_github
    
    # Create initial snapshot
    snapshot_path = tmp_path / "snapshot.json"
    initial_snapshot = {
        "snapshot_time": "2025-01-01T00:00:00Z",
        "repository": "owner/repo",
        "objects": {
            "test-1": {
                "data": {"value": 1},
                "meta": {
                    "created_at": "2025-01-01T00:00:00Z",
                    "updated_at": "2025-01-01T00:00:00Z",
                    "version": 1
                }
            }
        }
    }
    snapshot_path.write_text(json.dumps(initial_snapshot))
    
    # Setup mock issue with updates
    updated_issue = mock_issue(
        number=1,
        body={"value": 2},
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
    )
    mock_repo.get_issues.return_value = [updated_issue]
    
    # Update snapshot
    cli = CLI()
    cli.update_snapshot(
        token="fake-token",
        repo="owner/repo",
        snapshot_path=str(snapshot_path)
    )
    
    # Verify snapshot was updated
    updated_snapshot = json.loads(snapshot_path.read_text())
    assert updated_snapshot["objects"]["test-1"]["data"]["value"] == 2

def test_nonexistent_snapshot_error(tmp_path):
    """Test error handling for nonexistent snapshot file"""
    cli = CLI()
    with pytest.raises(FileNotFoundError):
        cli.update_snapshot(
            token="fake-token",
            repo="owner/repo",
            snapshot_path=str(tmp_path / "nonexistent.json")
        )

def test_process_updates_error_handling(mock_github):
    """Test error handling in process_updates command"""
    _, mock_repo = mock_github
    mock_repo.get_issue.side_effect = GitHubStoreError("Test error")
    
    cli = CLI()
    with pytest.raises(SystemExit) as exc_info:
        cli.process_updates(
            issue=123,
            token="fake-token",
            repo="owner/repo"
        )
    
    assert exc_info.value.code == 1

def test_command_requires_token():
    """Test that commands require GitHub token"""
    cli = CLI()
    with pytest.raises(SystemExit) as exc_info:
        cli.process_updates(
            issue=123,
            token=None,  # Missing token
            repo="owner/repo"
        )
    
    assert exc_info.value.code == 1

def test_snapshot_with_no_updates(mock_github, mock_issue, test_config_file, tmp_path):
    """Test snapshot update when no changes exist"""
    _, mock_repo = mock_github
    mock_repo.get_issues.return_value = []  # No updated issues
    
    # Create initial snapshot
    snapshot_path = tmp_path / "snapshot.json"
    initial_snapshot = {
        "snapshot_time": "2025-01-01T00:00:00Z",
        "repository": "owner/repo",
        "objects": {}
    }
    snapshot_path.write_text(json.dumps(initial_snapshot))
    
    # Try to update snapshot
    cli = CLI()
    cli.update_snapshot(
        token="fake-token",
        repo="owner/repo",
        snapshot_path=str(snapshot_path)
    )
    
    # Verify snapshot wasn't modified
    updated_snapshot = json.loads(snapshot_path.read_text())
    assert updated_snapshot == initial_snapshot
