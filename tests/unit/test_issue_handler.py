# tests/unit/test_issue_handler.py

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from gh_store.core.exceptions import DuplicateUIDError
from gh_store.handlers.issue import IssueHandler

@pytest.fixture
def mock_repo():
    return Mock()

@pytest.fixture
def config():
    return Mock(
        store=Mock(
            base_label="stored-object",
            uid_prefix="UID:"
        )
    )

@pytest.fixture
def handler(mock_repo, config):
    return IssueHandler(mock_repo, config)

def test_validate_uid_uniqueness_with_single_issue(handler):
    """Test validation passes with single matching issue"""
    mock_issue = Mock()
    handler.repo.get_issues.return_value = [mock_issue]
    
    # Should not raise error
    handler.validate_uid_uniqueness("test-123")
    
    handler.repo.get_issues.assert_called_once_with(
        labels=["stored-object", "UID:test-123"],
        state="all"
    )

def test_validate_uid_uniqueness_with_duplicate_issues(handler):
    """Test validation fails with multiple matching issues"""
    mock_issues = [Mock(number=1), Mock(number=2)]
    handler.repo.get_issues.return_value = mock_issues
    
    with pytest.raises(DuplicateUIDError) as exc:
        handler.validate_uid_uniqueness("test-123")
    
    assert "Found multiple issues ([1, 2])" in str(exc.value)

def test_process_issue_updates_with_duplicate_uid(handler):
    """Test processing skips issue with duplicate UID"""
    issue_number = 123
    mock_issue = Mock(number=issue_number)
    handler.repo.get_issue.return_value = mock_issue
    
    # Mock getting object ID from labels
    handler.get_object_id_from_labels = Mock(return_value="test-123")
    
    # Mock validate_uid_uniqueness to raise error
    handler.validate_uid_uniqueness = Mock(
        side_effect=DuplicateUIDError("Duplicate UID")
    )
    
    result = handler.process_issue_updates(issue_number)
    
    assert result is None
    mock_issue.edit.assert_called_once_with(state="closed")

def test_process_issue_updates_with_unique_uid(handler):
    """Test processing continues for issue with unique UID"""
    issue_number = 123
    mock_issue = Mock(
        number=issue_number,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        body='{"test": "data"}'
    )
    handler.repo.get_issue.return_value = mock_issue
    
    # Mock successful validation
    handler.get_object_id_from_labels = Mock(return_value="test-123")
    handler.validate_uid_uniqueness = Mock()  # Won't raise error
    
    result = handler.process_issue_updates(issue_number)
    
    assert result is not None
    assert result.data == {"test": "data"}
    handler.validate_uid_uniqueness.assert_called_once_with("test-123")

def test_process_issue_updates_with_invalid_labels(handler):
    """Test processing skips issue with invalid labels"""
    issue_number = 123
    mock_issue = Mock(number=issue_number)
    handler.repo.get_issue.return_value = mock_issue
    
    # Mock get_object_id_from_labels to raise ValueError
    handler.get_object_id_from_labels = Mock(
        side_effect=ValueError("Invalid labels")
    )
    
    result = handler.process_issue_updates(issue_number)
    
    assert result is None
    # Should not try to close issue in this case
    mock_issue.edit.assert_not_called()

# tests/unit/test_store.py

def test_process_updates_skips_duplicate_uid(store):
    """Test store skips updates for issues with duplicate UID"""
    issue_number = 123
    
    # Mock issue handler to return None (skipped issue)
    store.issue_handler.process_issue_updates = Mock(return_value=None)
    
    result = store.process_updates(issue_number)
    
    assert result is None
    # Verify no updates were processed
    store.comment_handler.get_unprocessed_updates.assert_not_called()
    store.comment_handler.mark_processed.assert_not_called()

def test_process_updates_handles_valid_issue(store):
    """Test store processes updates for valid issue"""
    issue_number = 123
    mock_obj = Mock()
    mock_updates = [Mock()]
    
    store.issue_handler.process_issue_updates = Mock(return_value=mock_obj)
    store.comment_handler.get_unprocessed_updates = Mock(return_value=mock_updates)
    store.comment_handler.apply_update = Mock(return_value=mock_obj)
    
    result = store.process_updates(issue_number)
    
    assert result == mock_obj
    store.comment_handler.mark_processed.assert_called_once_with(
        issue_number, mock_updates
    )
