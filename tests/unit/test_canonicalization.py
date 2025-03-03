# tests/unit/test_canonicalization.py
"""Tests for the canonicalization and aliasing functionality."""

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch

from gh_store.tools.canonicalize import CanonicalStore, LabelNames, DeprecationReason


@pytest.fixture
def canonical_store(store, mock_repo_factory, default_config):
    """Create a CanonicalStore with mocked dependencies."""
    repo = mock_repo_factory(
        name="owner/repo",
        owner_login="repo-owner",
        owner_type="User",
        labels=["stored-object"]
    )
    
    with patch('gh_store.core.store.Github') as mock_gh:
        mock_gh.return_value.get_repo.return_value = repo
        
        store = CanonicalStore(token="fake-token", repo="owner/repo")
        store.repo = repo
        store.access_control.repo = repo
        store.config = default_config
        
        # Mock the _ensure_special_labels method to avoid API calls
        store._ensure_special_labels = Mock()
        
        return store

@pytest.fixture
def mock_alias_issue(mock_issue_factory):
    """Create a mock issue that is an alias to another object."""
    return mock_issue_factory(
        number=789,
        labels=[
            "stored-object",
            f"{LabelNames.UID_PREFIX}daily-metrics",
            f"{LabelNames.ALIAS_TO_PREFIX}metrics"
        ],
        body=json.dumps({"period": "daily"}),
        created_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 12, tzinfo=timezone.utc)
    )

@pytest.fixture
def mock_canonical_issue(mock_issue_factory):
    """Create a mock issue that is the canonical version of an object."""
    return mock_issue_factory(
        number=123,
        labels=[
            "stored-object",
            f"{LabelNames.UID_PREFIX}metrics"
        ],
        body=json.dumps({"count": 42}),
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 15, tzinfo=timezone.utc)
    )

@pytest.fixture
def mock_duplicate_issue(mock_issue_factory, mock_label_factory):
    """Create a mock issue that is a duplicate to be deprecated."""
    return mock_issue_factory(
        number=456,
        labels=[
            mock_label_factory("stored-object"),
            mock_label_factory(f"{LabelNames.UID_PREFIX}metrics")
        ],
        body=json.dumps({"count": 15}),
        created_at=datetime(2025, 1, 5, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 5, tzinfo=timezone.utc)
    )

@pytest.fixture
def mock_deprecated_issue(mock_issue_factory, mock_label_factory):
    """Create a mock issue that has already been deprecated."""
    return mock_issue_factory(
        number=457,
        labels=[
            mock_label_factory(LabelNames.DEPRECATED),
            mock_label_factory(f"{LabelNames.MERGED_INTO_PREFIX}metrics")
        ],
        body=json.dumps({"old": "data"}),
        created_at=datetime(2025, 1, 6, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 6, tzinfo=timezone.utc)
    )

class TestCanonicalStoreObjectResolution:
    """Test object resolution functionality."""
    
    def test_resolve_canonical_object_id_direct(self, canonical_store, mock_canonical_issue):
        """Test resolving a canonical object ID (direct match)."""
        # Set up repository to return our canonical issue
        canonical_store.repo.get_issues.return_value = [mock_canonical_issue]
        
        # Should return the same ID since it's canonical
        result = canonical_store.resolve_canonical_object_id("metrics")
        assert result == "metrics"
        
        # Verify correct query was made - using string labels as the real implementation does
        canonical_store.repo.get_issues.assert_called_with(
            labels=[f"{LabelNames.UID_PREFIX}metrics", f"{LabelNames.ALIAS_TO_PREFIX}*"],
            state="all"
        )
        
    def test_resolve_canonical_object_id_alias(self, canonical_store, mock_alias_issue):
        """Test resolving an alias to find its canonical object ID."""
        # Set up repository to return our alias issue
        canonical_store.repo.get_issues.return_value = [mock_alias_issue]
        
        # Should return the canonical ID that the alias points to
        result = canonical_store.resolve_canonical_object_id("daily-metrics")
        assert result == "metrics"
        
        # Clear previous calls to avoid interference
        canonical_store.repo.get_issues.reset_mock()
        
        # Call the method again to check the actual call
        canonical_store.resolve_canonical_object_id("daily-metrics")
        
        # Verify correct query was made - using actual call args
        args, kwargs = canonical_store.repo.get_issues.call_args
        assert kwargs["state"] == "all"
        assert "UID:daily-metrics" in kwargs["labels"]
        assert "ALIAS-TO:*" in kwargs["labels"]

    def test_resolve_canonical_object_id_nonexistent(self, canonical_store):
        """Test resolving a non-existent object ID."""
        # Set up repository to return no issues
        canonical_store.repo.get_issues.return_value = []
        
        # Should return the same ID since no alias was found
        result = canonical_store.resolve_canonical_object_id("nonexistent")
        assert result == "nonexistent"

    def test_resolve_canonical_object_id_circular_prevention(self, canonical_store, mock_label_factory):
        """Test prevention of circular references in alias resolution."""
        # Create a circular reference scenario
        circular_alias_1 = Mock()
        circular_alias_1.labels = [
            mock_label_factory(f"{LabelNames.UID_PREFIX}object-a"),
            mock_label_factory(f"{LabelNames.ALIAS_TO_PREFIX}object-b")
        ]
        
        circular_alias_2 = Mock()
        circular_alias_2.labels = [
            mock_label_factory(f"{LabelNames.UID_PREFIX}object-b"),
            mock_label_factory(f"{LabelNames.ALIAS_TO_PREFIX}object-a")
        ]
        
        # Set up repository to simulate circular references
        def mock_get_issues_side_effect(**kwargs):
            labels = kwargs.get('labels', [])
            if f"{LabelNames.UID_PREFIX}object-a" in labels:
                return [circular_alias_1]
            elif f"{LabelNames.UID_PREFIX}object-b" in labels:
                return [circular_alias_2]
            return []
            
        canonical_store.repo.get_issues.side_effect = mock_get_issues_side_effect
        
        # Should detect circular reference and return original ID
        result = canonical_store.resolve_canonical_object_id("object-a")
        assert result == "object-b"  # It should follow at least one level

class TestCanonicalStoreAliasing:
    """Test alias creation and handling."""

    def test_create_alias(self, canonical_store, mock_canonical_issue, mock_alias_issue, mock_label_factory, mock_issue_factory):
        """Test creating an alias relationship."""
        # Set up repository to find source and target objects
        def mock_get_issues_side_effect(**kwargs):
            labels = kwargs.get('labels', [])
            if f"{LabelNames.UID_PREFIX}weekly-metrics" in labels:
                # Source object
                return [mock_issue_factory(
                    number=101,
                    labels=[
                        "stored-object",
                        f"{LabelNames.UID_PREFIX}weekly-metrics"
                    ]
                )]
            elif f"{LabelNames.UID_PREFIX}metrics" in labels:
                # Target object
                return [mock_canonical_issue]
            return []
            
        canonical_store.repo.get_issues.side_effect = mock_get_issues_side_effect
        
        # Mock the add_to_labels method
        source_issue_mock = Mock()
        canonical_store.repo.get_issues.return_value = [source_issue_mock]
        
        # Mock the create_comment method
        source_issue_mock.create_comment = Mock()
        mock_canonical_issue.create_comment = Mock()
        
        # Create label if needed
        canonical_store.repo.create_label = Mock()
        
        # Execute create_alias
        result = canonical_store.create_alias("weekly-metrics", "metrics")
        
        # Verify result
        assert result["success"] is True
        assert result["source_id"] == "weekly-metrics"
        assert result["target_id"] == "metrics"
        
        # Verify label was created
        canonical_store.repo.create_label.assert_called_once()
        
        # Verify label was added to source issue
        source_issue_mock.add_to_labels.assert_called_with(f"{LabelNames.ALIAS_TO_PREFIX}metrics")
        
        # Verify system comments were added
        source_issue_mock.create_comment.assert_called_once()
        mock_canonical_issue.create_comment.assert_called_once()

    def test_create_alias_already_alias(self, canonical_store, mock_alias_issue):
        """Test error when creating an alias for an object that is already an alias."""
        # Set up repository to return an issue that's already an alias
        canonical_store.repo.get_issues.return_value = [mock_alias_issue]
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Object daily-metrics is already an alias"):
            canonical_store.create_alias("daily-metrics", "metrics")

    def test_create_alias_source_not_found(self, canonical_store):
        """Test error when source object is not found."""
        # Set up repository to return no issues
        canonical_store.repo.get_issues.return_value = []
        
        # Should raise ObjectNotFound
        with pytest.raises(Exception, match="Source object not found"):
            canonical_store.create_alias("nonexistent", "metrics")

    def test_create_alias_target_not_found(self, canonical_store, mock_duplicate_issue):
        """Test error when target object is not found."""
        # Set up repository to find source but not target
        def mock_get_issues_side_effect(**kwargs):
            labels = kwargs.get('labels', [])
            if f"{LabelNames.UID_PREFIX}duplicate-metrics" in labels:
                return [mock_duplicate_issue]
            return []
            
        canonical_store.repo.get_issues.side_effect = mock_get_issues_side_effect
        
        # Should raise ObjectNotFound
        with pytest.raises(Exception, match="Target object not found"):
            canonical_store.create_alias("duplicate-metrics", "nonexistent")

class TestCanonicalStoreDeprecation:
    """Test object deprecation functionality."""

    def test_deprecate_object(self, canonical_store, mock_canonical_issue, mock_duplicate_issue):
        """Test deprecating an object as duplicate."""
        # Set up repository to find source and target objects
        def mock_get_issues_side_effect(**kwargs):
            labels = kwargs.get('labels', [])
            if f"{LabelNames.UID_PREFIX}metrics" in labels and len(labels) == 1:
                # When searching for all metrics objects
                return [mock_canonical_issue, mock_duplicate_issue]
            elif f"{LabelNames.UID_PREFIX}metrics" in labels:
                # When searching for canonical
                return [mock_canonical_issue]
            elif f"{LabelNames.UID_PREFIX}duplicate-metrics" in labels:
                # When searching for duplicate to deprecate
                return [mock_duplicate_issue]
            return []
            
        canonical_store.repo.get_issues.side_effect = mock_get_issues_side_effect
        
        # Mock label creation and modification methods
        canonical_store.repo.create_label = Mock()
        mock_duplicate_issue.remove_from_labels = Mock()
        mock_duplicate_issue.add_to_labels = Mock()
        
        # Mock comment creation
        mock_duplicate_issue.create_comment = Mock()
        mock_canonical_issue.create_comment = Mock()
        
        # Mock virtual merge processing
        canonical_store.process_with_virtual_merge = Mock()
        
        # Execute deprecate_object
        result = canonical_store.deprecate_object(
            "duplicate-metrics", 
            "metrics", 
            DeprecationReason.DUPLICATE
        )
        
        # Verify result
        assert result["success"] is True
        assert result["source_object_id"] == "duplicate-metrics"
        assert result["target_object_id"] == "metrics"
        assert result["reason"] == DeprecationReason.DUPLICATE
        
        # Verify UID label was removed
        mock_duplicate_issue.remove_from_labels.assert_called_with(
            f"{LabelNames.UID_PREFIX}duplicate-metrics"
        )
        
        # Verify deprecated labels were added
        mock_duplicate_issue.add_to_labels.assert_called_with(
            LabelNames.DEPRECATED, 
            f"{LabelNames.MERGED_INTO_PREFIX}metrics"
        )
        
        # Verify system comments were added
        mock_duplicate_issue.create_comment.assert_called_once()
        mock_canonical_issue.create_comment.assert_called_once()
        
        # Verify virtual merge was processed
        canonical_store.process_with_virtual_merge.assert_called_with("metrics")

    def test_deduplicate_object(self, canonical_store, mock_canonical_issue, mock_duplicate_issue):
        """Test deduplication of an object with multiple issues."""
        # Set up repository to find issues with the same UID
        canonical_store.repo.get_issues.return_value = [mock_canonical_issue, mock_duplicate_issue]
        
        # Mock the deprecate_object method
        canonical_store.deprecate_object = Mock(return_value={
            "success": True,
            "source_object_id": "metrics",
            "target_object_id": "metrics",
            "reason": DeprecationReason.DUPLICATE
        })
        
        # Mock _get_object_id method
        canonical_store._get_object_id = Mock(side_effect=lambda issue: "metrics")
        
        # Execute deduplicate_object
        result = canonical_store.deduplicate_object("metrics")
        
        # Verify result
        assert result["success"] is True
        assert result["canonical_object_id"] == "metrics"
        assert result["duplicates_processed"] == 1
        
        # Verify deprecate_object was called
        canonical_store.deprecate_object.assert_called_once()

    def test_deduplicate_object_no_duplicates(self, canonical_store, mock_canonical_issue):
        """Test deduplication when no duplicates exist."""
        # Set up repository to find only one issue
        canonical_store.repo.get_issues.return_value = [mock_canonical_issue]
        
        # Execute deduplicate_object
        result = canonical_store.deduplicate_object("metrics")
        
        # Verify result
        assert result["success"] is True
        assert "message" in result
        assert "No duplicates found" in result["message"]

class TestCanonicalStoreVirtualMerge:
    """Test virtual merge processing."""

    def test_collect_all_comments(self, canonical_store, mock_canonical_issue, mock_alias_issue, mock_comment_factory):
        """Test collecting comments from canonical and alias issues."""
        # Create mock comments for each issue
        canonical_comments = [
            mock_comment_factory(
                body={
                    "type": "initial_state",
                    "_data": {"count": 0},
                    "_meta": {
                        "client_version": "0.7.0",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "update_mode": "append"
                    }
                },
                comment_id=1,
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
            ),
            mock_comment_factory(
                body={
                    "_data": {"count": 10},
                    "_meta": {
                        "client_version": "0.7.0",
                        "timestamp": "2025-01-02T00:00:00Z",
                        "update_mode": "append"
                    }
                },
                comment_id=2,
                created_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
            )
        ]
        
        alias_comments = [
            mock_comment_factory(
                body={
                    "_data": {"period": "daily"},
                    "_meta": {
                        "client_version": "0.7.0",
                        "timestamp": "2025-01-10T00:00:00Z",
                        "update_mode": "append"
                    }
                },
                comment_id=3,
                created_at=datetime(2025, 1, 10, tzinfo=timezone.utc)
            )
        ]
        
        # Set up mock_comments method returns
        mock_canonical_issue.get_comments.return_value = canonical_comments
        mock_alias_issue.get_comments.return_value = alias_comments
        
        # Set up repository to find canonical and alias issues
        def mock_get_issues_side_effect(**kwargs):
            labels = kwargs.get('labels', [])
            if f"{LabelNames.UID_PREFIX}metrics" in labels and f"{LabelNames.ALIAS_TO_PREFIX}*" not in labels:
                # When searching for canonical
                return [mock_canonical_issue]
            elif f"{LabelNames.ALIAS_TO_PREFIX}metrics" in labels:
                # When searching for aliases
                return [mock_alias_issue]
            return []
            
        canonical_store.repo.get_issues.side_effect = mock_get_issues_side_effect
        
        # Mock _extract_comment_metadata to return minimal test data
        def mock_extract_metadata(comment, issue_number, object_id):
            # Just return basic information directly from comment for testing
            try:
                data = json.loads(comment.body)
                return {
                    "data": data,
                    "timestamp": comment.created_at,
                    "id": comment.id,
                    "source_issue": issue_number,
                    "source_object_id": object_id
                }
            except:
                return None
                
        canonical_store._extract_comment_metadata = mock_extract_metadata
        
        # Execute collect_all_comments
        comments = canonical_store.collect_all_comments("metrics")
        
        # Verify results
        assert len(comments) == 3
        
        # Verify chronological order
        timestamps = [c["timestamp"] for c in comments]
        assert timestamps == sorted(timestamps)
        
        # Verify comment sources
        assert comments[0]["source_issue"] == mock_canonical_issue.number
        assert comments[1]["source_issue"] == mock_canonical_issue.number
        assert comments[2]["source_issue"] == mock_alias_issue.number

    def test_process_with_virtual_merge(self, canonical_store, mock_canonical_issue, mock_comment_factory):
        """Test processing virtual merge to build object state."""
        # Create mock comments with proper structure
        comments = [
            {
                "data": {
                    "type": "initial_state",
                    "_data": {"count": 0, "name": "test"},
                    "_meta": {
                        "client_version": "0.7.0",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "update_mode": "append"
                    }
                },
                "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "id": 1,
                "source_issue": 123,
                "source_object_id": "metrics"
            },
            {
                "data": {
                    "_data": {"count": 10},
                    "_meta": {
                        "client_version": "0.7.0",
                        "timestamp": "2025-01-02T00:00:00Z",
                        "update_mode": "append"
                    }
                },
                "timestamp": datetime(2025, 1, 2, tzinfo=timezone.utc),
                "id": 2,
                "source_issue": 123,
                "source_object_id": "metrics"
            },
            {
                "data": {
                    "_data": {"period": "daily"},
                    "_meta": {
                        "client_version": "0.7.0",
                        "timestamp": "2025-01-10T00:00:00Z",
                        "update_mode": "append"
                    }
                },
                "timestamp": datetime(2025, 1, 10, tzinfo=timezone.utc),
                "id": 3,
                "source_issue": 789,
                "source_object_id": "daily-metrics"
            },
            {
                "data": {
                    "_data": {"count": 42},
                    "_meta": {
                        "client_version": "0.7.0",
                        "timestamp": "2025-01-15T00:00:00Z",
                        "update_mode": "append"
                    }
                },
                "timestamp": datetime(2025, 1, 15, tzinfo=timezone.utc),
                "id": 4,
                "source_issue": 123,
                "source_object_id": "metrics"
            }
        ]
        
        # Mock collect_all_comments to return our preset comments
        canonical_store.collect_all_comments = Mock(return_value=comments)
        canonical_store.resolve_canonical_object_id = Mock(return_value="metrics")
        
        # Set up repository to find canonical issue
        canonical_store.repo.get_issues.return_value = [mock_canonical_issue]
        
        # Mock issue edit method
        mock_canonical_issue.edit = Mock()
        
        # Execute process_with_virtual_merge
        result = canonical_store.process_with_virtual_merge("metrics")
        
        # Verify results
        assert result.meta.object_id == "metrics"
        
        # Verify data was merged correctly
        assert result.data["count"] == 42
        assert result.data["name"] == "test"
        assert result.data["period"] == "daily"
        
        # Verify canonical issue was updated
        mock_canonical_issue.edit.assert_called_once()

class TestCanonicalStoreGetUpdate:
    """Test get and update object operations with virtual merging."""

    def test_get_object_direct(self, canonical_store, mock_canonical_issue):
        """Test getting an object directly."""
        # Set up resolve_canonical_object_id to return same ID
        canonical_store.resolve_canonical_object_id = Mock(return_value="metrics")
        
        # Set up process_with_virtual_merge to return a mock object
        mock_obj = Mock()
        mock_obj.meta.object_id = "metrics"
        mock_obj.data = {"count": 42, "name": "test"}
        canonical_store.process_with_virtual_merge = Mock(return_value=mock_obj)
        
        # Execute get_object
        result = canonical_store.get_object("metrics")
        
        # Verify results
        assert result.meta.object_id == "metrics"
        assert result.data["count"] == 42
        
        # Verify correct methods were called
        canonical_store.resolve_canonical_object_id.assert_called_with("metrics")
        canonical_store.process_with_virtual_merge.assert_called_with("metrics")

    def test_get_object_via_alias(self, canonical_store):
        """Test getting an object via its alias."""
        # Set up resolve_canonical_object_id to return canonical ID
        canonical_store.resolve_canonical_object_id = Mock(return_value="metrics")
        
        # Set up process_with_virtual_merge to return a mock object
        mock_obj = Mock()
        mock_obj.meta.object_id = "metrics"
        mock_obj.data = {"count": 42, "name": "test"}
        canonical_store.process_with_virtual_merge = Mock(return_value=mock_obj)
        
        # Execute get_object with alias ID
        result = canonical_store.get_object("daily-metrics")
        
        # Verify results
        assert result.meta.object_id == "metrics"
        assert result.data["count"] == 42
        
        # Verify correct methods were called
        canonical_store.resolve_canonical_object_id.assert_called_with("daily-metrics")
        canonical_store.process_with_virtual_merge.assert_called_with("metrics")

    def test_update_object_alias(self, canonical_store, mock_alias_issue):
        """Test updating an object via its alias."""
        # Setup to find the alias issue
        canonical_store.repo.get_issues.return_value = [mock_alias_issue]
        
        # Mock issue create_comment and edit methods
        mock_alias_issue.create_comment = Mock()
        mock_alias_issue.edit = Mock()
        
        # Mock get_object to return a result after update
        mock_obj = Mock()
        mock_obj.meta.object_id = "metrics"
        mock_obj.data = {"count": 42, "name": "test", "period": "daily", "new_field": "value"}
        canonical_store.get_object = Mock(return_value=mock_obj)
        
        # Execute update_object on the alias
        changes = {"new_field": "value"}
        result = canonical_store.update_object("daily-metrics", changes)
        
        # Verify results
        assert result.meta.object_id == "metrics"
        assert result.data["new_field"] == "value"
        
        # Verify comment was added to alias issue
        mock_alias_issue.create_comment.assert_called_once()
        
        # Verify issue was reopened
        mock_alias_issue.edit.assert_called_with(state="open")

    def test_update_object_deprecated(self, canonical_store, mock_deprecated_issue, mock_canonical_issue, mock_label_factory):
        """Test updating a deprecated object."""
        # Setup to find a deprecated issue pointing to a canonical object
        def mock_get_issues_side_effect(**kwargs):
            labels = kwargs.get('labels', [])
            if f"{LabelNames.MERGED_INTO_PREFIX}*" in labels and LabelNames.DEPRECATED in labels:
                return [mock_deprecated_issue]
            elif f"{LabelNames.UID_PREFIX}metrics" in labels:
                return [mock_canonical_issue]
            return []
            
        canonical_store.repo.get_issues.side_effect = mock_get_issues_side_effect
        
        # Setup mock_deprecated_issue to have proper labels
        mock_deprecated_issue.labels = [
            mock_label_factory(name=LabelNames.DEPRECATED),
            mock_label_factory(name=f"{LabelNames.MERGED_INTO_PREFIX}metrics")
        ]
        
        # Mock issue create_comment and edit methods
        mock_canonical_issue.create_comment = Mock()
        mock_canonical_issue.edit = Mock()
        
        # Mock get_object to return a result after update
        mock_obj = Mock()
        mock_obj.meta.object_id = "metrics"
        mock_obj.data = {"count": 42, "name": "test", "new_field": "value"}
        canonical_store.get_object = Mock(return_value=mock_obj)
        canonical_store.resolve_canonical_object_id = Mock(return_value="metrics")
        
        # Execute update_object
        changes = {"new_field": "value"}
        result = canonical_store.update_object("old-metrics", changes)
        
        # Verify results
        assert result.meta.object_id == "metrics"
        assert result.data["new_field"] == "value"

class TestCanonicalStoreFinding:
    """Test finding duplicates and aliases."""

    def test_find_duplicates(self, canonical_store, mock_canonical_issue, mock_duplicate_issue):
        """Test finding duplicate objects."""
        # Set up repository to return a list of issues
        canonical_store.repo.get_issues.return_value = [mock_canonical_issue, mock_duplicate_issue]
        
        # Execute find_duplicates
        duplicates = canonical_store.find_duplicates()
        
        # Verify results
        assert len(duplicates) == 1
        assert f"{LabelNames.UID_PREFIX}metrics" in duplicates
        assert len(duplicates[f"{LabelNames.UID_PREFIX}metrics"]) == 2

    def test_find_aliases(self, canonical_store, mock_alias_issue):
        """Test finding aliases for objects."""
        # Set up repository to return a list of alias issues
        canonical_store.repo.get_issues.return_value = [mock_alias_issue]
        
        # Mock _get_object_id method
        canonical_store._get_object_id = Mock(return_value="daily-metrics")
        
        # Execute find_aliases
        aliases = canonical_store.find_aliases()
        
        # Verify results
        assert len(aliases) == 1
        assert aliases["daily-metrics"] == "metrics"

    def test_find_aliases_for_specific_object(self, canonical_store, mock_alias_issue):
        """Test finding aliases for a specific object."""
        # Set up repository to return a list of alias issues
        canonical_store.repo.get_issues.return_value = [mock_alias_issue]
        
        # Mock _get_object_id method
        canonical_store._get_object_id = Mock(return_value="daily-metrics")
        
        # Execute find_aliases with specific object
        aliases = canonical_store.find_aliases("metrics")
        
        # Verify results
        assert len(aliases) == 1
        assert aliases["daily-metrics"] == "metrics"
        
        # Verify correct query was made
        canonical_store.repo.get_issues.assert_called_with(
            labels=[f"{LabelNames.ALIAS_TO_PREFIX}metrics"],
            state="all"
        )

def test_get_object_canonicalize_modes(self, canonical_store, mock_alias_issue):
    """
    Test that get_object returns a canonical (aggregated) view when canonicalize=True (default)
    and returns the raw alias object when canonicalize=False.
    
    Assume that mock_alias_issue is set up with labels:
      "stored-object", "UID:daily-metrics", and "ALIAS-TO:metrics"
    """
    canonical_store.repo.get_issues.return_value = [mock_alias_issue]

    # When canonicalize is True, the alias should resolve to the canonical object.
    obj_canonical = canonical_store.get_object("daily-metrics", canonicalize=True)
    assert obj_canonical.meta.object_id == "metrics"

    # When canonicalize is False, the alias's own state is returned.
    obj_direct = canonical_store.get_object("daily-metrics", canonicalize=False)
    assert obj_direct.meta.object_id == "daily-metrics"
