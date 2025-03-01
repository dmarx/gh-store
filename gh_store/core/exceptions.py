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
    """Raised when access is denied to a resource"""
    pass

class AliasedObjectError(GitHubStoreError):
    """Raised when attempting to directly modify an alias object"""
    
    def __init__(self, alias_id, canonical_id, message=None):
        self.alias_id = alias_id
        self.canonical_id = canonical_id
        msg = message or f"Object {alias_id} is an alias to {canonical_id}"
        super().__init__(msg)

class CircularReferenceError(GitHubStoreError):
    """Raised when a circular reference is detected in aliases"""
    
    def __init__(self, object_ids=None, message=None):
        self.object_ids = object_ids or []
        msg = message or f"Circular reference detected in aliases: {' -> '.join(self.object_ids)}"
        super().__init__(msg)

class CanonicalObjectError(GitHubStoreError):
    """Raised when an operation requires a canonical object but gets an alias"""
    
    def __init__(self, object_id, message=None):
        self.object_id = object_id
        msg = message or f"Operation requires a canonical object, but {object_id} is an alias"
        super().__init__(msg)
