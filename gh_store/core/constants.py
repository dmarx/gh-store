# gh_store/core/constants.py

from enum import StrEnum # python 3.11

class LabelNames(StrEnum):
    """
    Constants for label names used by the gh-store system.
    
    Using str as a base class allows the enum values to be used directly as strings
    while still maintaining the benefits of an enumeration.
    """
    GH_STORE = "gh-store"  # System namespace label
    STORED_OBJECT = "stored-object"  # Active object label
    DEPRECATED = "deprecated-object"  # Deprecated object label
    UID_PREFIX = "UID:"  # Prefix for unique identifier labels
    ALIAS_TO_PREFIX = "ALIAS-TO:"  # Prefix for alias labels
    MERGED_INTO_PREFIX = "MERGED-INTO:"  # Prefix for merged object labels
    DEPRECATED_BY_PREFIX = "DEPRECATED-BY:"  # Prefix for referencing canonical issue
    DELETED = "archived"
    
    # def __str__(self) -> str:
    #     """Allow direct string usage in string contexts."""
    #     return self.value


class DeprecationReason(StrEnum):
    """Constants for deprecation reasons stored in metadata."""
    DUPLICATE = "duplicate"
    MERGED = "merged"
    REPLACED = "replaced"
    
    # def __str__(self) -> str:
    #     """Allow direct string usage in string contexts."""
    #     return self.value
