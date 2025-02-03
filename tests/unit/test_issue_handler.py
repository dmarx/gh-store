# tests/unit/test_issue_handler.py

from unittest.mock import Mock, mock_open, patch

def test_uid_prefix_handling(store):
    """Test UID prefix handling in IssueHandler"""
    handler = store.issue_handler
    
    # Test adding prefix
    assert handler._add_uid_prefix("test-123") == "UID:test-123"
    assert handler._add_uid_prefix("UID:test-123") == "UID:test-123"  # Already prefixed
    
    # Test removing prefix
    assert handler._remove_uid_prefix("UID:test-123") == "test-123"
    assert handler._remove_uid_prefix("test-123") == "test-123"  # No prefix
    
    # Test extracting ID from labels
    mock_issue = Mock()
    mock_issue.labels = [
        Mock(name="stored-object"),
        Mock(name="UID:test-123")
    ]
    
    object_id = handler.get_object_id_from_labels(mock_issue)
    assert object_id == "test-123"  # Should return ID without prefix
