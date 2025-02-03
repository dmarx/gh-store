# tests/unit/test_store_list_ops.py

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from unittest.mock import Mock

def test_list_updated_since(store, mock_issue):
    """Test fetching objects updated since timestamp"""
    timestamp = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
    object_id = "test-123"
    
    # Create mock issue updated after timestamp
    issue = mock_issue(
        created_at=timestamp - timedelta(minutes=30),
        updated_at=timestamp + timedelta(minutes=30)
    )
    store.repo.get_issues.return_value = [issue]
    
    # Mock object retrieval
    mock_obj = Mock()
    mock_obj.meta.updated_at = timestamp + timedelta(minutes=30)
    store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    
    # Test listing
    updated = store.list_updated_since(timestamp)
    
    # Verify
    store.repo.get_issues.assert_called_once()
    call_kwargs = store.repo.get_issues.call_args[1]
    assert call_kwargs["since"] == timestamp
    assert len(updated) == 1
    assert mock_obj in updated.values()

def test_list_updated_since_no_updates(store, mock_issue):
    """Test when no updates since timestamp"""
    timestamp = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
    
    # Create mock issue updated before timestamp
    issue = mock_issue(
        created_at=timestamp - timedelta(minutes=30),
        updated_at=timestamp - timedelta(minutes=30)
    )
    store.repo.get_issues.return_value = [issue]
    
    # Mock object retrieval
    mock_obj = Mock()
    mock_obj.meta.updated_at = timestamp - timedelta(minutes=30)
    store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    
    # Test listing
    updated = store.list_updated_since(timestamp)
    
    # Verify no updates found
    assert len(updated) == 0

def test_list_all_objects(store, mock_issue, mock_label_factory):
    """Test listing all objects in store"""
    # Create mock issues with proper labels
    issues = [
        mock_issue(
            number=1,
            labels=[
                mock_label_factory("stored-object"),
                mock_label_factory("UID:test-1")
            ]
        ),
        mock_issue(
            number=2,
            labels=[
                mock_label_factory("stored-object"),
                mock_label_factory("UID:test-2")
            ]
        )
    ]
    store.repo.get_issues.return_value = issues
    
    # Mock object retrieval
    def get_object_by_number(number):
        mock_obj = Mock()
        mock_obj.meta.object_id = f"test-{number}"
        return mock_obj
    
    store.issue_handler.get_object_by_number = Mock(
        side_effect=get_object_by_number
    )
    
    # Test listing all
    objects = store.list_all()
    
    # Verify
    assert len(objects) == 2
    assert "test-1" in objects
    assert "test-2" in objects

def test_list_all_skips_archived(store, mock_issue, mock_label_factory):
    """Test that archived objects are skipped in listing"""
    # Create archived and active issues
    archived_issue = mock_issue(
        number=1,
        labels=[
            mock_label_factory("stored-object"),
            mock_label_factory("UID:test-1"),
            mock_label_factory("archived")
        ]
    )
    active_issue = mock_issue(
        number=2,
        labels=[
            mock_label_factory("stored-object"),
            mock_label_factory("UID:test-2")
        ]
    )
    
    store.repo.get_issues.return_value = [archived_issue, active_issue]
    
    # Mock object retrieval
    def get_object_by_number(number):
        mock_obj = Mock()
        mock_obj.meta.object_id = f"test-{number}"
        return mock_obj
    
    store.issue_handler.get_object_by_number = Mock(
        side_effect=get_object_by_number
    )
    
    # Test listing
    objects = store.list_all()
    
    # Verify only active object listed
    assert len(objects) == 1
    assert "test-2" in objects
    assert "test-1" not in objects

def test_list_all_handles_invalid_labels(store, mock_issue, mock_label_factory):
    """Test handling of issues with invalid label structure"""
    # Create issue missing UID label
    invalid_issue = mock_issue(
        number=1,
        labels=[mock_label_factory("stored-object")]  # Missing UID label
    )
    
    # Create valid issue with explicit labels including UID
    valid_issue = mock_issue(
        number=2,
        labels=[
            mock_label_factory("stored-object"),
            mock_label_factory("UID:test-2")  # Explicitly set UID label
        ]
    )
    
    store.repo.get_issues.return_value = [invalid_issue, valid_issue]
    
    # Mock object retrieval
    def get_object_by_number(number):
        mock_obj = Mock()
        mock_obj.meta.object_id = f"test-{number}"
        mock_obj.meta.label = f"UID:test-{number}"
        return mock_obj
    
    store.issue_handler.get_object_by_number = Mock(
        side_effect=get_object_by_number
    )
    
    # Test listing
    objects = store.list_all()
    
    # Verify only valid object listed
    assert len(objects) == 1
    assert "test-2" in objects
