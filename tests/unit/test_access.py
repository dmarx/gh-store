# tests/unit/test_access.py

import pytest
from unittest.mock import Mock, patch
from github import GithubException, Repository, NamedUser
from gh_store.core.access import AccessControl

class MockRepositoryOwner:
    """Mock that accurately represents PyGithub's NamedUser structure"""
    def __init__(self, login: str, type_: str = "User"):
        self.login = login
        self.type = type_

class MockRepository:
    """Mock that accurately represents PyGithub's Repository structure"""
    def __init__(self, owner_login: str, owner_type: str = "User"):
        self._owner = MockRepositoryOwner(owner_login, owner_type)

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
    assert access_control.repo._owner.login == "repo-owner"  # Verify correct attribute access

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
    access_control.repo._owner = MockRepositoryOwner("new-owner")
    
    # Second call should use cached value
    info2 = access_control._get_owner_info()
    assert info2["login"] == "repo-owner"  # Should use cached value
    assert info1 == info2

def test_clear_cache_with_owner(access_control):
    """Test that clearing cache affects owner info"""
    # Prime the cache
    initial_info = access_control._get_owner_info()
    
    # Change underlying owner and clear cache
    access_control.repo._owner = MockRepositoryOwner("new-owner")
    access_control.clear_cache()
    
    # Get new owner info
    new_info = access_control._get_owner_info()
    assert new_info["login"] == "new-owner"
    assert new_info != initial_info

@pytest.mark.integration
def test_with_real_github_repo():
    """
    Integration test with actual PyGithub Repository
    Only runs when integration tests are explicitly requested
    """
    from github import Github
    
    # Create real Github instance with test token
    g = Github("test-token")
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
