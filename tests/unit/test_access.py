# tests/unit/test_access.py

import pytest
from unittest.mock import Mock, patch
from github import GithubException
from gh_store.core.access import AccessControl

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

def test_should_skip_line():
    """Test line skipping logic"""
    ac = AccessControl(Mock())
    
    assert ac._should_skip_line("")  # Empty line
    assert ac._should_skip_line("  ")  # Whitespace only
    assert ac._should_skip_line("# Comment")  # Comment
    assert ac._should_skip_line("  # Indented comment")  # Indented comment
    assert not ac._should_skip_line("* @user")  # Valid line
    assert not ac._should_skip_line("/path @user")  # Valid line with path

def test_extract_users_from_line():
    """Test extracting users from CODEOWNERS lines"""
    ac = AccessControl(Mock())
    
    # Basic user
    assert ac._extract_users_from_line("* @user1") == {"user1"}
    
    # Multiple users
    assert ac._extract_users_from_line("/path @user1 @user2") == {"user1", "user2"}
    
    # Mix of users and teams (teams handled separately)
    line = "/path @user1 @org/team1 @user2"
    users = ac._extract_users_from_line(line)
    assert "user1" in users
    assert "user2" in users
    
    # Ignore non-@ mentions
    assert ac._extract_users_from_line("/path user1 @user2") == {"user2"}
    
    # Path with spaces
    assert ac._extract_users_from_line("/path with spaces @user1") == {"user1"}

def test_get_team_members(mock_repo):
    """Test team membership resolution"""
    ac = AccessControl(mock_repo)
    
    # Mock team members
    team_members = [Mock(login="team-member-1"), Mock(login="team-member-2")]
    team = Mock()
    team.get_members.return_value = team_members
    
    # Mock organization and team lookup
    org = Mock()
    org.get_team_by_slug.return_value = team
    mock_repo.organization = org
    
    # Test successful team lookup
    members = ac._get_team_members("org/team")
    assert members == {"team-member-1", "team-member-2"}
    
    # Test failed team lookup
    org.get_team_by_slug.side_effect = GithubException(404, "Not found")
    members = ac._get_team_members("org/nonexistent")
    assert members == set()

def test_find_codeowners_file(mock_repo):
    """Test CODEOWNERS file location logic"""
    ac = AccessControl(mock_repo)
    
    # Test successful find
    content = Mock()
    content.decoded_content = b"* @user1"
    mock_repo.get_contents.return_value = content
    
    found = ac._find_codeowners_file()
    assert found == "* @user1"
    
    # Test no file found
    mock_repo.get_contents.side_effect = GithubException(404, "Not found")
    found = ac._find_codeowners_file()
    assert found is None

def test_parse_codeowners_content():
    """Test parsing complete CODEOWNERS file"""
    ac = AccessControl(Mock())
    
    content = """
    # Comment line
    * @global-owner
    
    # Docs team
    /docs/ @doc-owner
    
    # Multiple owners
    /src/ @dev1 @dev2
    
    # Team ownership
    /apps/ @org/team1
    
    # Mixed ownership
    /api/ @api-owner @org/api-team
    """
    
    # Mock team resolution
    ac._get_team_members = Mock(return_value={"team-member-1", "team-member-2"})
    
    users = ac._parse_codeowners_content(content)
    expected = {
        "global-owner", "doc-owner", "dev1", "dev2",
        "api-owner", "team-member-1", "team-member-2"
    }
    
    assert users == expected

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
    
    # Mock CODEOWNERS to return None (no file found)
    access_control._find_codeowners_file = Mock(return_value=None)
    
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
    
    # Mock CODEOWNERS to return None (no file found)
    access_control._find_codeowners_file = Mock(return_value=None)
    
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

def test_validate_update_request_owner(access_control, mock_repo):
    """Test update validation for owner"""
    # Mock issue with owner as creator
    issue = Mock()
    issue.user.login = "repo-owner"
    mock_repo.get_issue.return_value = issue
    
    # No unprocessed comments
    issue.get_comments.return_value = []
    
    assert access_control.validate_update_request(123) is True

def test_validate_update_request_with_comments(access_control, mock_repo):
    """Test update validation with comments"""
    # Mock issue with owner as creator
    issue = Mock()
    issue.user.login = "repo-owner"
    mock_repo.get_issue.return_value = issue
    
    # Mock comments
    processed_comment = Mock()
    processed_comment.user.login = "random-user"
    processed_reaction = Mock()
    processed_reaction.content = "+1"
    processed_comment.get_reactions.return_value = [processed_reaction]
    
    unprocessed_comment = Mock()
    unprocessed_comment.user.login = "repo-owner"
    unprocessed_comment.get_reactions.return_value = []
    
    issue.get_comments.return_value = [processed_comment, unprocessed_comment]
    
    assert access_control.validate_update_request(123) is True

def test_validate_update_request_unauthorized_comment(access_control, mock_repo):
    """Test update validation fails with unauthorized comment"""
    # Mock issue with owner as creator
    issue = Mock()
    issue.user.login = "repo-owner"  # This is valid
    mock_repo.get_issue.return_value = issue
    
    # Mock unauthorized comment
    comment = Mock()
    comment.user.login = "random-user"
    comment.get_reactions.return_value = iter([])  # Empty iterator for no reactions
    
    issue.get_comments.return_value = [comment]
    
    # Mock CODEOWNERS to return None (no file found)
    access_control._find_codeowners_file = Mock(return_value=None)
    
    assert access_control.validate_update_request(123) is False

def test_get_codeowners_caching(access_control, mock_repo):
    """Test that CODEOWNERS list is cached"""
    # Mock content for first call
    content = Mock()
    content.decoded_content = b"* @user1"
    mock_repo.get_contents.return_value = content
    
    # First call
    users1 = access_control._get_codeowners()
    assert users1 == {"user1"}
    assert mock_repo.get_contents.call_count == 1
    
    # Second call should use cache
    users2 = access_control._get_codeowners()
    assert users2 == {"user1"}
    assert mock_repo.get_contents.call_count == 1  # No additional API calls
