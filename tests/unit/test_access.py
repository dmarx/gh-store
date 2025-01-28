# tests/unit/test_access.py

from unittest.mock import Mock, patch
import pytest
from gh_store.core.access import AccessControl


# tests/unit/test_store.py

import pytest
from unittest.mock import Mock, patch
from gh_store.core.exceptions import AccessDeniedError
from gh_store.core.store import GitHubStore

@pytest.fixture
def mock_github():
    with patch('gh_store.core.store.Github') as mock:
        mock_repo = mock.return_value.get_repo.return_value
        yield mock, mock_repo

@pytest.fixture
def store(mock_github):
    _, mock_repo = mock_github
    
    # Mock the default config
    mock_config = """
    store:
        base_label: "stored-object"
        uid_prefix: "UID:"
        reactions:
            processed: "+1"
            initial_state: "rocket"
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
        store.repo = mock_repo
        return store


@pytest.fixture
def mock_repo():
    """Create a mock repository"""
    repo = Mock()
    # Mock the owner with a simple response
    owner = Mock()
    owner.login = "repo-owner"
    owner.type = "User"
    repo.get_owner.return_value = owner
    return repo

@pytest.fixture
def access_control(mock_repo):
    """Create AccessControl instance with mocked repo"""
    return AccessControl(mock_repo)

def test_owner_info_caching(access_control, mock_repo):
    """Test that owner info is cached after first retrieval"""
    # First call should hit the API
    info1 = access_control._get_owner_info()
    assert mock_repo.get_owner.call_count == 1
    assert info1['login'] == "repo-owner"
    
    # Second call should use cache
    info2 = access_control._get_owner_info()
    assert mock_repo.get_owner.call_count == 1  # No additional calls
    assert info2['login'] == "repo-owner"

def test_clear_cache(access_control):
    """Test that clear_cache resets cached data"""
    # Prime the cache
    access_control._owner_info = {"login": "cached-owner", "type": "User"}
    access_control._codeowners = {"user1", "user2"}
    
    # Clear cache
    access_control.clear_cache()
    
    # Verify cache is cleared
    assert access_control._owner_info is None
    assert access_control._codeowners is None

def test_parse_basic_codeowners(mock_repo):
    """Test parsing basic CODEOWNERS content"""
    codeowners_content = """
    # Comment line
    * @global-owner
    
    /docs/ @doc-owner
    /src/ @dev1 @dev2
    """.encode('utf-8')
    
    # Mock the get_contents response
    content = Mock()
    content.decoded_content = codeowners_content
    mock_repo.get_contents.return_value = content
    
    ac = AccessControl(mock_repo)
    codeowners = ac._get_codeowners()
    
    expected = {"global-owner", "doc-owner", "dev1", "dev2"}
    assert codeowners == expected

def test_validate_issue_creator_owner(access_control):
    """Test that repo owner can create issues"""
    issue = Mock()
    issue.user.login = "repo-owner"  # Matches mock_repo owner
    
    result = access_control.validate_issue_creator(issue)
    assert result is True

def test_validate_issue_creator_unauthorized(access_control):
    """Test that unauthorized users cannot create issues"""
    issue = Mock()
    issue.user.login = "random-user"
    issue.number = 123
    
    result = access_control.validate_issue_creator(issue)
    assert result is False

def test_validate_comment_author_owner(access_control):
    """Test that repo owner can add comments"""
    comment = Mock()
    comment.user.login = "repo-owner"  # Matches mock_repo owner
    comment.id = 456
    
    result = access_control.validate_comment_author(comment)
    assert result is True

def test_validate_comment_author_unauthorized(access_control):
    """Test that unauthorized users cannot add comments"""
    comment = Mock()
    comment.user.login = "random-user"
    comment.id = 456
    
    result = access_control.validate_comment_author(comment)
    assert result is False

def test_validate_missing_user(access_control):
    """Test handling of missing user information"""
    # Test with no user on issue
    issue = Mock()
    issue.user = None
    issue.number = 123
    assert access_control.validate_issue_creator(issue) is False
    
    # Test with no user on comment
    comment = Mock()
    comment.user = None
    comment.id = 456
    assert access_control.validate_comment_author(comment) is False

def test_parse_empty_codeowners(mock_repo):
    """Test parsing empty CODEOWNERS file"""
    # Mock empty CODEOWNERS file
    content = Mock()
    content.decoded_content = "".encode('utf-8')
    mock_repo.get_contents.return_value = content
    
    ac = AccessControl(mock_repo)
    codeowners = ac._get_codeowners()
    
    assert codeowners == set()  # Should be empty set

def test_parse_comments_only_codeowners(mock_repo):
    """Test parsing CODEOWNERS file with only comments"""
    codeowners_content = """
    # This is a comment
    # Another comment
    
    # Final comment
    """.encode('utf-8')
    
    content = Mock()
    content.decoded_content = codeowners_content
    mock_repo.get_contents.return_value = content
    
    ac = AccessControl(mock_repo)
    codeowners = ac._get_codeowners()
    
    assert codeowners == set()  # Should be empty set


async def test_process_updates_access_denied(store):
    """Test that process_updates enforces access control"""
    # Mock access control to deny access
    store.access_control.validate_update_request = Mock(return_value=False)
    
    with pytest.raises(AccessDeniedError) as exc:
        await store.process_updates(123)
    
    assert "Updates can only be processed" in str(exc.value)
    assert store.access_control.validate_update_request.called

async def test_process_updates_access_granted(store):
    """Test that process_updates allows access for authorized users"""
    # Mock access control to allow access
    store.access_control.validate_update_request = Mock(return_value=True)
    
    # Mock the update processing
    mock_obj = Mock()
    store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
    store.comment_handler.get_unprocessed_updates = Mock(return_value=[])
    
    result = await store.process_updates(123)
    
    assert result == mock_obj
    assert store.access_control.validate_update_request.called
