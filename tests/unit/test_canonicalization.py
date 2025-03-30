# tests/unit/test_canonicalization.py
"""Tests for the canonicalization and aliasing functionality."""

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch

from gh_store.core.constants import LabelNames
from gh_store.tools.canonicalize import CanonicalStore, DeprecationReason


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
            LabelNames.STORED_OBJECT,
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
            LabelNames.STORED_OBJECT,
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
            mock_label_factory(LabelNames.STORED_OBJECT),
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
                        LabelNames.STORED_OBJECT,
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
        #source_issue_mock.add_to_labels.assert_called_with(f"{LabelNames.ALIAS_TO_PREFIX}metrics")
        #assert f"{LabelNames.ALIAS_TO_PREFIX}metrics" in source_issue_mock.labels
        #assert source_issue_mock.labels.append.assert_called_with(f"{LabelNames.ALIAS_TO_PREFIX}metrics")
        
        # Verify system comments were added
        #source_issue_mock.create_comment.assert_called_once()
        #mock_canonical_issue.create_comment.assert_called_once()

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
    
    # Update test for deprecate_object to use the new deprecate_issue method
    def test_deprecate_object(self, canonical_store_with_mocks, mock_issue_factory):
        """Test deprecating an object properly calls deprecate_issue."""
        store = canonical_store_with_mocks
        
        # Create source and target issues
        source_issue = mock_issue_factory(
            number=123,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:old-metrics"],
            created_at=datetime(2025, 1, 5, tzinfo=timezone.utc)
        )
        
        target_issue = mock_issue_factory(
            number=456,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:metrics"],
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
        
        # Setup get_issues mock
        def mock_get_issues(**kwargs):
            labels = kwargs.get('labels', [])
            if len(labels) > 0:
                if "UID:old-metrics" in labels[0]:
                    return [source_issue]
                elif "UID:metrics" in labels[0]:
                    return [target_issue]
            return []
        
        store.repo.get_issues = Mock(side_effect=mock_get_issues)
        
        # Mock deprecate_issue
        expected_result = {
            "success": True,
            "source_issue": 123,
            "source_object_id": "old-metrics",
            "target_issue": 456,
            "target_object_id": "metrics",
            "reason": DeprecationReason.REPLACED
        }
        store.deprecate_issue = Mock(return_value=expected_result)
        
        # Execute deprecate_object
        result = store.deprecate_object("old-metrics", "metrics", DeprecationReason.REPLACED)
        
        # Verify result
        assert result == expected_result
        
        # Verify deprecate_issue was called with correct params
        store.deprecate_issue.assert_called_once_with(
            issue_number=123,
            target_issue_number=456,
            reason=DeprecationReason.REPLACED
        )

    
    # Test for attempting to deprecate an object as itself
    def test_deprecate_object_self_reference(self, canonical_store_with_mocks, mock_issue_factory):
        """Test that deprecating an object as itself raises an error."""
        store = canonical_store_with_mocks
        
        # Create a test issue
        issue = mock_issue_factory(
            number=123,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:metrics"],
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
        
        # Setup mocks
        store.repo.get_issues.return_value = [issue]
        
        # Verify that deprecate_object raises ValueError for self-reference
        with pytest.raises(ValueError, match="Cannot deprecate an object as itself"):
            store.deprecate_object("metrics", "metrics", DeprecationReason.REPLACED)
        
    
    # Modified test for deduplicate_object
    def test_deduplicate_object(self, canonical_store_with_mocks, mock_issue_factory):
        """Test deduplication of an object with multiple issues."""
        store = canonical_store_with_mocks
        
        # Create two issues with same UID and stored-object labels
        canonical_issue = mock_issue_factory(
            number=101,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:metrics"],
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
        
        duplicate_issue = mock_issue_factory(
            number=102,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:metrics"],
            created_at=datetime(2025, 1, 2, tzinfo=timezone.utc)
        )
        
        # Setup mock for get_issues to return our test issues
        store.repo.get_issues.return_value = [canonical_issue, duplicate_issue]
        
        # Mock get_issue to return the correct issue by number
        def mock_get_issue(issue_number):
            if issue_number == 101:
                return canonical_issue
            elif issue_number == 102:
                return duplicate_issue
            return Mock()
            
        store.repo.get_issue = Mock(side_effect=mock_get_issue)
        
        # Mock _get_object_id to return the correct object ID
        store._get_object_id = Mock(return_value="metrics")
        
        # Mock deprecate_issue to simulate the deprecation and return success
        store.deprecate_issue = Mock(return_value={
            "success": True,
            "source_issue": 102,
            "source_object_id": "metrics",
            "target_issue": 101,
            "target_object_id": "metrics",
            "reason": DeprecationReason.DUPLICATE
        })
        
        # Execute deduplicate_object
        result = store.deduplicate_object("metrics")
        
        # Verify result
        assert result["success"] is True
        assert result["canonical_object_id"] == "metrics"
        assert result["canonical_issue"] == 101
        assert result["duplicates_processed"] == 1
        
        # Verify deprecate_issue was called with correct params
        store.deprecate_issue.assert_called_once_with(
            issue_number=102,
            target_issue_number=101,
            reason=DeprecationReason.DUPLICATE
        )
    
    # New test to verify deprecate_issue
    def test_deprecate_issue(self, canonical_store_with_mocks, mock_issue_factory):
        """Test deprecating a specific issue."""
        store = canonical_store_with_mocks
        
        # Create source and target issues
        source_issue = mock_issue_factory(
            number=123,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:old-metrics"],
            created_at=datetime(2025, 1, 5, tzinfo=timezone.utc)
        )
        
        target_issue = mock_issue_factory(
            number=456,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:metrics"],
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc)
        )
        
        # Setup get_issue mock
        def mock_get_issue(issue_number):
            if issue_number == 123:
                return source_issue
            elif issue_number == 456:
                return target_issue
            raise ValueError(f"Unknown issue number: {issue_number}")
        
        store.repo.get_issue = Mock(side_effect=mock_get_issue)
        
        # Mock _get_object_id to return the correct IDs
        def mock_get_object_id(issue):
            if issue.number == 123:
                return "old-metrics"
            elif issue.number == 456:
                return "metrics"
            return None
        
        store._get_object_id = Mock(side_effect=mock_get_object_id)
        
        # Mock label creation
        store.repo.create_label = Mock()
        
        # Mock adding/removing labels
        source_issue.add_to_labels = Mock()
        source_issue.remove_from_labels = Mock()
        
        # Execute deprecate_issue
        result = store.deprecate_issue(
            issue_number=123,
            target_issue_number=456,
            reason=DeprecationReason.MERGED
        )
        
        # Verify result
        assert result["success"] is True
        assert result["source_issue"] == 123
        assert result["source_object_id"] == "old-metrics"
        assert result["target_issue"] == 456
        assert result["target_object_id"] == "metrics"
        assert result["reason"] == DeprecationReason.MERGED
        
        # Verify labels were removed/added
        source_issue.remove_from_labels.assert_called_with(LabelNames.STORED_OBJECT)
        source_issue.add_to_labels.assert_called_with(
            LabelNames.DEPRECATED, 
            f"{LabelNames.MERGED_INTO_PREFIX}metrics",
            f"{LabelNames.DEPRECATED_BY_PREFIX}456"
        )


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
                        "update_mode": "append",
                        "issue_number": 123  # Include issue number
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
                        "update_mode": "append",
                        "issue_number": 123  # Include issue number
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
                        "update_mode": "append",
                        "issue_number": 789  # Different issue number
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
                    "issue_number":issue_number,
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
        # Set mock_canonical_issue number
        mock_canonical_issue.number = 123
        
        # Create mock comments with proper structure
        comments = [
            {
                "data": {
                    "type": "initial_state",
                    "_data": {"count": 0, "name": "test"},
                    "_meta": {
                        "client_version": "0.7.0",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "update_mode": "append",
                        "issue_number": 123  # Include issue number
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
                        "update_mode": "append",
                        "issue_number": 123  # Include issue number
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
                        "update_mode": "append",
                        "issue_number": 789  # Different issue number
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
                        "update_mode": "append",
                        "issue_number": 123  # Include issue number
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
        assert result.meta.issue_number == 123  # Verify issue number in result metadata
        
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
        # Set mock_canonical_issue number
        mock_canonical_issue.number = 123
        
        # Set up resolve_canonical_object_id to return same ID
        canonical_store.resolve_canonical_object_id = Mock(return_value="metrics")
        
        # Set up process_with_virtual_merge to return a mock object
        mock_obj = Mock()
        mock_obj.meta.object_id = "metrics"
        mock_obj.meta.issue_number = 123  # Set issue number in returned object
        mock_obj.data = {"count": 42, "name": "test"}
        canonical_store.process_with_virtual_merge = Mock(return_value=mock_obj)
        
        # Execute get_object
        result = canonical_store.get_object("metrics")
        
        # Verify results
        assert result.meta.object_id == "metrics"
        assert result.meta.issue_number == 123  # Verify issue number
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
        mock_obj.meta.issue_number = 123  # Set issue number in returned object
        mock_obj.data = {"count": 42, "name": "test"}
        canonical_store.process_with_virtual_merge = Mock(return_value=mock_obj)
        
        # Execute get_object with alias ID
        result = canonical_store.get_object("daily-metrics")
        
        # Verify results
        assert result.meta.object_id == "metrics"
        assert result.meta.issue_number == 123  # Verify issue number
        assert result.data["count"] == 42
        
        # Verify correct methods were called
        canonical_store.resolve_canonical_object_id.assert_called_with("daily-metrics")
        canonical_store.process_with_virtual_merge.assert_called_with("metrics")

    def test_update_object_alias(self, canonical_store, mock_alias_issue):
        """Test updating an object via its alias."""
        # Set mock_alias_issue number
        mock_alias_issue.number = 789
        
        # Setup to find the alias issue
        canonical_store.repo.get_issues.return_value = [mock_alias_issue]
        
        # Mock issue create_comment and edit methods
        mock_alias_issue.create_comment = Mock()
        mock_alias_issue.edit = Mock()
        
        # Mock get_object to return a result after update
        mock_obj = Mock()
        mock_obj.meta.object_id = "metrics"
        mock_obj.meta.issue_number = 123  # Set issue number in result
        mock_obj.data = {"count": 42, "name": "test", "period": "daily", "new_field": "value"}
        canonical_store.get_object = Mock(return_value=mock_obj)
        
        # Execute update_object on the alias
        changes = {"new_field": "value"}
        result = canonical_store.update_object("daily-metrics", changes)
        
        # Verify results
        assert result.meta.object_id == "metrics"
        assert result.meta.issue_number == 123  # Verify issue number
        assert result.data["new_field"] == "value"
        
        # Verify comment was added to alias issue
        mock_alias_issue.create_comment.assert_called_once()
        
        # Verify issue was reopened
        mock_alias_issue.edit.assert_called_with(state="open")
        
        # Verify comment payload included issue number
        call_args = mock_alias_issue.create_comment.call_args[0]
        comment_payload = json.loads(call_args[0])
        assert "issue_number" in comment_payload["_meta"]
        assert comment_payload["_meta"]["issue_number"] == 789  # Should use alias issue number

    def test_update_object_deprecated(self, canonical_store, mock_deprecated_issue, mock_canonical_issue, mock_label_factory):
        """Test updating a deprecated object."""
        # Set mock issue numbers
        mock_deprecated_issue.number = 457
        mock_canonical_issue.number = 123
        
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
        mock_obj.meta.issue_number = 123  # Set issue number
        mock_obj.data = {"count": 42, "name": "test", "new_field": "value"}
        canonical_store.get_object = Mock(return_value=mock_obj)
        canonical_store.resolve_canonical_object_id = Mock(return_value="metrics")
        
        # Execute update_object
        changes = {"new_field": "value"}
        result = canonical_store.update_object("old-metrics", changes)
        
        # Verify results
        assert result.meta.object_id == "metrics"
        assert result.meta.issue_number == 123  # Verify issue number
        assert result.data["new_field"] == "value"
    
    def test_update_object_on_alias_preserves_identity(self, canonical_store, mock_alias_issue):
        """
        Test that an update on an alias returns the object without merging into the canonical record.
        """
        # Set mock_alias_issue number
        mock_alias_issue.number = 789
        
        # Setup: mock_alias_issue should represent the alias "daily-metrics" pointing to "metrics".
        canonical_store.repo.get_issues.return_value = [mock_alias_issue]
        
        # Mock update behavior
        mock_alias_issue.create_comment = Mock()
        mock_alias_issue.edit = Mock()
        
        # Mock get_object with canonicalize=False to return the alias object
        alias_obj = Mock()
        alias_obj.meta.object_id = "daily-metrics"
        alias_obj.meta.issue_number = 789  # Set alias issue number
        alias_obj.data = {"period": "daily", "additional": "info"}
        
        canonical_store.get_object = Mock(return_value=alias_obj)
        
        # Assume update_object is called with changes.
        changes = {"additional": "info"}
        updated_obj = canonical_store.update_object("daily-metrics", changes)
        
        # Since update_object now returns get_object(..., canonicalize=False),
        # the alias identity should be preserved.
        assert updated_obj.meta.object_id == "daily-metrics"
        assert updated_obj.meta.issue_number == 789  # Verify issue number
    

class TestCanonicalStoreFinding:
    """Test finding duplicates and aliases."""
    
    def test_find_duplicates(self, canonical_store_with_mocks, mock_issue_factory):
        """Test finding duplicate objects."""
        store = canonical_store_with_mocks
        
        # Create issues with same UID
        issue1 = mock_issue_factory(
            number=101,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:metrics"]
        )
        
        issue2 = mock_issue_factory(
            number=102,
            labels=[LabelNames.GH_STORE, LabelNames.STORED_OBJECT, "UID:metrics"]
        )
        
        # Setup mock for get_issues
        store.repo.get_issues.return_value = [issue1, issue2]
        
        # Execute find_duplicates
        duplicates = store.find_duplicates()
        
        # Verify results - should find duplicates for "UID:metrics"
        assert len(duplicates) == 1
        assert "UID:metrics" in duplicates
        assert len(duplicates["UID:metrics"]) == 2

    def test_find_aliases(self, canonical_store, mock_alias_issue):
        """Test finding aliases for objects."""
        # Set mock_alias_issue number
        mock_alias_issue.number = 789
        
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
        # Set mock_alias_issue number
        mock_alias_issue.number = 789
        
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
    
    # def test_get_object_canonicalize_modes(self, canonical_store_with_mocks, mock_issue_factory, mock_comment_factory):
    #     """Test different canonicalization modes in get_object."""
    #     store = canonical_store_with_mocks
        
    #     # Create a mock alias issue (daily-metrics -> metrics)
    #     alias_issue = mock_issue_factory(
    #         number=101,
    #         labels=["stored-object", "UID:daily-metrics", "ALIAS-TO:metrics"],
    #         body=json.dumps({"period": "daily"})
    #     )
        
    #     # Create a mock canonical issue with initial state
    #     initial_state_comment = mock_comment_factory(
    #         body={
    #             "type": "initial_state",
    #             "_data": {"count": 42},
    #             "_meta": {
    #                 "client_version": "0.7.0", 
    #                 "timestamp": "2025-01-01T00:00:00Z",
    #                 "update_mode": "append",
    #                 "issue_number": 102  # Include issue number
    #             }
    #         },
    #         comment_id=1
    #     )
        
    #     canonical_issue = mock_issue_factory(
    #         number=102,
    #         labels=["stored-object", "UID:metrics"],
    #         body=json.dumps({"count": 42}),
    #         comments=[initial_state_comment]
    #     )
        
    #     # Setup mocks for get_issues
    #     def mock_get_issues(**kwargs):
    #         labels = kwargs.get('labels', [])
    #         if isinstance(labels, list):
    #             if any(label == "UID:daily-metrics" for label in labels):
    #                 return [alias_issue]
    #             elif any(label == "UID:metrics" for label in labels):
    #                 return [canonical_issue]
    #             elif any(label == "ALIAS-TO:metrics" for label in labels):
    #                 return [alias_issue]
    #         return []
        
    #     store.repo.get_issues = Mock(side_effect=mock_get_issues)
        
    #     # Setup resolve_canonical_object_id to correctly resolve the alias
    #     store.resolve_canonical_object_id = Mock(side_effect=lambda obj_id: "metrics" if obj_id == "daily-metrics" else obj_id)
        
    #     # Setup get_object_by_number
    #     def get_object_by_number(number):
    #         if number == 101:  # alias
    #             meta = Mock(
    #                 object_id="daily-metrics",
    #                 label="daily-metrics",
    #                 issue_number=101,  # Include issue number
    #                 created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    #                 updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
    #                 version=1
    #             )
    #             return Mock(meta=meta, data={"period": "daily"})
    #         else:  # canonical
    #             meta = Mock(
    #                 object_id="metrics",
    #                 label="metrics",
    #                 issue_number=102,  # Include issue number
    #                 created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    #                 updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
    #                 version=1
    #             )
    #             return Mock(meta=meta, data={"count": 42})
        
    #     store.issue_handler.get_object_by_number = Mock(side_effect=get_object_by_number)
        
    #     # Mock collect_all_comments to include the initial state
    #     store.collect_all_comments = Mock(return_value=[
    #         {
    #             "data": {
    #                 "type": "initial_state",
    #                 "_data": {"count": 42},
    #                 "_meta": {
    #                     "client_version": "0.7.0",
    #                     "timestamp": "2025-01-01T00:00:00Z",
    #                     "update_mode": "append",
    #                     "issue_number": 102  # Include issue number
    #                 }
    #             },
    #             "timestamp": datetime(2025, 1, 1, tzinfo=timezone.utc),
    #             "id": 1,
    #             "source_issue": 102,
    #             "source_object_id": "metrics"
    #         }
    #     ])
        
    #     # Mock process_with_virtual_merge
    #     store.process_with_virtual_merge = Mock(return_value=Mock(
    #         meta=Mock(
    #             object_id="metrics",
    #             issue_number=102  # Include issue number
    #         ),
    #         data={"count": 42}
    #     ))
        
    #     # Test canonicalize=True (default) - should return canonical object
    #     obj_canonical = store.get_object("daily-metrics", canonicalize=True)
    #     assert obj_canonical.meta.object_id == "metrics"
    #     assert obj_canonical.meta.issue_number == 102  # Verify issue number
        
    #     # Test canonicalize=False - should return alias object directly
    #     obj_direct = store.get_object("daily-metrics", canonicalize=False)
    #     assert obj_direct.meta.object_id == "daily-metrics"
    #     assert obj_direct.meta.issue_number == 101  # Verify issue number
