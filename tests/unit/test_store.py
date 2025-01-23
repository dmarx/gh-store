# tests/unit/test_store.py

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from unittest.mock import Mock, patch, mock_open

from gh_store.core.store import GitHubStore
from gh_store.core.exceptions import ObjectNotFound, ConcurrentUpdateError

@pytest.fixture
def store():
    """Create a store instance with a mocked GitHub repo"""
    with patch('gh_store.core.store.Github') as mock_github:
        mock_repo = Mock()
        mock_github.return_value.get_repo.return_value = mock_repo
        
        # Mock the default config
        mock_config = """
store:
  base_label: "stored-object"
  uid_prefix: "UID:"
  reactions:
    processed: "+1"
    initial_state: "🔰"
  retries:
    max_attempts: 3
    backoff_factor: 2
  rate_limit:
    max_requests_per_hour: 1000
  log:
    level: "INFO"
    format: "{time} | {level} | {message}"
"""
        with patch('pathlib.Path.exists', return_value=False), \
             patch('importlib.resources.files') as mock_files:
            mock_files.return_value.joinpath.return_value.open.return_value = mock_open(read_data=mock_config)()
            
            store = GitHubStore(token="fake-token", repo="owner/repo")
            store.repo = mock_repo  # Attach for test access
            return store

def test_create_object_with_initial_state(store):
    """Test that creating an object stores the initial state in a comment"""
    # Setup
    object_id = "test-123"
    test_data = {"name": "test", "value": 42}
    uid_label = f"{store.config.store.uid_prefix}{object_id}"
    
    # Mock existing labels
    mock_base_label = Mock()
    mock_base_label.name = "stored-object"
    store.repo.get_labels.return_value = [mock_base_label]
    
    # Mock issue and comment creation
    mock_issue = Mock()
    mock_comment = Mock()
    store.repo.create_issue.return_value = mock_issue
    mock_issue.create_comment.return_value = mock_comment
    
    # Set up other required mock attributes
    mock_issue.created_at = datetime.now(ZoneInfo("UTC"))
    mock_issue.updated_at = datetime.now(ZoneInfo("UTC"))
    mock_issue.get_comments = Mock(return_value=[])
    
    # Create object
    obj = store.create(object_id, test_data)
    
    # Verify initial state comment was created
    mock_issue.create_comment.assert_called_once()
    comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
    assert comment_data["type"] == "initial_state"
    assert comment_data["data"] == test_data
    
    # Verify comment was marked as processed and initial state
    mock_comment.create_reaction.assert_any_call(store.config.store.reactions.processed)
    mock_comment.create_reaction.assert_any_call(store.config.store.reactions.initial_state)
    
    # Verify label creation
    store.repo.create_label.assert_called_once_with(
        name=uid_label,
        color="0366d6"
    )

def test_get_object(store):
    """Test retrieving an object"""
    # Setup
    test_data = {"name": "test", "value": 42}
    
    # Mock labels
    stored_label = Mock()
    stored_label.name = "stored-object"
    store.repo.get_labels.return_value = [stored_label]
    
    mock_issue = Mock()
    mock_issue.body = json.dumps(test_data)
    mock_issue.get_comments = Mock(return_value=[])  # Return empty list of comments
    mock_issue.created_at = datetime.now(ZoneInfo("UTC"))
    mock_issue.updated_at = datetime.now(ZoneInfo("UTC"))
    store.repo.get_issues.return_value = [mock_issue]
    
    # Test
    obj = store.get("test-obj")
    
    # Verify
    assert obj.data == test_data
    store.repo.get_issues.assert_called_once()

def test_get_nonexistent_object(store):
    """Test getting an object that doesn't exist"""
    store.repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.get("nonexistent")

def test_process_update(store):
    """Test processing an update"""
    # Setup initial state
    test_data = {"name": "test", "value": 42}
    mock_issue = Mock()
    mock_issue.body = json.dumps(test_data)
    mock_issue.get_comments = Mock(return_value=[])
    mock_issue.number = 123
    
    # Handle different query states
    def get_issues_side_effect(**kwargs):
        if kwargs.get("state") == "open":
            return []  # No issues being processed
        return [mock_issue]
    
    store.repo.get_issues.side_effect = get_issues_side_effect
    store.repo.get_issue.return_value = mock_issue
    
    # Test update by adding a comment
    update_data = {"value": 43}
    store.update("test-obj", update_data)
    
    # Basic verification
    mock_issue.create_comment.assert_called_once()  # Comment created with update data
    comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
    assert comment_data == update_data
    mock_issue.edit.assert_called_with(state="open")  # Issue reopened to trigger processing

def test_create_object_ensures_labels_exist(store):
    """Test that create_object creates any missing labels"""
    # Setup
    object_id = "test-123"
    test_data = {"name": "test", "value": 42}
    uid_label = f"{store.config.store.uid_prefix}{object_id}"  # Get expected label with prefix
    
    # Mock existing labels
    mock_label = Mock()
    mock_label.name = "stored-object"
    store.repo.get_labels.return_value = [mock_label]  # Only base label exists
    
    mock_issue = Mock()
    store.repo.create_issue.return_value = mock_issue
    
    # Test
    store.create(object_id, test_data)
    
    # Verify label creation with UID prefix
    store.repo.create_label.assert_called_once_with(
        name=uid_label,  # Should include prefix
        color="0366d6"
    )
    
    # Verify issue creation with both labels
    store.repo.create_issue.assert_called_once()
    call_kwargs = store.repo.create_issue.call_args[1]
    assert call_kwargs["labels"] == ["stored-object", uid_label]


def test_get_object_history_complete(store):
    """Test retrieving complete object history including initial state"""
    # Setup
    object_id = "test-123"
    initial_data = {"name": "test", "value": 42}
    update1_data = {"value": 43}
    update2_data = {"value": 44}
    
    # Create mock issue with history
    mock_issue = Mock()
    mock_issue.created_at = datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC"))
    
    # Create mock comments for initial state and updates
    mock_comments = []
    
    # Initial state comment
    initial_comment = Mock()
    initial_comment.body = json.dumps({
        "type": "initial_state",
        "data": initial_data,
        "timestamp": "2025-01-01T00:00:00Z"
    })
    initial_comment.created_at = datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC"))
    initial_comment.id = 1
    mock_comments.append(initial_comment)
    
    # Update comments
    update1_comment = Mock()
    update1_comment.body = json.dumps(update1_data)
    update1_comment.created_at = datetime(2025, 1, 2, tzinfo=ZoneInfo("UTC"))
    update1_comment.id = 2
    mock_comments.append(update1_comment)
    
    update2_comment = Mock()
    update2_comment.body = json.dumps(update2_data)
    update2_comment.created_at = datetime(2025, 1, 3, tzinfo=ZoneInfo("UTC"))
    update2_comment.id = 3
    mock_comments.append(update2_comment)
    
    mock_issue.get_comments = Mock(return_value=mock_comments)
    store.repo.get_issues.return_value = [mock_issue]
    
    # Test
    history = store.issue_handler.get_object_history(object_id)
    
    # Verify
    assert len(history) == 3
    
    # Check initial state
    assert history[0]["type"] == "initial_state"
    assert history[0]["data"] == initial_data
    assert history[0]["comment_id"] == 1
    
    # Check updates
    assert history[1]["type"] == "update"
    assert history[1]["data"] == update1_data
    assert history[1]["comment_id"] == 2
    
    assert history[2]["type"] == "update"
    assert history[2]["data"] == update2_data
    assert history[2]["comment_id"] == 3

def test_get_object_history_legacy(store):
    """Test retrieving history for legacy objects without initial state comment"""
    # Setup
    object_id = "test-123"
    update_data = {"value": 43}
    
    # Create mock issue with only update comments
    mock_issue = Mock()
    mock_issue.created_at = datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC"))
    
    # Create mock update comment
    update_comment = Mock()
    update_comment.body = json.dumps(update_data)
    update_comment.created_at = datetime(2025, 1, 2, tzinfo=ZoneInfo("UTC"))
    update_comment.id = 1
    
    mock_issue.get_comments = Mock(return_value=[update_comment])
    store.repo.get_issues.return_value = [mock_issue]
    
    # Test
    history = store.issue_handler.get_object_history(object_id)
    
    # Verify
    assert len(history) == 1
    assert history[0]["type"] == "update"
    assert history[0]["data"] == update_data
    assert history[0]["comment_id"] == 1

def test_get_object_history_invalid_comment(store):
    """Test handling invalid JSON in comments when retrieving history"""
    # Setup
    object_id = "test-123"
    
    # Create mock issue with invalid comment
    mock_issue = Mock()
    invalid_comment = Mock()
    invalid_comment.body = "This is not JSON"
    invalid_comment.id = 1
    
    mock_issue.get_comments = Mock(return_value=[invalid_comment])
    store.repo.get_issues.return_value = [mock_issue]
    
    # Test
    history = store.issue_handler.get_object_history(object_id)
    
    # Verify
    assert len(history) == 0  # Invalid comment should be skipped

def test_get_object_history_nonexistent(store):
    """Test retrieving history for nonexistent object"""
    # Setup
    store.repo.get_issues.return_value = []
    
    # Test and verify
    with pytest.raises(ObjectNotFound):
        store.issue_handler.get_object_history("nonexistent")

def test_concurrent_update_prevention(store):
    """Test that concurrent updates are prevented"""
    # Setup - mock an open issue to simulate ongoing processing
    mock_issue = Mock()
    
    def get_issues_side_effect(**kwargs):
        if kwargs.get("state") == "open":
            return [mock_issue]  # Return open issue to simulate processing
        return []
    
    store.repo.get_issues.side_effect = get_issues_side_effect
    
    # Test
    with pytest.raises(ConcurrentUpdateError):
        store.update("test-obj", {"value": 43})

def test_list_updated_since(store):
    """Test fetching objects updated since timestamp"""
    # Setup
    timestamp = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
    object_id = "test-123"
    uid_label = f"{store.config.store.uid_prefix}{object_id}"
    
    # Create properly configured mock labels
    stored_label = Mock()
    stored_label.name = "stored-object"
    uid_mock_label = Mock()
    uid_mock_label.name = uid_label
    
    # Mock get_labels for label creation check
    store.repo.get_labels.return_value = [stored_label]
    
    mock_issue = Mock()
    mock_issue.labels = [stored_label, uid_mock_label]
    mock_issue.number = 1
    mock_issue.created_at = timestamp - timedelta(minutes=30)
    mock_issue.updated_at = timestamp + timedelta(minutes=30)
    
    store.repo.get_issues.return_value = [mock_issue]
    
    # Mock the object retrieval
    mock_obj = Mock()
    mock_obj.meta.updated_at = timestamp + timedelta(minutes=30)
    
    # Mock the get_object_by_number method
    store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    
    # Test
    updated = store.list_updated_since(timestamp)
    
    # Verify
    store.repo.get_issues.assert_called_once()
    call_kwargs = store.repo.get_issues.call_args[1]
    assert call_kwargs["since"] == timestamp
    assert object_id in updated
    assert len(updated) == 1
    assert updated[object_id] == mock_obj

def test_list_updated_since_no_updates(store):
    """Test when no updates since timestamp"""
    # Setup
    timestamp = datetime.now(ZoneInfo("UTC")) - timedelta(hours=1)
    object_id = "test-123"
    uid_label = f"{store.config.store.uid_prefix}{object_id}"
    
    # Create properly configured mock labels
    stored_label = Mock()
    stored_label.name = "stored-object"
    uid_mock_label = Mock()
    uid_mock_label.name = uid_label
    
    # Mock get_labels for label creation check
    store.repo.get_labels.return_value = [stored_label]
    
    mock_issue = Mock()
    mock_issue.labels = [stored_label, uid_mock_label]
    mock_issue.number = 1
    mock_issue.created_at = timestamp - timedelta(minutes=30)
    mock_issue.updated_at = timestamp - timedelta(minutes=30)  # Updated before timestamp
    
    store.repo.get_issues.return_value = [mock_issue]
    
    # Mock the object retrieval
    mock_obj = Mock()
    mock_obj.meta.updated_at = timestamp - timedelta(minutes=30)
    
    # Mock the get_object_by_number method
    store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    
    # Test
    updated = store.list_updated_since(timestamp)
    
    # Verify
    assert len(updated) == 0
