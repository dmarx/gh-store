# tests/unit/conftest.py

import pytest
from unittest.mock import Mock, patch
import json

@pytest.fixture
def mock_owner():
    """Create a mock repository owner"""
    owner = Mock()
    owner.login = "repo-owner"
    owner.type = "User"
    yield owner

@pytest.fixture
def mock_repo(mock_owner):
    """Create a mock repository with basic functionality"""
    repo = Mock()
    repo.get_owner.return_value = mock_owner
    yield repo

@pytest.fixture
def mock_config():
    """Create a mock store configuration"""
    config = Mock(
        store=Mock(
            base_label="stored-object",
            uid_prefix="UID:",
            reactions=Mock(
                processed="+1",
                initial_state="rocket"
            ),
            retries=Mock(
                max_attempts=3,
                backoff_factor=2
            ),
            rate_limit=Mock(
                max_requests_per_hour=1000
            ),
            log=Mock(
                level="INFO",
                format="{time} | {level} | {message}"
            )
        )
    )
    yield config

@pytest.fixture
def mock_comment():
    """Create a mock comment with configurable attributes"""
    comments = []  # Keep track of created comments for cleanup
    
    def _make_comment(user_login="repo-owner", body=None, comment_id=1, reactions=None):
        comment = Mock()
        comment.user = Mock(login=user_login)
        comment.id = comment_id
        comment.body = json.dumps(body) if body else "{}"
        comment.get_reactions.return_value = reactions or []
        comment.create_reaction = Mock()
        comments.append(comment)  # Track the comment
        return comment
    
    yield _make_comment
    
    # Cleanup
    for comment in comments:
        comment.reset_mock()

@pytest.fixture
def mock_issue(mock_comment):
    """Create a mock issue with configurable attributes"""
    issues = []  # Keep track of created issues for cleanup
    
    def _make_issue(number=1, user_login="repo-owner", body=None, comments=None):
        issue = Mock()
        issue.number = number
        issue.user = Mock(login=user_login)
        issue.body = json.dumps(body) if body else "{}"
        issue.get_comments = Mock(return_value=comments if comments is not None else [])
        issue.edit = Mock()  # For closing the issue
        issues.append(issue)  # Track the issue
        return issue
    
    yield _make_issue
    
    # Cleanup
    for issue in issues:
        issue.reset_mock()

# @pytest.fixture
# def store(mock_repo, mock_config):
#     """Create a GitHubStore instance with mocked components"""
#     patches = []
#     try:
#         # Create all patches
#         github_patch = patch('gh_store.core.store.Github')
#         path_patch = patch('pathlib.Path.exists', return_value=False)
#         resources_patch = patch('importlib.resources.files')
        
#         # Start all patches
#         mock_github = github_patch.start()
#         path_patch.start()
#         resources_patch.start()
        
#         # Track patches for cleanup
#         patches.extend([github_patch, path_patch, resources_patch])
        
#         # Set up store
#         mock_github.return_value.get_repo.return_value = mock_repo
        
#         from gh_store.core.store import GitHubStore
#         store = GitHubStore(token="fake-token", repo="owner/repo")
#         store.repo = mock_repo
#         store.config = mock_config
        
#         yield store
        
#     finally:
#         # Clean up all patches
#         for p in patches:
#             p.stop()

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
