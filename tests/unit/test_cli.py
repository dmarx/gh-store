# tests/unit/test_cli.py

import pytest
from unittest.mock import Mock, patch, mock_open, call
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from gh_store.__main__ import CLI
from gh_store.core.exceptions import GitHubStoreError

@pytest.fixture
def mock_github():
    """Create a mock Github instance"""
    with patch('gh_store.core.store.Github') as mock_gh:
        # Setup mock repo
        mock_repo = Mock()
        
        # Mock the owner info
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.owner = owner
        
        # Set up mock repo in mock Github instance
        mock_gh.return_value.get_repo.return_value = mock_repo
        
        yield mock_gh, mock_repo

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

@pytest.fixture
def cli(cli_env_vars, mock_github, mock_config_exists):
    """Create CLI instance with mocked dependencies"""
    mock_gh, mock_repo = mock_github
    return CLI()

class TestCLIInitialization:
    def test_init_with_env_vars(self, cli_env_vars, mock_github, mock_config_exists):
        """Test CLI initialization using environment variables"""
        mock_gh, _ = mock_github
        cli = CLI()
        assert cli.token == "test-token"
        assert cli.repo == "owner/repo"
        
        # Verify Github was initialized with correct token
        mock_gh.assert_called_once_with("test-token")
        # Verify correct repo was requested
        mock_gh.return_value.get_repo.assert_called_once_with("owner/repo")

    def test_init_with_args(self, mock_github, mock_config_exists):
        """Test CLI initialization using explicit arguments"""
        mock_gh, _ = mock_github
        cli = CLI(token="arg-token", repo="arg/repo", config="custom_config.yml")
        assert cli.token == "arg-token"
        assert cli.repo == "arg/repo"
        assert cli.config_path == Path("custom_config.yml")

    def test_init_no_credentials(self, mock_github, mock_config_exists):
        """Test CLI initialization with no credentials fails"""
        with pytest.raises(ValueError, match="No GitHub token found"):
            CLI(repo="owner/repo")

        with pytest.raises(ValueError, match="No repository specified"):
            CLI(token="test-token")

class TestCLIOperations:
    def test_create(self, cli, mock_github):
        """Test create command"""
        mock_gh, mock_repo = mock_github
        mock_data = {"test": "data"}
        
        # Mock issue creation
        mock_issue = Mock(
            number=123,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            body=json.dumps(mock_data)
        )
        mock_repo.create_issue.return_value = mock_issue
        
        # Mock comment creation and reactions
        mock_comment = Mock(id=456)
        mock_issue.create_comment.return_value = mock_comment
        
        # Mock labels
        mock_repo.get_labels.return_value = [Mock(name="stored-object")]

        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            cli.create("test-123", "data.json")

        # Verify issue creation
        mock_repo.create_issue.assert_called_once()
        call_kwargs = mock_repo.create_issue.call_args[1]
        assert "test-123" in call_kwargs["title"]
        assert mock_data == json.loads(call_kwargs["body"])
        
        # Verify comment and reactions
        mock_issue.create_comment.assert_called_once()
        comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
        assert comment_data["type"] == "initial_state"
        assert comment_data["_data"] == mock_data

    def test_get(self, cli, mock_github):
        """Test get command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issue response
        mock_issue = Mock(
            body=json.dumps({"test": "data"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-1")
            ],
            get_comments=Mock(return_value=[])
        )
        mock_repo.get_issues.return_value = [mock_issue]

        with patch('pathlib.Path.write_text') as mock_write:
            cli.snapshot("snapshot.json")

        # Verify snapshot creation
        mock_repo.get_issues.assert_called_once_with(
            state="closed",
            labels=["stored-object"]
        )
        
        # Verify snapshot content
        mock_write.assert_called_once()
        snapshot_data = json.loads(mock_write.call_args[0][0])
        assert "snapshot_time" in snapshot_data
        assert snapshot_data["repository"] == "owner/repo"
        assert "test-1" in snapshot_data["objects"]
        assert snapshot_data["objects"]["test-1"]["data"] == {"test": "data"}

    def test_update_snapshot(self, cli, mock_github):
        """Test update_snapshot command"""
        mock_gh, mock_repo = mock_github
        
        # Mock existing snapshot
        mock_snapshot = {
            "snapshot_time": "2025-01-01T00:00:00Z",
            "repository": "owner/repo",
            "objects": {
                "test-1": {
                    "data": {"test": "old"},
                    "meta": {
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z",
                        "version": 1
                    }
                }
            }
        }
        
        # Mock issues response for updates
        mock_issue = Mock(
            body=json.dumps({"test": "updated"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-1")
            ],
            get_comments=Mock(return_value=[])
        )
        mock_repo.get_issues.return_value = [mock_issue]

        # Setup file mocks
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_snapshot))), \
             patch('pathlib.Path.write_text') as mock_write:
            cli.update_snapshot("snapshot.json")

        # Verify snapshot update
        mock_write.assert_called_once()
        updated_data = json.loads(mock_write.call_args[0][0])
        assert "test-1" in updated_data["objects"]
        assert updated_data["objects"]["test-1"]["data"] == {"test": "updated"}
        assert updated_data["snapshot_time"] > mock_snapshot["snapshot_time"]

class TestCLIErrorHandling:
    def test_create_invalid_json(self, cli, mock_github):
        """Test create command with invalid JSON file"""
        with patch('builtins.open', mock_open(read_data="invalid json")):
            with pytest.raises(SystemExit):
                cli.create("test-123", "data.json")

    def test_get_nonexistent_object(self, cli, mock_github):
        """Test get command for nonexistent object"""
        mock_gh, mock_repo = mock_github
        mock_repo.get_issues.return_value = []
        
        with pytest.raises(SystemExit):
            cli.get("nonexistent")

    def test_get_store_error(self, cli, mock_github):
        """Test get command when store operation fails"""
        mock_gh, mock_repo = mock_github
        mock_repo.get_issues.side_effect = GitHubStoreError("Test error")
        
        with pytest.raises(SystemExit):
            cli.get("test-123")

    def test_update_missing_file(self, cli, mock_github):
        """Test update command with missing file"""
        with pytest.raises(SystemExit):
            cli.update("test-123", "nonexistent.json")

    def test_update_concurrent_processing(self, cli, mock_github):
        """Test update when object is being processed"""
        mock_gh, mock_repo = mock_github
        
        # Mock open issue to simulate concurrent processing
        mock_issue = Mock(
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issues.return_value = [mock_issue]
        
        with patch('builtins.open', mock_open(read_data='{"test": "data"}')):
            with pytest.raises(SystemExit):
                cli.update("test-123", "update.json")

    def test_delete_nonexistent_object(self, cli, mock_github):
        """Test delete command for nonexistent object"""
        mock_gh, mock_repo = mock_github
        mock_repo.get_issues.return_value = []
        
        with pytest.raises(SystemExit):
            cli.delete("nonexistent")

    def test_unauthorized_process_updates(self, cli, mock_github):
        """Test process_updates with unauthorized creator"""
        mock_gh, mock_repo = mock_github
        
        # Mock issue with unauthorized creator
        mock_issue = Mock(
            number=123,
            user=Mock(login="unauthorized"),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issue.return_value = mock_issue
        
        with pytest.raises(SystemExit):
            cli.process_updates(123)

    def test_update_snapshot_missing_file(self, cli, mock_github):
        """Test update_snapshot command with missing snapshot file"""
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(SystemExit):
                cli.update_snapshot("nonexistent.json")

    def test_update_snapshot_malformed(self, cli, mock_github):
        """Test update_snapshot command with malformed snapshot data"""
        mock_snapshot = {
            # Missing required fields
            "objects": {}
        }
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_snapshot))):
            with pytest.raises(SystemExit):
                cli.update_snapshot("snapshot.json")

    def test_update_snapshot_no_updates(self, cli, mock_github):
        """Test update_snapshot when no updates are available"""
        mock_gh, mock_repo = mock_github
        
        # Mock existing snapshot
        mock_snapshot = {
            "snapshot_time": "2025-01-01T00:00:00Z",
            "repository": "owner/repo",
            "objects": {}
        }
        
        # Mock no updates available
        mock_repo.get_issues.return_value = []
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_snapshot))), \
             patch('pathlib.Path.write_text') as mock_write:
            cli.update_snapshot("snapshot.json")
            
        # Verify no write occurred
        mock_write.assert_not_called()

    def test_github_api_error(self, cli, mock_github):
        """Test handling of GitHub API errors"""
        mock_gh, mock_repo = mock_github
        mock_repo.get_issues.side_effect = Exception("API Error")
        
        with pytest.raises(SystemExit):
            cli.list_all()

    def test_invalid_config_path(self, mock_github):
        """Test initialization with invalid config path"""
        with pytest.raises(FileNotFoundError):
            CLI(
                token="test-token",
                repo="owner/repo",
                config="/nonexistent/path/config.yml"
            )

    def test_process_updates_no_changes(self, cli, mock_github):
        """Test process_updates when no new updates exist"""
        mock_gh, mock_repo = mock_github
        
        # Mock issue with no unprocessed updates
        mock_issue = Mock(
            number=123,
            user=Mock(login="repo-owner"),
            body=json.dumps({"test": "data"}),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issue.return_value = mock_issue
        
        # All comments have been processed (have reactions)
        mock_comments = [
            Mock(
                id=1,
                user=Mock(login="repo-owner"),
                body=json.dumps({
                    "_data": {"status": "updated"},
                    "_meta": {
                        "client_version": "0.1.0",
                        "timestamp": "2025-01-02T00:00:00Z",
                        "update_mode": "append"
                    }
                }),
                get_reactions=Mock(return_value=[Mock(content="+1")])
            )
        ]
        mock_issue.get_comments.return_value = mock_comments
        
        cli.process_updates(123)
        
        # Verify issue was closed without updates
        mock_issue.edit.assert_called_with(
            body=mock.ANY,
            state="closed"
        )

    def test_create_with_empty_data(self, cli, mock_github):
        """Test create command with empty JSON data"""
        mock_gh, mock_repo = mock_github
        empty_data = {}
        
        # Mock issue creation
        mock_issue = Mock(
            number=123,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
        )
        mock_repo.create_issue.return_value = mock_issue
        
        with patch('builtins.open', mock_open(read_data=json.dumps(empty_data))):
            cli.create("test-123", "data.json")
        
        # Verify empty object was created
        mock_repo.create_issue.assert_called_once()
        call_kwargs = mock_repo.create_issue.call_args[1]
        assert json.loads(call_kwargs["body"]) == empty_data

if __name__ == '__main__':
    pytest.main([__file__])d_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issues.return_value = [mock_issue]
        
        # Mock comments for version
        mock_issue.get_comments.return_value = []

        with patch('builtins.print') as mock_print:
            cli.get("test-123")

        # Verify issue fetch
        mock_repo.get_issues.assert_called_once()
        mock_print.assert_called_once()

    def test_get_with_output(self, cli, mock_github):
        """Test get command with output file"""
        mock_gh, mock_repo = mock_github
        
        # Mock issue response
        mock_issue = Mock(
            body=json.dumps({"test": "data"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issues.return_value = [mock_issue]
        
        # Mock comments for version
        mock_issue.get_comments.return_value = []

        with patch('builtins.open', mock_open()) as mock_file:
            cli.get("test-123", output="output.json")

        # Verify file output
        mock_file.assert_called_once_with("output.json", "w")
        write_calls = mock_file().write.call_args_list
        assert any("test-123" in str(call) for call in write_calls)
        assert any("2025-01-01" in str(call) for call in write_calls)

    def test_update(self, cli, mock_github):
        """Test update command"""
        mock_gh, mock_repo = mock_github
        mock_data = {"update": "data"}
        
        # Mock issue response
        mock_issue = Mock(
            number=123,
            body=json.dumps({"test": "data"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        
        # Mock issue listing (check for open issues)
        def get_issues_side_effect(**kwargs):
            if kwargs.get("state") == "open":
                return []  # No open issues
            return [mock_issue]
        mock_repo.get_issues.side_effect = get_issues_side_effect
        
        # Mock comment creation
        mock_comment = Mock(id=456)
        mock_issue.create_comment.return_value = mock_comment

        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            cli.update("test-123", "update.json")

        # Verify comment creation
        mock_issue.create_comment.assert_called_once()
        comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
        assert comment_data["_data"] == mock_data
        
        # Verify issue reopened
        mock_issue.edit.assert_called_with(state="open")

    def test_delete(self, cli, mock_github):
        """Test delete command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issue response
        mock_issue = Mock(
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issues.return_value = [mock_issue]

        cli.delete("test-123")

        # Verify issue edited
        mock_issue.edit.assert_called_once_with(
            state="closed",
            labels=["archived", "stored-object", "UID:test-123"]
        )

    def test_list_all(self, cli, mock_github):
        """Test list_all command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issues response
        mock_issues = [
            Mock(
                body=json.dumps({"test": 1}),
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                labels=[
                    Mock(name="stored-object"),
                    Mock(name="UID:test-1")
                ],
                get_comments=Mock(return_value=[])
            ),
            Mock(
                body=json.dumps({"test": 2}),
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                labels=[
                    Mock(name="stored-object"),
                    Mock(name="UID:test-2")
                ],
                get_comments=Mock(return_value=[])
            )
        ]
        mock_repo.get_issues.return_value = mock_issues

        with patch('builtins.print') as mock_print:
            cli.list_all()

        # Verify issue listing
        mock_repo.get_issues.assert_called_once_with(
            state="closed",
            labels=["stored-object"]
        )
        mock_print.assert_called_once()

    def test_list_updated(self, cli, mock_github):
        """Test list_updated command"""
        mock_gh, mock_repo = mock_github
        timestamp = "2025-01-01T00:00:00Z"
        
        # Mock issues response
        mock_issue = Mock(
            body=json.dumps({"test": "updated"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-1")
            ],
            get_comments=Mock(return_value=[])
        )
        mock_repo.get_issues.return_value = [mock_issue]

        with patch('builtins.print') as mock_print:
            cli.list_updated(timestamp)

        # Verify issue listing with since parameter
        call_kwargs = mock_repo.get_issues.call_args[1]
        assert call_kwargs["since"] == datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        mock_print.assert_called_once()

    def test_get_history(self, cli, mock_github):
        """Test get_history command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issues response
        mock_issue = Mock(number=123)
        mock_repo.get_issues.return_value = [mock_issue]
        
        # Mock comments
        mock_comments = [
            Mock(
                id=1,
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                body=json.dumps({
                    "type": "initial_state",
                    "_data": {"status": "new"},
                    "_meta": {
                        "client_version": "0.1.0",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "update_mode": "append"
                    }
                })
            ),
            Mock(
                id=2,
                created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                body=json.dumps({
                    "_data": {"status": "updated"},
                    "_meta": {
                        "client_version": "0.1.0",
                        "timestamp": "2025-01-02T00:00:00Z",
                        "update_mode": "append"
                    }
                })
            )
        ]
        mock_issue.get_comments.return_value = mock_comments

        with patch('builtins.print') as mock_print:
            cli.get_history("test-123")

        # Verify comment retrieval
        mock_issue.get_comments.assert_called_once()
        mock_print.assert_called_once()

    def test_process_updates(self, cli, mock_github):
        """Test process_updates command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issue and user
        mock_issue = Mock(
            number=123,
            user=Mock(login="repo-owner"),
            body=json.dumps({"test": "data"}),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issue.return_value = mock_issue
        
        # Mock update comments
        mock_comments = [
            Mock(
                id=1,
                user=Mock(login="repo-owner"),
                body=json.dumps({
                    "_data": {"status": "updated"},
                    "_meta": {
                        "client_version": "0.1.0",
                        "timestamp": "2025-01-02T00:00:00Z",
                        "update_mode": "append"
                    }
                }),
                get_reactions=Mock(return_value=[])
            )
        ]
        mock_issue.get_comments.return_value = mock_comments

        cli.process_updates(123)

        # Verify updates processed
        mock_issue.edit.assert_called_with(
            body=mock.ANY,
            state="closed"
        )
        body = json.loads(mock_issue.edit.call_args[1]["body"])
        assert body["status"] == "updated"
        
    def test_snapshot(self, cli, mock_github):
        """Test snapshot command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issues response
        mock_issue = Mock(
            body=json.dumps({"test": "data"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-1")
            ],
            get_comments=Mock(return_value=[])
        )
        mock_repo.get_issues.return_value = [mock_issue]

        with patch('pathlib.Path.write_text') as mock_write:
            cli.snapshot("snapshot.json")

        # Verify snapshot creation
        mock_repo.get_issues.assert_called_once_with(
            state="closed",
            labels=["stored-object"]
        )
        
        # Verify snapshot content
        mock_write.assert_called_once()
        snapshot_data = json.loads(mock_write.call_args[0][0])
        assert "snapshot_time" in snapshot_data
        assert snapshot_data["repository"] == "owner/repo"
        assert "test-1" in snapshot_data["objects"]
        assert snapshot_data["objects"]["test-1"]["data"] == {"test": "data"}
