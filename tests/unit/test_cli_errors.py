# tests/unit/test_cli_errors.py
from datetime import datetime, timezone 
import pytest
from unittest.mock import Mock, patch, mock_open
import json

from gh_store.core.exceptions import GitHubStoreError

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

    def test_update_snapshot_invalid_json(self, cli, mock_github):
        """Test update_snapshot command with invalid JSON in snapshot"""
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data="invalid json")):
            with pytest.raises(SystemExit):
                cli.update_snapshot("snapshot.json")

    def test_github_api_error(self, cli, mock_github):
        """Test handling of GitHub API errors"""
        mock_gh, mock_repo = mock_github
        mock_repo.get_issues.side_effect = Exception("API Error")
        
        with pytest.raises(SystemExit):
            cli.list_all()

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

    def test_process_updates_invalid_issue(self, cli, mock_github):
        """Test process_updates with invalid issue number"""
        mock_gh, mock_repo = mock_github
        mock_repo.get_issue.side_effect = Exception("Issue not found")
        
        with pytest.raises(SystemExit):
            cli.process_updates(999)

    def test_update_snapshot_permission_error(self, cli, mock_github):
        """Test update_snapshot with file permission error"""
        mock_gh, mock_repo = mock_github
        
        mock_snapshot = {
            "snapshot_time": "2025-01-01T00:00:00Z",
            "repository": "owner/repo",
            "objects": {}
        }
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_snapshot))), \
             patch('pathlib.Path.write_text', side_effect=PermissionError):
            with pytest.raises(SystemExit):
                cli.update_snapshot("snapshot.json")
