# tests/unit/conftest.py

from datetime import datetime, timezone
import json, os
from pathlib import Path
import pytest
from unittest.mock import Mock, mock_open, patch
from github import GithubException
from omegaconf import OmegaConf

from gh_store.core.store import GitHubStore

# Base test data
DEFAULT_TIMESTAMP = datetime(2025, 1, 1, tzinfo=timezone.utc)
UPDATE_TIMESTAMP = datetime(2025, 1, 2, tzinfo=timezone.utc)

@pytest.fixture
def default_config():
    """Create a consistent default config for testing"""
    return OmegaConf.create({
        "store": {
            "base_label": "stored-object",
            "uid_prefix": "UID:",
            "reactions": {
                "processed": "+1",
                "initial_state": "rocket"
            },
            "retries": {
                "max_attempts": 3,
                "backoff_factor": 2
            },
            "rate_limit": {
                "max_requests_per_hour": 1000
            },
            "log": {
                "level": "INFO",
                "format": "{time} | {level} | {message}"
            }
        }
    })

@pytest.fixture
def mock_label_factory():
    """Create GitHub-style label objects"""
    def create_label(name: str):
        label = Mock()
        label.name = name
        return label
    return create_label

@pytest.fixture
def mock_comment():
    """Create a mock comment with GitHub-like structure"""
    comments = []
    
    def _make_comment(
        user_login="repo-owner", 
        body=None, 
        comment_id=1, 
        reactions=None,
        created_at=None
    ):
        comment = Mock()
        # Set up user properly
        user = Mock()
        user.login = user_login
        comment.user = user
        
        # Handle body serialization
        comment.body = json.dumps(body) if body else "{}"
        comment.id = comment_id
        
        # Set up reactions
        comment.get_reactions = Mock(return_value=reactions or [])
        comment.create_reaction = Mock()
        
        # Set timestamps
        comment.created_at = created_at or DEFAULT_TIMESTAMP
        
        comments.append(comment)
        return comment
    
    yield _make_comment
    
    for comment in comments:
        comment.reset_mock()

@pytest.fixture
def mock_issue(mock_label_factory):
    """Create a mock issue with complete GitHub-like structure"""
    issues = []
    
    def _make_issue(
        number=1, 
        user_login="repo-owner", 
        body=None, 
        comments=None, 
        labels=None,
        created_at=None,
        updated_at=None,
        state="closed"
    ):
        issue = Mock()
        
        # Set basic attributes
        issue.number = number
        issue.state = state
        
        # Set up user properly
        user = Mock()
        user.login = user_login
        issue.user = user
        
        # Handle body serialization
        issue.body = json.dumps(body) if body else "{}"
        
        # Set up comments
        issue.get_comments = Mock(return_value=comments or [])
        
        # Set up labels with factory
        default_labels = [
            mock_label_factory("stored-object"),
            mock_label_factory("UID:test-123")
        ]
        if isinstance(labels, list):
            issue.labels = [
                label if isinstance(label, Mock) else mock_label_factory(label)
                for label in labels
            ]
        else:
            issue.labels = default_labels
            
        # Set timestamps
        issue.created_at = created_at or DEFAULT_TIMESTAMP
        issue.updated_at = updated_at or UPDATE_TIMESTAMP
        
        # Set up methods
        issue.edit = Mock()
        issue.create_comment = Mock()
        
        issues.append(issue)
        return issue
    
    yield _make_issue
    
    for issue in issues:
        issue.reset_mock()

@pytest.fixture(autouse=True)
def mock_config():
    """Mock OmegaConf config loading"""
    with patch('omegaconf.OmegaConf.load') as mock_load:
        mock_load.return_value = OmegaConf.create({
            "store": {
                "base_label": "stored-object",
                "uid_prefix": "UID:",
                "reactions": {
                    "processed": "+1",
                    "initial_state": "rocket"
                },
                "retries": {
                    "max_attempts": 3,
                    "backoff_factor": 2
                },
                "rate_limit": {
                    "max_requests_per_hour": 1000
                },
                "log": {
                    "level": "INFO",
                    "format": "{time} | {level} | {message}"
                }
            }
        })
        yield mock_load

@pytest.fixture
def mock_github(mock_label_factory):
    """Create a mock Github instance with proper repo structure"""
    with patch('gh_store.core.store.Github') as mock_gh:
        mock_repo = Mock()
        
        # Set up owner
        owner = Mock()
        owner.login = "repo-owner"
        owner.type = "User"
        mock_repo.owner = owner
        
        # Set up labels
        mock_labels = [mock_label_factory("stored-object")]
        mock_repo.get_labels = Mock(return_value=mock_labels)
        
        def create_label(name, color="0366d6"):
            new_label = mock_label_factory(name)
            mock_labels.append(new_label)
            return new_label
        mock_repo.create_label = Mock(side_effect=create_label)
        
        # Set up CODEOWNERS
        mock_content = Mock()
        mock_content.decoded_content = b"* @repo-owner"
        def get_contents_side_effect(path):
            if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
                return mock_content
            raise GithubException(404, "Not found")
        mock_repo.get_contents = Mock(side_effect=get_contents_side_effect)
        
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo

@pytest.fixture
def store(mock_config, mock_github):
    """Create a GitHubStore instance with mocked dependencies"""
    _, mock_repo = mock_github
    store = GitHubStore(token="fake-token", repo="owner/repo")
    store.repo = mock_repo
    store.access_control.repo = mock_repo
    return store
