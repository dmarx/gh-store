# tests/unit/fixtures/canonical.py
"""Fixtures for canonicalization tests"""

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch, MagicMock

from gh_store.tools.canonicalize import CanonicalStore, LabelNames

@pytest.fixture
def mock_canonical_store():
    """Create a mock for CanonicalStore class."""
    with patch('gh_store.cli.commands.CanonicalStore') as mock_canonical:
        canonical_instance = Mock()
        mock_canonical.return_value = canonical_instance
        
        # Mock commonly used methods
        canonical_instance.find_aliases.return_value = {"alias-obj": "canonical-obj"}
        
        yield mock_canonical

@pytest.fixture
def mock_labels_response():
    """Mock the response for get_labels to return iterable labels."""
    labels = [
        Mock(name="stored-object"),
        Mock(name="deprecated-object"),
        Mock(name="UID:test-123")
    ]
    return labels

@pytest.fixture
def canonical_store_with_mocks(mock_repo_factory, default_config, mock_labels_response):
    """Create a CanonicalStore instance with mocked repo and methods."""
    # Create mock repo
    repo = mock_repo_factory(
        name="owner/repo",
        owner_login="repo-owner",
        owner_type="User",
        labels=["stored-object", "deprecated-object"]
    )
    
    # Setup get_labels to return iterable
    repo.get_labels.return_value = mock_labels_response
    
    # Create CanonicalStore with mocked repo
    with patch('gh_store.core.store.Github') as mock_gh:
        mock_gh.return_value.get_repo.return_value = repo
        
        store = CanonicalStore(token="fake-token", repo="owner/repo")
        store.repo = repo
        store.access_control.repo = repo
        store.config = default_config
        
        # Mock common methods
        store._extract_comment_metadata = Mock(side_effect=lambda comment, issue_number, object_id: {
            "data": json.loads(comment.body) if hasattr(comment, 'body') else {},
            "timestamp": getattr(comment, 'created_at', datetime.now(timezone.utc)),
            "id": getattr(comment, 'id', 1),
            "source_issue": issue_number,
            "source_object_id": object_id
        })
        
        # Setup for find_duplicates
        store.repo.get_issues = Mock(return_value=[])
        
        # Mock methods to avoid real API calls
        store._ensure_special_labels = Mock()
        
        return store

@pytest.fixture
def mock_issue_with_initial_state(mock_issue_factory, mock_comment_factory):
    """Create a mock issue with initial state for canonicalization tests."""
    # Create initial state comment
    initial_comment = mock_comment_factory(
        body={
            "type": "initial_state",
            "_data": {"name": "test", "value": 42},
            "_meta": {
                "client_version": "0.7.0",
                "timestamp": "2025-01-01T00:00:00Z",
                "update_mode": "append",
                "issue_number": 123  # Add issue number
            }
        },
        comment_id=1,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    
    # Create issue with initial state comment
    return mock_issue_factory(
        number=123,
        body=json.dumps({"name": "test", "value": 42}),
        labels=["stored-object", "UID:metrics"],
        comments=[initial_comment]
    )
