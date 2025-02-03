# tests/unit/test_cli_snapshot.py

from datetime import datetime, timezone
import json
from unittest.mock import Mock, patch, mock_open


class TestCLISnapshotOperations:

def test_snapshot(self, cli, mock_github, mock_issue):
    """Test snapshot command"""
    mock_gh, mock_repo = mock_github
    
    mock_data = {"test": "data"}
    test_issue = mock_issue(
        body=mock_data,
        labels=["stored-object", "UID:test-1"]
    )
    mock_repo.get_issues.return_value = [test_issue]

    with patch('pathlib.Path.write_text') as mock_write:
        cli.snapshot("snapshot.json")

    mock_write.assert_called_once()
    snapshot_data = json.loads(mock_write.call_args[0][0])
    assert "test-1" in snapshot_data["objects"]
    assert snapshot_data["objects"]["test-1"]["data"] == mock_data

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

    def test_snapshot_empty(self, cli, mock_github):
        """Test snapshot command with no objects"""
        mock_gh, mock_repo = mock_github
        mock_repo.get_issues.return_value = []

        with patch('pathlib.Path.write_text') as mock_write:
            cli.snapshot("snapshot.json")

        # Verify empty snapshot
        mock_write.assert_called_once()
        snapshot_data = json.loads(mock_write.call_args[0][0])
        assert not snapshot_data["objects"]

    def test_update_snapshot_no_changes(self, cli, mock_github):
        """Test update_snapshot when objects haven't changed"""
        mock_gh, mock_repo = mock_github
        
        # Mock existing snapshot
        mock_snapshot = {
            "snapshot_time": "2025-01-01T00:00:00Z",
            "repository": "owner/repo",
            "objects": {
                "test-1": {
                    "data": {"test": "data"},
                    "meta": {
                        "created_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-01T00:00:00Z",
                        "version": 1
                    }
                }
            }
        }
        
        # Mock issue with same data
        mock_issue = Mock(
            body=json.dumps({"test": "data"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            labels=[Mock(name="stored-object"), Mock(name="UID:test-1")],
            get_comments=Mock(return_value=[])
        )
        mock_repo.get_issues.return_value = [mock_issue]

        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_snapshot))), \
             patch('pathlib.Path.write_text') as mock_write:
            cli.update_snapshot("snapshot.json")

        # Verify no update was made
        mock_write.assert_not_called()
