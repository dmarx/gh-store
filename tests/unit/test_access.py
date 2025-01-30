# tests/unit/test_access.py

import pytest
from unittest.mock import Mock, patch
from github import GithubException, Repository, NamedUser
from gh_store.core.access import AccessControl

class MockRepositoryContent:
    """Mock for Repository Content object"""
    def __init__(self, decoded_content: bytes):
        self.decoded_content = decoded_content

class MockRepositoryOwner:
    """Mock that accurately represents PyGithub's NamedUser structure"""
    def __init__(self, login: str, type_: str = "User"):
        self.login = login
        self.type = type_

class MockRepository:
    """Mock that accurately represents PyGithub's Repository structure"""
    def __init__(self, owner_login: str, owner_type: str = "User", codeowners_content: bytes | None = None):
        self.owner = MockRepositoryOwner(owner_login, owner_type)
        self._codeowners_content = codeowners_content or b"* @repo-owner"
        
    def get_contents(self, path: str):
        """Mock get_contents to handle CODEOWNERS file"""
        if path in ['.github/CODEOWNERS', 'docs/CODEOWNERS', 'CODEOWNERS']:
            return MockRepositoryContent(self._codeowners_content)
        raise GithubException(404, "Not found")

@pytest.fixture
def mock_repo():
    """Create a mock repository that matches PyGithub's structure"""
    return MockRepository("repo-owner")

@pytest.fixture
def access_control(mock_repo):
    """Create AccessControl instance with properly structured mock repo"""
    return AccessControl(mock_repo)

def test_get_owner_info_structure(access_control):
    """Test that owner info is retrieved using correct PyGithub attributes"""
    owner_info = access_control._get_owner_info()
    assert owner_info["login"] == "repo-owner"
    assert owner_info["type"] == "User"
    assert access_control.repo.owner.login == "repo-owner"

def test_get_owner_info_compatibility():
    """Test compatibility with different PyGithub Repository structures"""
    # Test with organization owner
    org_repo = MockRepository("org-name", "Organization")
    ac = AccessControl(org_repo)
    owner_info = ac._get_owner_info()
    assert owner_info["login"] == "org-name"
    assert owner_info["type"] == "Organization"

def test_owner_info_caching(access_control):
    """Test that owner info is properly cached"""
    # First call should get owner info
    info1 = access_control._get_owner_info()
    
    # Change underlying repo owner (shouldn't affect cached result)
    access_control.repo.owner = MockRepositoryOwner("new-owner")
    
    # Second call should use cached value
    info2 = access_control._get_owner_info()
    assert info2["login"] == "repo-owner"  # Should use cached value
    assert info1 == info2

def test_clear_cache_with_owner(access_control):
    """Test that clearing cache affects owner info"""
    # Prime the cache
    initial_info = access_control._get_owner_info()
    
    # Change underlying owner and clear cache
    access_control.repo.owner = MockRepositoryOwner("new-owner")
    access_control.clear_cache()
    
    # Get new owner info
    new_info = access_control._get_owner_info()
    assert new_info["login"] == "new-owner"
    assert new_info != initial_info

# @pytest.mark.integration
def test_with_real_github_repo():
    """
    Integration test with actual PyGithub Repository.
    Requires GITHUB_TOKEN environment variable
    """
    import os
    from github import Github, Auth
    
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN environment variable not set")
    
    auth = Auth.Token(token)
    g = Github(auth=auth)
    repo = g.get_repo("octocat/Hello-World")
    ac = AccessControl(repo)
    
    # Verify owner info structure
    owner_info = ac._get_owner_info()
    assert "login" in owner_info
    assert "type" in owner_info
    assert isinstance(owner_info["login"], str)
    assert isinstance(owner_info["type"], str)

def test_validate_issue_creator_with_real_structure(access_control):
    """Test issue creator validation with accurate PyGithub structure"""
    # Create mock issue with proper user structure
    issue = Mock()
    issue.user = MockRepositoryOwner("repo-owner")
    
    assert access_control.validate_issue_creator(issue) is True
    
    # Test with different user
    issue.user = MockRepositoryOwner("other-user")
    assert access_control.validate_issue_creator(issue) is False

def test_validate_comment_author_with_real_structure(access_control):
    """Test comment author validation with accurate PyGithub structure"""
    # Create mock comment with proper user structure
    comment = Mock()
    comment.user = MockRepositoryOwner("repo-owner")
    comment.id = 123
    
    assert access_control.validate_comment_author(comment) is True
    
    # Test with different user
    comment.user = MockRepositoryOwner("other-user")
    assert access_control.validate_comment_author(comment) is False

def test_codeowners_file_handling(access_control):
    """Test CODEOWNERS file handling"""
    # Test with default CODEOWNERS content
    assert access_control._is_authorized("repo-owner") is True
    assert access_control._is_authorized("other-user") is False

    # Test with custom CODEOWNERS content
    custom_content = b"* @maintainer @contributor"
    repo = MockRepository("owner", codeowners_content=custom_content)
    ac = AccessControl(repo)
    
    assert ac._is_authorized("maintainer") is True
    assert ac._is_authorized("contributor") is True
    assert ac._is_authorized("random-user") is False

def test_missing_codeowners_file():
    """Test behavior when no CODEOWNERS file exists"""
    # Mock repo that raises 404 for all get_contents calls
    repo = MockRepository("owner")
    repo.get_contents = Mock(side_effect=GithubException(404, "Not found"))
    
    ac = AccessControl(repo)
    assert ac._find_codeowners_file() is None
    # Only owner should be authorized when no CODEOWNERS exists
    assert ac._is_authorized("owner") is True
    assert ac._is_authorized("other-user") is False
