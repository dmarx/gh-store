# tests/unit/test_comment_handler.py

import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from gh_store.handlers.comment import CommentHandler
from gh_store.core.version import CLIENT_VERSION

@pytest.fixture
def mock_repo():
    return Mock()

@pytest.fixture
def mock_config():
    return Mock(
        store=Mock(
            reactions=Mock(
                processed="+1",
                initial_state="rocket"
            )
        )
    )

@pytest.fixture
def comment_handler(mock_repo, mock_config):
    return CommentHandler(mock_repo, mock_config)

def test_get_unprocessed_updates_mixed_comments(comment_handler, mock_repo):
    """Test processing a mix of valid and invalid comments"""
    
    # Setup mock issue with various types of comments
    issue = Mock()
    mock_repo.get_issue.return_value = issue
    
    # Create a variety of comments to test filtering
    comments = [
        # Valid update with metadata from authorized user
        Mock(
            id=1,
            body=json.dumps({
                '_data': {'update': 'valid'},
                '_meta': {
                    'client_version': CLIENT_VERSION,
                    'timestamp': '2025-01-01T00:00:00Z',
                    'update_mode': 'append'
                }
            }),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[])  # No reactions = unprocessed
        ),
        
        # Already processed update (should be skipped)
        Mock(
            id=2,
            body=json.dumps({
                '_data': {'update': 'processed'},
                '_meta': {
                    'client_version': CLIENT_VERSION,
                    'timestamp': '2025-01-01T00:00:00Z',
                    'update_mode': 'append'
                }
            }),
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[Mock(content="+1")])
        ),
        
        # Legacy format comment (should be handled with generated metadata)
        Mock(
            id=3,
            body='{"legacy": "update"}',
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[])
        ),
        
        # Initial state comment (should be skipped)
        Mock(
            id=4,
            body=json.dumps({
                'type': 'initial_state',
                '_data': {'initial': 'state'},
                '_meta': {
                    'client_version': CLIENT_VERSION,
                    'timestamp': '2025-01-01T00:00:00Z',
                    'update_mode': 'append'
                }
            }),
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[])
        ),
        
        # Invalid JSON comment (should be skipped)
        Mock(
            id=5,
            body='not json',
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[])
        ),
        
        # Valid JSON but unauthorized user (should be skipped)
        Mock(
            id=6,
            body=json.dumps({
                '_data': {'update': 'unauthorized'},
                '_meta': {
                    'client_version': CLIENT_VERSION,
                    'timestamp': '2025-01-02T00:00:00Z',
                    'update_mode': 'append'
                }
            }),
            created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            user=Mock(login="random-user"),
            get_reactions=Mock(return_value=[])
        ),
        
        # Regular discussion comment (should be skipped)
        Mock(
            id=7,
            body='Just a regular comment',
            user=Mock(login="random-user"),
            get_reactions=Mock(return_value=[])
        )
    ]
    
    issue.get_comments.return_value = comments
    
    # Mock the access control to only authorize "owner"
    comment_handler.access_control._get_owner_info = Mock(
        return_value={"login": "owner", "type": "User"}
    )
    comment_handler.access_control._find_codeowners_file = Mock(return_value=None)
    
    # Get unprocessed updates
    updates = comment_handler.get_unprocessed_updates(123)
    
    # Should get two valid updates (new format and legacy format)
    assert len(updates) == 2
    assert updates[0].comment_id == 1
    assert updates[0].changes == {'update': 'valid'}
    assert updates[1].comment_id == 3
    assert updates[1].changes == {'legacy': 'update'}

def test_get_unprocessed_updates_unauthorized_json(comment_handler, mock_repo):
    """Test that valid JSON updates from unauthorized users are skipped"""
    issue = Mock()
    mock_repo.get_issue.return_value = issue
    
    # Create an unauthorized but valid JSON update
    comment = Mock(
        id=1,
        body=json.dumps({
            '_data': {'malicious': 'update'},
            '_meta': {
                'client_version': CLIENT_VERSION,
                'timestamp': '2025-01-01T00:00:00Z',
                'update_mode': 'append'
            }
        }),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        user=Mock(login="attacker"),
        get_reactions=Mock(return_value=[])
    )
    
    issue.get_comments.return_value = [comment]
    
    # Mock access control to reject the user
    comment_handler.access_control._get_owner_info = Mock(
        return_value={"login": "owner", "type": "User"}
    )
    comment_handler.access_control._find_codeowners_file = Mock(return_value=None)
    
    updates = comment_handler.get_unprocessed_updates(123)
    assert len(updates) == 0

def test_get_unprocessed_updates_with_codeowners(comment_handler, mock_repo):
    """Test processing updates with CODEOWNERS authorization"""
    issue = Mock()
    mock_repo.get_issue.return_value = issue
    
    # Create comments from different users
    comments = [
        # From CODEOWNERS team member
        Mock(
            id=1,
            body=json.dumps({
                '_data': {'update': 'from-team'},
                '_meta': {
                    'client_version': CLIENT_VERSION,
                    'timestamp': '2025-01-01T00:00:00Z',
                    'update_mode': 'append'
                }
            }),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            user=Mock(login="team-member"),
            get_reactions=Mock(return_value=[])
        ),
        # From unauthorized user
        Mock(
            id=2,
            body=json.dumps({
                '_data': {'update': 'unauthorized'},
                '_meta': {
                    'client_version': CLIENT_VERSION,
                    'timestamp': '2025-01-02T00:00:00Z',
                    'update_mode': 'append'
                }
            }),
            created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            user=Mock(login="random-user"),
            get_reactions=Mock(return_value=[])
        )
    ]
    
    issue.get_comments.return_value = comments
    
    # Mock CODEOWNERS to include team-member
    comment_handler.access_control._get_owner_info = Mock(
        return_value={"login": "owner", "type": "User"}
    )
    # Set up CODEOWNERS content
    codeowners_content = "* @team-member"
    comment_handler.access_control._find_codeowners_file = Mock(
        return_value=codeowners_content
    )
    
    updates = comment_handler.get_unprocessed_updates(123)
    
    # Should only get update from team member
    assert len(updates) == 1
    assert updates[0].comment_id == 1
    assert updates[0].changes == {'update': 'from-team'}

def test_get_unprocessed_updates_empty(comment_handler, mock_repo):
    """Test behavior with no comments"""
    issue = Mock()
    mock_repo.get_issue.return_value = issue
    issue.get_comments.return_value = []
    
    updates = comment_handler.get_unprocessed_updates(123)
    assert len(updates) == 0

def test_get_unprocessed_updates_all_processed(comment_handler, mock_repo):
    """Test behavior when all comments are already processed"""
    issue = Mock()
    mock_repo.get_issue.return_value = issue
    
    # Create some processed comments
    comments = [
        Mock(
            id=1,
            body=json.dumps({
                '_data': {'update': 'processed'},
                '_meta': {
                    'client_version': CLIENT_VERSION,
                    'timestamp': '2025-01-01T00:00:00Z',
                    'update_mode': 'append'
                }
            }),
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[Mock(content="+1")])
        ),
        Mock(
            id=2,
            body=json.dumps({
                '_data': {'another': 'processed'},
                '_meta': {
                    'client_version': CLIENT_VERSION,
                    'timestamp': '2025-01-01T00:00:00Z',
                    'update_mode': 'append'
                }
            }),
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[Mock(content="+1")])
        )
    ]
    
    issue.get_comments.return_value = comments
    
    updates = comment_handler.get_unprocessed_updates(123)
    assert len(updates) == 0

def test_create_comment_payload(comment_handler):
    """Test creation of properly structured comment payloads"""
    data = {'test': 'data'}
    
    # Test regular update payload
    update_payload = comment_handler.create_comment_payload(data)
    assert update_payload._data == data
    assert update_payload._meta.client_version == CLIENT_VERSION
    assert update_payload._meta.update_mode == 'append'
    assert update_payload.type is None
    
    # Test initial state payload
    initial_payload = comment_handler.create_comment_payload(data, 'initial_state')
    assert initial_payload._data == data
    assert initial_payload._meta.client_version == CLIENT_VERSION
    assert initial_payload._meta.update_mode == 'append'
    assert initial_payload.type == 'initial_state'

def test_get_unprocessed_updates_malformed_metadata(comment_handler, mock_repo):
    """Test handling of malformed metadata in comments"""
    issue = Mock()
    mock_repo.get_issue.return_value = issue
    
    # Create comment with malformed metadata
    malformed_comment = Mock(
        id=1,
        body=json.dumps({
            '_data': {'test': 'data'},
            '_meta': {
                # Missing required fields
                'client_version': CLIENT_VERSION
            }
        }),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        user=Mock(login="owner"),
        get_reactions=Mock(return_value=[])
    )
    
    issue.get_comments.return_value = [malformed_comment]
    
    # Mock access control
    comment_handler.access_control._get_owner_info = Mock(
        return_value={"login": "owner", "type": "User"}
    )
    comment_handler.access_control._find_codeowners_file = Mock(return_value=None)
    
    # Should skip malformed comment
    updates = comment_handler.get_unprocessed_updates(123)
    assert len(updates) == 0

def test_apply_update_preserves_metadata(comment_handler):
    """Test that applying updates preserves any existing metadata"""
    # Create mock object with existing metadata
    obj = Mock()
    obj.meta = Mock(object_id='test-123')
    obj.data = {
        'value': 1,
        '_meta': {
            'some': 'metadata'
        }
    }
    
    # Create update that includes metadata
    update = Mock(
        comment_id=1,
        timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
        changes={
            'value': 2,
            '_meta': {
                'new': 'metadata'
            }
        }
    )
    
    # Apply update
    result = comment_handler.apply_update(obj, update)
    
    # Verify metadata was updated correctly
    assert result.data['value'] == 2
    assert result.data['_meta']['some'] == 'metadata'
    assert result.data['_meta']['new'] == 'metadata'
