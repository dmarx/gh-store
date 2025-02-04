# tests/unit/fixtures/common.py
"""Common mock factories and utilities for gh-store unit tests."""

from datetime import datetime, timezone
from typing import Any
import json
from unittest.mock import Mock

from gh_store.core.version import CLIENT_VERSION

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

def create_github_comment(
    user_login: str,
    body: dict[str, Any] | str,
    comment_id: int,
    reactions: list[str] | None = None,
    created_at: datetime | None = None,
    **kwargs
) -> Mock:
    """
    Create a mock GitHub comment with standard structure.
    
    Args:
        user_login: GitHub username of comment author
        body: Comment body (dict will be JSON serialized)
        comment_id: Unique comment ID
        reactions: List of reaction types
        created_at: Comment creation timestamp
        **kwargs: Additional attributes for the comment

    Returns:
        Mock comment with GitHub-like structure
    """
    comment = create_base_mock(
        id=comment_id,
        created_at=created_at,
        body=json.dumps(body) if isinstance(body, dict) else body
    )
    
    # Set up user
    user = Mock()
    user.login = user_login
    comment.user = user
    
    # Set up reactions
    mock_reactions = []
    if reactions:
        for reaction in reactions:
            mock_reaction = Mock()
            mock_reaction.content = reaction
            mock_reactions.append(mock_reaction)
    
    comment.get_reactions = Mock(return_value=mock_reactions)
    comment.create_reaction = Mock()
    
    # Add any additional attributes
    for key, value in kwargs.items():
        setattr(comment, key, value)
    
    return comment

def create_github_issue(
    number: int,
    user_login: str,
    body: dict[str, Any] | str | None = None,
    labels: list[str] | None = None,
    comments: list[Mock] | None = None,
    state: str = "closed",
    **kwargs
) -> Mock:
    """
    Create a mock GitHub issue with standard structure.
    
    Args:
        number: Issue number
        user_login: GitHub username of issue creator
        body: Issue body content
        labels: List of label names
        comments: List of mock comments
        state: Issue state (open/closed)
        **kwargs: Additional attributes for the issue

    Returns:
        Mock issue with GitHub-like structure
    """
    issue = create_base_mock(
        id=str(number),
        body=json.dumps(body) if isinstance(body, dict) else (body or "{}"),
        number=number,
        state=state
    )
    
    # Set up user
    user = Mock()
    user.login = user_login
    issue.user = user
    
    # Set up labels
    issue_labels = []
    if labels:
        for label_name in labels:
            label = Mock()
            label.name = label_name
            issue_labels.append(label)
    issue.labels = issue_labels
    
    # Set up comments
    issue.get_comments = Mock(return_value=comments or [])
    issue.create_comment = Mock()
    issue.edit = Mock()
    
    # Add any additional attributes
    for key, value in kwargs.items():
        setattr(issue, key, value)
    
    return issue

def create_store_object(
    object_id: str,
    data: dict[str, Any],
    version: int = 1,
    created_at: datetime | None = None,
    updated_at: datetime | None = None
) -> Mock:
    """
    Create a mock store object with standard structure.
    
    Args:
        object_id: Unique object identifier
        data: Object data
        version: Object version
        created_at: Creation timestamp
        updated_at: Last update timestamp

    Returns:
        Mock store object with standard structure
    """
    obj = create_base_mock(id=object_id)
    
    # Set up metadata
    meta = Mock()
    meta.object_id = object_id
    meta.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
    meta.updated_at = updated_at or datetime(2025, 1, 2, tzinfo=timezone.utc)
    meta.version = version
    
    obj.meta = meta
    obj.data = data
    
    return obj

def create_update_payload(
    data: dict[str, Any],
    update_mode: str = "append",
    timestamp: datetime | None = None
) -> dict[str, Any]:
    """
    Create a standard update payload with metadata.
    
    Args:
        data: Update data
        update_mode: Update mode (append/replace)
        timestamp: Update timestamp

    Returns:
        Dict containing update data and metadata
    """
    return {
        "_data": data,
        "_meta": {
            "client_version": CLIENT_VERSION,
            "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
            "update_mode": update_mode
        }
    }
