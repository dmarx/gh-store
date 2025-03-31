# tests/unit/test_store_list_ops.py

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from unittest.mock import Mock

from gh_store.core.constants import LabelNames


def test_list_updated_since(store, mock_issue_factory):
    """Test fetching objects updated since timestamp"""
    timestamp = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
    object_id = "test-123"
    
    # Create mock issue updated after timestamp - include gh-store label
    issue = mock_issue_factory(
        labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, f"{LabelNames.UID_PREFIX}{object_id}"],
        updated_at = timestamp + timedelta(minutes=30),
        created_at = timestamp - timedelta(minutes=30),
    )
    store.repo.get_issues.return_value = [issue]
    
    # Mock object retrieval
    # mock_obj = Mock()
    # mock_obj.meta.updated_at = timestamp + timedelta(minutes=30)
    # store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    
    # Test listing
    updated = list(store.list_updated_since(timestamp))
    
    # Verify
    store.repo.get_issues.assert_called_once()
    call_kwargs = store.repo.get_issues.call_args[1]
    assert call_kwargs["since"] == timestamp
    assert call_kwargs["labels"] == [LabelNames.GH_STORE, LabelNames.STORED_OBJECT]  # Query by stored-object for active objects
    assert len(updated) == 1
    assert updated[0].meta.object_id == object_id

def test_list_updated_since_no_updates(store, mock_issue):
    """Test when no updates since timestamp"""
    timestamp = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
    
    # Create mock issue updated before timestamp
    issue = mock_issue(
        created_at=timestamp - timedelta(minutes=30),
        updated_at=timestamp - timedelta(minutes=30),
        labels=[str(LabelNames.GH_STORE), "stored-object", f"UID:foo"],
    )
    store.repo.get_issues.return_value = [issue]
    
    # Mock object retrieval
    mock_obj = Mock()
    mock_obj.meta.updated_at = timestamp - timedelta(minutes=30)
    store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    
    # Test listing
    updated = list(store.list_updated_since(timestamp))
    
    # Verify no updates found
    assert len(updated) == 0
# Updates needed for test_store_list_ops.py

def test_list_all_objects(store, mock_issue, mock_label_factory):
    """Test listing all objects in store"""
    # Create mock issues with proper labels - include gh-store label
    issues = [
        mock_issue(
            number=1,
            labels=["gh-store", "stored-object", f"UID:test-1"],
        ),
        mock_issue(
            number=2,
            labels=["gh-store", "stored-object", f"UID:test-2"],
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
    objects = [obj.meta.object_id for obj in list(store.list_all())]
    
    # Verify
    assert len(objects) == 2
    assert "test-1" in objects
    assert "test-2" in objects
    
    # Verify the query was made with stored-object label
    store.repo.get_issues.assert_called_with(
        state="closed",
        labels=["gh-store", "stored-object"]
    )

def test_list_all_skips_archived(store, mock_issue, mock_label_factory):
    """Test that archived objects are skipped in listing"""
    # Create archived and active issues - include gh-store label
    archived_issue = mock_issue(
        number=1,
        labels=[
            "gh-store",
            "stored-object",
            "UID:test-1",
            "archived",
        ]
    )
    active_issue = mock_issue(
        number=2,
        labels=["gh-store", "stored-object", "UID:test-2"]
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
    objects = [obj.meta.object_id for obj in list(store.list_all())]
    
    # Verify only active object listed
    # 
    assert len(objects) == 1
    assert "test-2" in objects
    assert "test-1" not in objects

def test_list_all_handles_invalid_labels(store, mock_issue, mock_label_factory):
    """Test handling of issues with invalid label structure"""
    # Create issue missing UID label
    invalid_issue = mock_issue(
        number=1,
        labels=["gh-store", "stored-object"]  # Missing UID label
    )
    
    # Create valid issue with explicit labels including UID
    valid_issue = mock_issue(
        number=2,
        labels=["gh-store", "stored-object","UID:test-2"]  # Explicitly set UID label
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
    objects = [obj.meta.object_id for obj in list(store.list_all())]
    
    # Verify only valid object listed
    assert len(objects) == 1
    assert "test-2" in objects
