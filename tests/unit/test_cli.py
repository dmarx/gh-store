# tests/unit/test_cli.py

import pytest
from unittest.mock import Mock, patch, mock_open
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from gh_store.__main__ import CLI
from gh_store.core.exceptions import GitHubStoreError

@pytest.fixture
def mock_store():
    """Create a mock GitHubStore instance"""
    with patch('gh_store.__main__.GitHubStore') as mock:
        yield mock.return_value

@pytest.fixture
def mock_config_exists():
    """Mock config file existence check"""
    with patch('gh_store.__main__.ensure_config_exists') as mock:
        yield mock

@pytest.fixture
def cli_env_vars():
    """Set up environment variables for CLI"""
    os.environ["GITHUB_TOKEN"] = "test-token"
    os.environ["GITHUB_REPOSITORY"] = "owner/repo"
    yield
    del os.environ["GITHUB_TOKEN"]
    del os.environ["GITHUB_REPOSITORY"]

class TestCLIInitialization:
    def test_init_with_env_vars(self, cli_env_vars, mock_store, mock_config_exists):
        """Test CLI initialization using environment variables"""
        cli = CLI()
        assert cli.token == "test-token"
        assert cli.repo == "owner/repo"
        mock_store.assert_called_once_with(
            token="test-token",
            repo="owner/repo",
            config_path=Path.home() / ".config" / "gh-store" / "config.yml"
        )

    def test_init_with_args(self, mock_store, mock_config_exists):
        """Test CLI initialization using explicit arguments"""
        cli = CLI(token="arg-token", repo="arg/repo", config="custom_config.yml")
        assert cli.token == "arg-token"
        assert cli.repo == "arg/repo"
        assert cli.config_path == Path("custom_config.yml")

    def test_init_no_credentials(self, mock_store, mock_config_exists):
        """Test CLI initialization with no credentials fails"""
        with pytest.raises(ValueError, match="No GitHub token found"):
            CLI(repo="owner/repo")

        with pytest.raises(ValueError, match="No repository specified"):
            CLI(token="test-token")

class TestCLIOperations:
    @pytest.fixture
    def cli(self, cli_env_vars, mock_store, mock_config_exists):
        """Create CLI instance with mocked dependencies"""
        return CLI()

    def test_create(self, cli, mock_store):
        """Test create command"""
        mock_data = {"test": "data"}
        mock_obj = Mock(
            meta=Mock(object_id="test-123", version=1)
        )
        mock_store.create.return_value = mock_obj

        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            cli.create("test-123", "data.json")

        mock_store.create.assert_called_once_with("test-123", mock_data)

    def test_get(self, cli, mock_store):
        """Test get command"""
        mock_obj = Mock(
            meta=Mock(
                object_id="test-123",
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                version=1
            ),
            data={"test": "data"}
        )
        mock_store.get.return_value = mock_obj

        with patch('builtins.print') as mock_print:
            cli.get("test-123")

        mock_store.get.assert_called_once_with("test-123")
        mock_print.assert_called_once()

    def test_get_with_output(self, cli, mock_store):
        """Test get command with output file"""
        mock_obj = Mock(
            meta=Mock(
                object_id="test-123",
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                version=1
            ),
            data={"test": "data"}
        )
        mock_store.get.return_value = mock_obj

        mock_file = mock_open()
        with patch('builtins.open', mock_file):
            cli.get("test-123", output="output.json")

        mock_store.get.assert_called_once_with("test-123")
        mock_file().write.assert_called_once()

    def test_update(self, cli, mock_store):
        """Test update command"""
        mock_data = {"update": "data"}
        mock_obj = Mock(
            meta=Mock(object_id="test-123")
        )
        mock_store.update.return_value = mock_obj

        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            cli.update("test-123", "update.json")

        mock_store.update.assert_called_once_with("test-123", mock_data)

    def test_delete(self, cli, mock_store):
        """Test delete command"""
        cli.delete("test-123")
        mock_store.delete.assert_called_once_with("test-123")

    def test_list_all(self, cli, mock_store):
        """Test list_all command"""
        mock_objects = {
            "test-1": Mock(
                meta=Mock(
                    object_id="test-1",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                    version=1
                ),
                data={"test": 1}
            ),
            "test-2": Mock(
                meta=Mock(
                    object_id="test-2",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                    version=1
                ),
                data={"test": 2}
            )
        }
        mock_store.list_all.return_value = mock_objects

        with patch('builtins.print') as mock_print:
            cli.list_all()

        mock_store.list_all.assert_called_once()
        mock_print.assert_called_once()

    def test_list_updated(self, cli, mock_store):
        """Test list_updated command"""
        timestamp = "2025-01-01T00:00:00Z"
        mock_objects = {
            "test-1": Mock(
                meta=Mock(
                    object_id="test-1",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                    version=1
                ),
                data={"test": 1}
            )
        }
        mock_store.list_updated_since.return_value = mock_objects

        with patch('builtins.print') as mock_print:
            cli.list_updated(timestamp)

        mock_store.list_updated_since.assert_called_once()
        mock_print.assert_called_once()

    def test_get_history(self, cli, mock_store):
        """Test get_history command"""
        mock_history = [
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "type": "initial_state",
                "data": {"status": "new"}
            },
            {
                "timestamp": "2025-01-02T00:00:00Z",
                "type": "update",
                "data": {"status": "updated"}
            }
        ]
        mock_store.issue_handler.get_object_history.return_value = mock_history

        with patch('builtins.print') as mock_print:
            cli.get_history("test-123")

        mock_store.issue_handler.get_object_history.assert_called_once_with("test-123")
        mock_print.assert_called_once()

    def test_process_updates(self, cli, mock_store):
        """Test process_updates command"""
        mock_obj = Mock(
            meta=Mock(object_id="test-123")
        )
        mock_store.process_updates.return_value = mock_obj

        cli.process_updates(123)
        mock_store.process_updates.assert_called_once_with(123)

    def test_snapshot(self, cli, mock_store):
        """Test snapshot command"""
        mock_objects = {
            "test-1": Mock(
                meta=Mock(
                    object_id="test-1",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                    version=1
                ),
                data={"test": 1}
            )
        }
        mock_store.list_all.return_value = mock_objects

        with patch('pathlib.Path.write_text') as mock_write:
            cli.snapshot("snapshot.json")

        mock_store.list_all.assert_called_once()
        mock_write.assert_called_once()

    def test_update_snapshot(self, cli, mock_store):
        """Test update_snapshot command"""
        mock_snapshot = {
            "snapshot_time": "2025-01-01T00:00:00Z",
            "repository": "owner/repo",
            "objects": {}
        }
        mock_objects = {
            "test-1": Mock(
                meta=Mock(
                    object_id="test-1",
                    created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                    updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                    version=1
                ),
                data={"test": 1}
            )
        }
        mock_store.list_updated_since.return_value = mock_objects

        with patch('builtins.open', mock_open(read_data=json.dumps(mock_snapshot))):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.write_text') as mock_write:
                    cli.update_snapshot("snapshot.json")

        mock_store.list_updated_since.assert_called_once()
        mock_write.assert_called_once()

class TestCLIErrorHandling:
    @pytest.fixture
    def cli(self, cli_env_vars, mock_store, mock_config_exists):
        return CLI()

    def test_create_invalid_json(self, cli, mock_store):
        """Test create command with invalid JSON file"""
        with patch('builtins.open', mock_open(read_data="invalid json")):
            with pytest.raises(SystemExit):
                cli.create("test-123", "data.json")

    def test_get_store_error(self, cli, mock_store):
        """Test get command when store raises error"""
        mock_store.get.side_effect = GitHubStoreError("Test error")
        with pytest.raises(SystemExit):
            cli.get("test-123")

    def test_update_missing_file(self, cli, mock_store):
        """Test update command with missing file"""
        with pytest.raises(SystemExit):
            cli.update("test-123", "nonexistent.json")

    def test_update_snapshot_missing_file(self, cli, mock_store):
        """Test update_snapshot command with missing snapshot file"""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(SystemExit):
                cli.update_snapshot("nonexistent.json")
