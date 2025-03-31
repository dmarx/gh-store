# tests/unit/test_cli.py (Updated for Iterator Support)

import json
from pathlib import Path
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch

from gh_store.__main__ import CLI
from gh_store.cli import commands
from gh_store.core.exceptions import GitHubStoreError

class TestCLIBasicOperations:
    """Test basic CLI operations like create, get, update, delete"""
    
    def test_create_object(self, mock_cli, mock_store_response, tmp_path, caplog):
        """Test creating a new object via CLI"""
        data = json.dumps({"name": "test", "value": 42})
        
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            mock_store.create.return_value = mock_store_response
            
            # Execute command
            mock_cli.create("test-123", data)
            
            # Verify store interactions
            mock_store.create.assert_called_once_with(
                "test-123",
                {"name": "test", "value": 42}
            )
            assert "Created object test-123" in caplog.text
    
    def test_get_object(self, mock_cli, mock_store_response, tmp_path):
        """Test retrieving an object via CLI"""
        output_file = tmp_path / "output.json"
        
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            mock_store.get.return_value = mock_store_response
            
            # Execute command
            mock_cli.get("test-123", output=str(output_file))
            
            # Verify output file
            assert output_file.exists()
            content = json.loads(output_file.read_text())
            assert content["object_id"] == "test-123"
            assert content["data"] == {"name": "test", "value": 42}
    
    def test_delete_object(self, mock_cli, mock_store_response, caplog):
        """Test deleting an object via CLI"""
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            
            # Execute command
            mock_cli.delete("test-123")
            
            # Verify store interactions
            mock_store.delete.assert_called_once_with("test-123")
            assert "Deleted object test-123" in caplog.text

class TestCLIUpdateOperations:
    """Test update-related CLI operations"""
    
    def test_update_object(self, mock_cli, mock_store_response, caplog):
        """Test updating an object via CLI"""
        changes = json.dumps({"value": 43})
        
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            mock_store.update.return_value = mock_store_response
            
            # Execute command
            mock_cli.update("test-123", changes)
            
            # Verify store interactions
            mock_store.update.assert_called_once_with(
                "test-123",
                {"value": 43}
            )
            assert "Updated object" in caplog.text
    
    def test_process_updates(self, mock_cli, mock_store_response, caplog):
        """Test processing pending updates via CLI"""
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            mock_store.process_updates.return_value = mock_store_response
            
            # Execute command
            mock_cli.process_updates(123)
            
            # Verify store interactions
            mock_store.process_updates.assert_called_once_with(123)

class TestCLISnapshotOperations:
    """Test snapshot-related CLI operations"""
    
    def test_create_snapshot(self, mock_cli, mock_stored_objects, tmp_path, caplog):
        """Test creating a snapshot via CLI"""
        output_path = tmp_path / "snapshot.json"
        
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            
            # Create iterator from mock_stored_objects
            mock_store.list_all.return_value = mock_stored_objects.values()
            
            # Execute command
            mock_cli.snapshot(output=str(output_path))
            
            # Verify output
            assert output_path.exists()
            snapshot = json.loads(output_path.read_text())
            assert "snapshot_time" in snapshot
            assert len(snapshot["objects"]) == len(mock_stored_objects)
            assert "Snapshot written to" in caplog.text
    
    def test_update_snapshot(self, mock_cli, mock_stored_objects, mock_snapshot_file, caplog):
        """Test updating an existing snapshot via CLI"""
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            
            # Create iterator with just one object for updated objects
            updated_objects = [mock_stored_objects["test-obj-1"]]
            mock_store.list_updated_since.return_value = updated_objects
            
            # Execute command
            mock_cli.update_snapshot(str(mock_snapshot_file))
            
            # Verify snapshot was updated
            updated_snapshot = json.loads(mock_snapshot_file.read_text())
            assert "Updated 1 objects in snapshot" in caplog.text

class TestCLIErrorHandling:
    """Test CLI error handling scenarios"""
    
    def test_invalid_json_data(self, mock_cli, caplog):
        """Test handling of invalid JSON input"""
        with pytest.raises(SystemExit) as exc_info:
            mock_cli.create("test-123", "invalid json")
            
        assert exc_info.value.code == 1
        assert "Invalid JSON data provided" in caplog.text
    
    def test_store_error_handling(self, mock_cli, caplog):
        """Test handling of GitHubStore errors"""
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            mock_store.get.side_effect = GitHubStoreError("Test error")
            
            with pytest.raises(SystemExit) as exc_info:
                mock_cli.get("test-123")
            
            assert exc_info.value.code == 1
            assert "Failed to get object" in caplog.text
    
    def test_file_not_found(self, mock_cli, caplog):
        """Test handling of missing snapshot file"""
        with pytest.raises(FileNotFoundError) as exc_info:
            mock_cli.update_snapshot("/nonexistent/path")
            
        assert "Snapshot file not found" in caplog.text

# should probably just deprecate all the config stuff.
# class TestCLIConfigHandling:
#     """Test CLI configuration handling"""
    
#     def test_init_creates_config(self, mock_cli, tmp_path, caplog):
#         """Test initialization of new config file."""
#         config_path = tmp_path / "new_config.yml"
        
#         with patch('gh_store.cli.commands.ensure_config_exists') as mock_ensure:
#             # Run command
#             mock_cli.init(config=str(config_path))
            
#             # Verify config creation was attempted
#             mock_ensure.assert_called_once_with(config_path)
    
#     def test_custom_config_path(self, mock_cli, mock_config, mock_store_response):
#         """Test using custom config path"""
#         with patch('gh_store.cli.commands.get_store') as mock_get_store, \
#              patch('gh_store.cli.commands.ensure_config_exists') as mock_ensure:
#             mock_store = Mock()
#             mock_get_store.return_value = mock_store
#             mock_store.get.return_value = mock_store_response
            
#             # Execute command with custom config
#             mock_cli.get("test-123", config=str(mock_config))
            
#             # Verify store creation
#             mock_get_store.assert_called_with(
#                 token=None,
#                 repo=None,
#                 config=str(mock_config)
#             )
