# tests/unit/test_types.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock

from gh_store.core.constants import LabelNames
from gh_store.core.types import StoredObject, get_object_id_from_labels

class TestStoredObject:
    """Tests for StoredObject class."""
    
    def test_from_issue(self, mock_issue_factory, mock_label_factory):
        """Test correctly creating a StoredObject from an issue."""
        # Create test data
        object_id = "test-123"
        issue_number = 42
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        data = {"name": "test", "value": 42}
        
        # Create a properly labeled mock issue
        issue = mock_issue_factory(
            number=issue_number,
            body=json.dumps(data),
            labels=[
                "gh-store",
                "stored-object",
                f"{LabelNames.UID_PREFIX}{object_id}"
            ],
            created_at=created_at,
            updated_at=updated_at
        )
        
        # Create StoredObject from the issue
        obj = StoredObject.from_issue(issue)
        
        # Verify metadata
        assert obj.meta.object_id == object_id
        assert obj.meta.label == object_id
        assert obj.meta.issue_number == issue_number
        assert obj.meta.created_at == created_at
        assert obj.meta.updated_at == updated_at
        assert obj.meta.version == 1
        
        # Verify data
        assert obj.data == data
        
    def test_from_issue_with_explicit_version(self, mock_issue_factory):
        """Test creating a StoredObject with explicit version number."""
        # Create test data
        object_id = "test-123"
        data = {"name": "test", "value": 42}
        version = 5
        
        # Create a properly labeled mock issue
        issue = mock_issue_factory(
            body=json.dumps(data),
            labels=[
                "gh-store",
                "stored-object",
                f"{LabelNames.UID_PREFIX}{object_id}"
            ]
        )
        
        # Create StoredObject with explicit version
        obj = StoredObject.from_issue(issue, version=version)
        
        # Verify version
        assert obj.meta.version == version
    
    def test_from_issue_missing_uid_label(self, mock_issue_factory):
        """Test that creating a StoredObject fails when UID label is missing."""
        # Create an issue missing the UID label
        issue = mock_issue_factory(
            body=json.dumps({"name": "test"}),
            labels=["gh-store", "stored-object"]  # No UID label
        )
        
        # Should raise ValueError when UID label is missing
        with pytest.raises(ValueError, match="No UID label found"):
            StoredObject.from_issue(issue)
    
    def test_from_issue_invalid_body(self, mock_issue_factory):
        """Test that creating a StoredObject fails with invalid JSON body."""
        # Create an issue with invalid JSON in body
        issue = mock_issue_factory(
            body="not valid json",
            labels=[
                "gh-store",
                "stored-object",
                f"{LabelNames.UID_PREFIX}test-123"
            ]
        )
        
        # Should raise JSON decode error
        with pytest.raises(json.JSONDecodeError):
            StoredObject.from_issue(issue)

class TestObjectIDFromLabels:
    """Tests for get_object_id_from_labels function."""
    
    def test_get_object_id_from_labels(self, mock_label_factory):
        """Test extracting object ID from issue labels."""
        # Create an issue with mock labels
        object_id = "test-123"
        issue = Mock()
        issue.labels = [
            mock_label_factory(name="stored-object"),
            mock_label_factory(name=f"{LabelNames.UID_PREFIX}{object_id}"),
            mock_label_factory(name="other-label")
        ]
        
        # Extract object ID
        extracted_id = get_object_id_from_labels(issue)
        
        # Verify extracted ID
        assert extracted_id == object_id
    
    def test_get_object_id_from_labels_no_match(self, mock_label_factory):
        """Test that ValueError is raised when no UID label exists."""
        # Create an issue with no UID label
        issue = Mock()
        issue.labels = [
            mock_label_factory(name="stored-object"),
            mock_label_factory(name="other-label")
        ]
        
        # Should raise ValueError
        with pytest.raises(ValueError):
            get_object_id_from_labels(issue)
