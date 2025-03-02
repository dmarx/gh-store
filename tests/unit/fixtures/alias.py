# tests/unit/fixtures/alias.py
"""Alias-specific fixtures for gh-store unit tests."""

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock

from gh_store.core.version import CLIENT_VERSION


@pytest.fixture
def canonical_issue(mock_issue_factory):
    """Create a standard canonical issue for testing."""
    return mock_issue_factory(
        number=1,
        labels=["stored-object", "UID:canonical-id", "canonical-object"],
        body=json.dumps({"value": 42}),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
    )


@pytest.fixture
def alias_issue(mock_issue_factory):
    """Create a standard alias issue for testing."""
    return mock_issue_factory(
        number=2,
        labels=["stored-object", "UID:alias-id", "alias-object", "ALIAS-TO:1"],
        body=json.dumps({"alias_to": "canonical-id"}),
        created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 3, tzinfo=timezone.utc)
    )


@pytest.fixture
def secondary_alias_issue(mock_issue_factory):
    """Create a second alias issue for the same canonical object."""
    return mock_issue_factory(
        number=3,
        labels=["stored-object", "UID:secondary-alias-id", "alias-object", "ALIAS-TO:1"],
        body=json.dumps({"alias_to": "canonical-id"}),
        created_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 4, tzinfo=timezone.utc)
    )


@pytest.fixture
def canonical_alias_pair(mock_repo_factory, canonical_issue, alias_issue):
    """Set up a repo with a canonical and alias issue pair."""
    repo = mock_repo_factory()
    
    def get_issue_side_effect(num):
        if num == 1:
            return canonical_issue
        elif num == 2:
            return alias_issue
        else:
            raise ValueError(f"Unexpected issue number: {num}")
        
    repo.get_issue.side_effect = get_issue_side_effect
    
    def get_issues_side_effect(**kwargs):
        labels = kwargs.get("labels", [])
        state = kwargs.get("state", "all")
        
        # Match by state if provided
        if state == "open":
            return []  # No issues are open
        
        # Match by labels
        if "UID:canonical-id" in labels:
            return [canonical_issue]
        elif "UID:alias-id" in labels:
            return [alias_issue]
        elif "ALIAS-TO:1" in labels:
            return [alias_issue]
        elif len(labels) == 1 and labels[0] == "stored-object":
            return [canonical_issue, alias_issue]
        
        # Return empty list for any other query
        return []
        
    repo.get_issues.side_effect = get_issues_side_effect
    
    return repo


@pytest.fixture
def multi_alias_setup(mock_repo_factory, canonical_issue, alias_issue, secondary_alias_issue):
    """Set up a repo with a canonical issue and multiple aliases."""
    repo = mock_repo_factory()
    
    def get_issue_side_effect(num):
        if num == 1:
            return canonical_issue
        elif num == 2:
            return alias_issue
        elif num == 3:
            return secondary_alias_issue
        else:
            raise ValueError(f"Unexpected issue number: {num}")
        
    repo.get_issue.side_effect = get_issue_side_effect
    
    def get_issues_side_effect(**kwargs):
        labels = kwargs.get("labels", [])
        state = kwargs.get("state", "all")
        
        if "alias-object" in labels:
            return [alias_issue, secondary_alias_issue]
        elif "UID:canonical-id" in labels:
            return [canonical_issue]
        elif "UID:alias-id" in labels:
            return [alias_issue]
        elif "UID:secondary-alias-id" in labels:
            return [secondary_alias_issue]
        elif "ALIAS-TO:1" in labels:
            return [alias_issue, secondary_alias_issue]
        return []
        
    repo.get_issues.side_effect = get_issues_side_effect
    return repo


@pytest.fixture
def duplicate_issues(mock_issue_factory):
    """Create multiple issues with the same UID for deduplication tests."""
    issues = [
        mock_issue_factory(
            number=1,
            labels=["stored-object", "UID:duplicate-id"],
            body=json.dumps({"value": 42}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
        ),
        mock_issue_factory(
            number=2,
            labels=["stored-object", "UID:duplicate-id"],
            body=json.dumps({"value": 43}),
            created_at=datetime(2025, 1, 3, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 4, tzinfo=timezone.utc)
        ),
        mock_issue_factory(
            number=3,
            labels=["stored-object", "UID:duplicate-id"],
            body=json.dumps({"value": 44}),
            created_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 6, tzinfo=timezone.utc)
        )
    ]
    return issues


@pytest.fixture
def alias_system_comment(mock_comment_factory):
    """Create a system comment documenting an alias relationship."""
    return mock_comment_factory(
        user_login="repo-owner",
        comment_id=101,
        body={
            "_data": {
                "duplicate_relationship": "alias",
                "canonical_issue": 1,
                "timestamp": "2025-01-01T00:00:00Z"
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-01T00:00:00Z",
                "update_mode": "append",
                "system": True
            },
            "type": "system_relationship"
        }
    )


@pytest.fixture
def canonical_system_comment(mock_comment_factory):
    """Create a system comment documenting a canonical relationship."""
    return mock_comment_factory(
        user_login="repo-owner",
        comment_id=102,
        body={
            "_data": {
                "duplicate_relationship": "canonical",
                "alias_issues": [2, 3],
                "timestamp": "2025-01-01T00:00:00Z"
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-01T00:00:00Z",
                "update_mode": "append",
                "system": True
            },
            "type": "system_relationship"
        }
    )


@pytest.fixture
def alias_update_comment(mock_comment_factory):
    """Create an update comment from an alias issue."""
    return mock_comment_factory(
        user_login="repo-owner",
        comment_id=201,
        body={
            "_data": {
                "from_alias": True,
                "value": 50
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-03T00:00:00Z",
                "update_mode": "append"
            }
        }
    )


@pytest.fixture
def canonical_update_comment(mock_comment_factory):
    """Create an update comment from a canonical issue."""
    return mock_comment_factory(
        user_login="repo-owner",
        comment_id=202,
        body={
            "_data": {
                "from_canonical": True,
                "value": 60
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": "2025-01-02T00:00:00Z",
                "update_mode": "append"
            }
        }
    )
