# tests/unit/test_comment_handler.py

import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from gh_store.handlers.comment import CommentHandler

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
        # Valid update from authorized user
        Mock(
            id=1,
            body='{"update": "valid"}',
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[])  # No reactions = unprocessed
        ),
        
        # Already processed update (should be skipped)
        Mock(
            id=2,
            body='{"update": "processed"}',
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[Mock(content="+1")])
        ),
        
        # Initial state comment (should be skipped)
        Mock(
            id=3,
            body=json.dumps({
                "type": "initial_state",
                "data": {"initial": "state"}
            }),
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[])
        ),
        
        # Invalid JSON comment (should be skipped)
        Mock(
            id=4,
            body='not json',
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[])
        ),
        
        # Valid JSON but unauthorized user (should be skipped)
        Mock(
            id=5,
            body='{"update": "unauthorized"}',
            created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            user=Mock(login="random-user"),
            get_reactions=Mock(return_value=[])
        ),
        
        # Regular discussion comment (should be skipped)
        Mock(
            id=6,
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
    
    # Should only get one valid update
    assert len(updates) == 1
    assert updates[0].comment_id == 1
    assert updates[0].changes == {"update": "valid"}

def test_get_unprocessed_updates_unauthorized_json(comment_handler, mock_repo):
    """Test that valid JSON updates from unauthorized users are skipped"""
    issue = Mock()
    mock_repo.get_issue.return_value = issue
    
    # Create an unauthorized but valid JSON update
    comment = Mock(
        id=1,
        body='{"malicious": "update"}',
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
            body='{"update": "from-team"}',
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            user=Mock(login="team-member"),
            get_reactions=Mock(return_value=[])
        ),
        # From unauthorized user
        Mock(
            id=2,
            body='{"update": "unauthorized"}',
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
    assert updates[0].changes == {"update": "from-team"}

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
            body='{"update": "processed"}',
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[Mock(content="+1")])
        ),
        Mock(
            id=2,
            body='{"another": "processed"}',
            user=Mock(login="owner"),
            get_reactions=Mock(return_value=[Mock(content="+1")])
        )
    ]
    
    issue.get_comments.return_value = comments
    
    updates = comment_handler.get_unprocessed_updates(123)
    assert len(updates) == 0
