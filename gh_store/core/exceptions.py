# gh_store/core/exceptions.py

class GitHubStoreError(Exception):
    """Base exception for GitHub store errors"""
    pass

class ObjectNotFound(GitHubStoreError):
    """Raised when attempting to access a non-existent object"""
    pass

class InvalidUpdate(GitHubStoreError):
    """Raised when an update comment contains invalid JSON or schema"""
    pass

class ConcurrentUpdateError(GitHubStoreError):
    """Raised when concurrent updates are detected"""
    pass

class ConfigurationError(GitHubStoreError):
    """Raised when there's an error in the store configuration"""
    pass

class DuplicateUIDError(GitHubStoreError):
    """Raised when multiple issues have the same UID label"""
    pass

class AccessDeniedError(GitHubStoreError):
    pass
