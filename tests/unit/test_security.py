# tests/unit/test_security.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch
from github import GithubException

from gh_store.core.access import AccessControl
from gh_store.core.exceptions import AccessDeniedError
from gh_store.core.version import CLIENT_VERSION

# Authorization Tests

def test_owner_always_authorized(mock_github):
    """Test that repository owner is always authorized regardless of CODEOWNERS"""
    _, mock_repo = mock_github
    
    # Override get_contents to return no CODEOWNERS
    mock_repo.get_contents = Mock(side_effect=GithubException(404, "Not found"))
    
    ac = AccessControl(mock_repo)
    assert ac._is_authorized("repo-owner") is True

def test_codeowners_authorization(mock_github):
    """Test authorization via CODEOWNERS file"""
    _, mock_repo = mock_github
    
    # Override CODEOWNERS content
    mock_content = Mock()
    mock_content.decoded_content = b"* @maintainer @contributor"
    mock_repo.get_contents = Mock(return_value=mock_content)
    
    ac = AccessControl(mock_repo)
    assert ac._is_authorized("maintainer") is True
    assert ac._is_authorized("contributor") is True
    assert ac._is_authorized("random-user") is False

def test_organization_ownership(mock_github):
    """Test authorization with organization ownership"""
    _, mock_repo = mock_github
    
    # Override owner type
    owner = Mock()
    owner.login = "org-name"
    owner.type = "Organization"
    mock_repo.owner = owner
    
    ac = AccessControl(mock_repo)
    owner_info = ac._get_owner_info()
    
    assert owner_info["login"] == "org-name"
    assert owner_info["type"] == "Organization"
    assert ac._is_authorized("org-name") is True

def test_codeowners_file_locations(mock_github):
    """Test CODEOWNERS file location precedence"""
    _, mock_repo = mock_github
    
    for test_path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
        mock_content = Mock()
        mock_content.decoded_content = b"* @authorized-user"
        
        def get_contents_side_effect(path):
            if path == test_path:
                return mock_content
            raise GithubException(404, "Not found")
        
        mock_repo.get_contents = Mock(side_effect=get_contents_side_effect)
        ac = AccessControl(mock_repo)
        
        assert ac._is_authorized("authorized-user") is True

# Update Authorization Tests

def test_unauthorized_update_rejection(store, mock_comment):
    """Test that updates from unauthorized users are rejected"""
    unauthorized_update = mock_comment(
        user_login="attacker",
        body={
            '_data': {'malicious': 'update'},
            '_meta': {
                'client_version': CLIENT_VERSION,
                'timestamp': '2025-01-01T00:00:00Z',
                'update_mode': 'append'
            }
        }
    )
    authorized_update = mock_comment(
        user_login="repo-owner",
        body={
            '_data': {'valid': 'update'},
            '_meta': {
                'client_version': CLIENT_VERSION,
                'timestamp': '2025-01-01T00:00:00Z',
                'update_mode': 'append'
            }
        }
    )
    
    # Mock issue with both comments
    issue = Mock()
    issue.get_comments = Mock(return_value=[unauthorized_update, authorized_update])
    store.repo.get_issue.return_value = issue
    
    # Process updates
    updates = store.comment_handler.get_unprocessed_updates(123)
    
    # Only authorized update should be processed
    assert len(updates) == 1
    assert updates[0].changes == {'valid': 'update'}

def test_unauthorized_issue_creator_denied(store, mock_issue):
    """Test that updates are blocked for issues created by unauthorized users"""
    issue = mock_issue(
        user_login="infiltrator"
    )
    store.repo.get_issue.return_value = issue
    
    with pytest.raises(AccessDeniedError):
        store.process_updates(456)

def test_authorized_codeowners_updates(store, mock_comment, mock_github):
    """Test that CODEOWNERS team members can make updates"""
    _, mock_repo = mock_github
    
    # Set up CODEOWNERS authorization
    mock_content = Mock()
    mock_content.decoded_content = b"* @team-member"
    mock_repo.get_contents = Mock(return_value=mock_content)
    
    team_update = mock_comment(
        user_login="team-member",
        body={
            '_data': {'team': 'update'},
            '_meta': {
                'client_version': CLIENT_VERSION,
                'timestamp': '2025-01-01T00:00:00Z',
                'update_mode': 'append'
            }
        }
    )
    
    # Mock issue with team member's update
    issue = mock_issue(
        user_login="repo-owner",
        comments=[team_update]
    )
    store.repo.get_issue.return_value = issue
    
    # Process updates
    updates = store.comment_handler.get_unprocessed_updates(123)
    
    # Team member's update should be processed
    assert len(updates) == 1
    assert updates[0].changes == {'team': 'update'}

def test_metadata_tampering_protection(store, mock_comment, mock_issue):
    """Test protection against metadata tampering in updates"""
    tampered_update = mock_comment(
        user_login="repo-owner",
        body={
            '_data': {'update': 'data'},
            '_meta': {
                # Missing required fields
                'client_version': CLIENT_VERSION
            }
        }
    )
    
    issue = mock_issue(
        comments=[tampered_update]
    )
    store.repo.get_issue.return_value = issue
    
    # Process updates
    updates = store.comment_handler.get_unprocessed_updates(123)
    
    # Update with invalid metadata should be rejected
    assert len(updates) == 0

def test_reaction_based_processing_protection(store, mock_comment, mock_issue):
    """Test that processed updates cannot be reprocessed"""
    processed_update = mock_comment(
        user_login="repo-owner",
        body={
            '_data': {'already': 'processed'},
            '_meta': {
                'client_version': CLIENT_VERSION,
                'timestamp': '2025-01-01T00:00:00Z',
                'update_mode': 'append'
            }
        },
        reactions=[Mock(content="+1")]
    )
    
    issue = mock_issue(
        comments=[processed_update]
    )
    store.repo.get_issue.return_value = issue
    
    # Try to process updates
    updates = store.comment_handler.get_unprocessed_updates(123)
    
    # Already processed update should be skipped
    assert len(updates) == 0
