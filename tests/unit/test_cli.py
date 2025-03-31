# tests/unit/test_cli.py (Updated for Iterator Support)

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
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

# Add to tests/unit/test_cli.py - Enhanced snapshot tests

class TestCLISnapshotOperations:
    """Test snapshot-related CLI operations"""
    
    def test_create_snapshot(self, mock_cli, mock_stored_objects, tmp_path, caplog):
        """Test creating a snapshot via CLI"""
        output_path = tmp_path / "snapshot.json"
        
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            
            # Create iterator from mock_stored_objects
            mock_store.list_all.return_value = mock_stored_objects
            
            # Execute command
            mock_cli.snapshot(output=str(output_path))
            
            # Verify output
            assert output_path.exists()
            snapshot = json.loads(output_path.read_text())
            assert "snapshot_time" in snapshot
            assert len(snapshot["objects"]) == len(mock_stored_objects)
            assert "Snapshot written to" in caplog.text
    
    def test_update_snapshot_with_changes(self, mock_cli, mock_stored_objects, mock_snapshot_file_factory, caplog):
        """Test updating snapshot when objects have actually changed."""
        # Create a snapshot with a known timestamp
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        snapshot_path = mock_snapshot_file_factory(snapshot_time=one_day_ago, include_objects=[0])
        
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            
            # Configure a mock object that's newer than the snapshot
            updated_obj = mock_stored_objects[1]
            updated_obj.meta.updated_at = one_day_ago + timedelta(hours=2)
            
            # Only return the "updated" object
            mock_store.list_updated_since.return_value = [updated_obj]
            
            # Store original snapshot data for comparison
            original_snapshot = json.loads(snapshot_path.read_text())
            
            # Execute command
            mock_cli.update_snapshot(str(snapshot_path))
            
            # Verify correct arguments
            mock_store.list_updated_since.assert_called_once()
            assert mock_store.list_updated_since.call_args[0][0] == one_day_ago
            
            # Read updated snapshot
            updated_snapshot = json.loads(snapshot_path.read_text())
            
            # Verify timestamp was updated
            assert updated_snapshot["snapshot_time"] != original_snapshot["snapshot_time"]
            
            # Verify updated object was added
            assert updated_obj.meta.object_id in updated_snapshot["objects"]
            
            # Verify log message
            assert "Updated 1 objects in snapshot" in caplog.text
    
    def test_update_snapshot_no_changes(self, mock_cli, mock_stored_objects, mock_snapshot_file_factory, caplog):
        """Test not updating snapshot when no objects have changed."""
        # Create a snapshot with a known timestamp
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        snapshot_path = mock_snapshot_file_factory(snapshot_time=one_day_ago)
        
        with patch('gh_store.cli.commands.get_store') as mock_get_store:
            mock_store = Mock()
            mock_get_store.return_value = mock_store
            
            # Return empty iterator - no objects were updated
            mock_store.list_updated_since.return_value = []
            
            # Store original snapshot data for comparison
            original_snapshot = json.loads(snapshot_path.read_text())
            
            # Execute command
            mock_cli.update_snapshot(str(snapshot_path))
            
            # Read updated snapshot
            updated_snapshot = json.loads(snapshot_path.read_text())
            
            # Verify timestamp was NOT updated
            assert updated_snapshot["snapshot_time"] == original_snapshot["snapshot_time"]
            
            # Verify objects are unchanged
            assert updated_snapshot["objects"] == original_snapshot["objects"]
            
            # Verify log message
            assert "No updates found since last snapshot" in caplog.text
    
    def test_update_snapshot_empty_file(self, mock_cli, mock_stored_objects, tmp_path, caplog):
        """Test error handling when updating a snapshot with invalid content."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("{}")
        
        with pytest.raises(Exception) as exc_info:
            mock_cli.update_snapshot(str(empty_file))
            

class TestCLIErrorHandling:
    """Test CLI error handling scenarios"""
    
    def test_invalid_json_data(self, mock_cli):
        """Test handling of invalid JSON input"""
        with pytest.raises(json.decoder.JSONDecodeError) as exc_info:
            mock_cli.create("test-123", "invalid json")
    
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
