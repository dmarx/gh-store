# tests/unit/fixtures/common.py
"""Common mock factories and utilities for gh-store unit tests."""

from datetime import datetime, timezone
from unittest.mock import Mock

def create_base_mock(
    id: str,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    **kwargs
) -> Mock:
    """
    Create a base mock object with common attributes.
    
    Args:
        id: Unique identifier for the mock object
        created_at: Creation timestamp (defaults to 2025-01-01)
        updated_at: Last update timestamp (defaults to 2025-01-02)
        **kwargs: Additional attributes to set on the mock

    Returns:
        Mock object with standard attributes
    """
    mock = Mock()
    mock.id = id
    mock.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
    mock.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
    
    for key, value in kwargs.items():
        setattr(mock, key, value)
    
    return mock
