# tests/unit/test_aliasing.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch, ANY

from gh_store.core.exceptions import AliasedObjectError, ObjectNotFound
from gh_store.tools.find_duplicates import find_duplicates
from gh_store.tools.mark_duplicates import mark_duplicate_relationship


class TestDuplicateDetection:
    """Test finding duplicate objects in the repository"""
    
    def test_find_duplicates_empty(self, mock_repo_factory):
        """Test when there are no duplicates"""
        repo = mock_repo_factory()
        repo.get_issues.return_value = []
        
        duplicates = find_duplicates(repo)
        assert len(duplicates) == 0
    
    def test_find_duplicates_with_duplicates(self, mock_repo_factory, duplicate_issues):
        """Test finding duplicates with multiple issues for the same object"""
        repo = mock_repo_factory()
        repo.get_issues.return_value = duplicate_issues
        
        duplicates = find_duplicates(repo)
        assert len(duplicates) == 1
        assert "UID:duplicate-id" in duplicates
        assert sorted(duplicates["UID:duplicate-id"]) == [1, 2, 3]
    
    def test_find_duplicates_skips_archived(self, mock_issue_factory, mock_repo_factory):
        """Test that archived issues are skipped"""
        # Create issues with the same UID label, but one is archived
        issues = [
            mock_issue_factory(
                number=1,
                labels=["stored-object", "UID:test-1"]
            ),
            mock_issue_factory(
                number=2,
                labels=["stored-object", "UID:test-1", "archived"]
            )
        ]
        
        repo = mock_repo_factory()
        repo.get_issues.return_value = issues
        
        duplicates = find_duplicates(repo)
        assert len(duplicates) == 0  # No duplicates since one is archived


class TestMarkDuplicates:
    """Test marking duplicate relationships"""
    
    def test_mark_duplicate_relationship(self, mock_repo_factory, duplicate_issues):
        """Test marking a duplicate relationship"""
        repo = mock_repo_factory()
        
        # Setup repository to return our mock issues
        canonical_issue = duplicate_issues[0]
        alias_issues = duplicate_issues[1:]
        
        # Set up repository to return our mock issues
        repo.get_issue.side_effect = lambda num: next((i for i in duplicate_issues if i.number == num), None)
        
        # Mock label creation
        repo.create_label = Mock()
        
        # Call function
        result = mark_duplicate_relationship(repo, "duplicate-id", 1, [2, 3])
        
        # Verify canonical issue was marked
        canonical_issue.add_to_labels.assert_called_with("canonical-object")
        
        # Verify alias issues were marked with "alias-object"
        for alias_issue in alias_issues:
            alias_issue.add_to_labels.assert_any_call("alias-object")
            assert any(call.args[0] == "ALIAS-TO:1" for call in alias_issue.add_to_labels.call_args_list)
        
        # Verify comments were added to all issues
        assert canonical_issue.create_comment.called
        for alias_issue in alias_issues:
            assert alias_issue.create_comment.called
        
        # Verify result
        assert result["object_id"] == "duplicate-id"
        assert result["canonical"] == 1
        assert result["aliases"] == [2, 3]
        assert result["status"] == "success"


class TestAliasResolution:
    """Test resolving aliases to canonical objects"""
    
    def test_get_object_resolves_alias(self, store):
        """Test that get_object resolves aliases to canonical objects"""
        # Create canonical issue
        canonical_issue = Mock()
        canonical_issue.body = json.dumps({"value": 42})
        canonical_issue.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        canonical_issue.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        canonical_issue.labels = [
            Mock(name="stored-object"),
            Mock(name="UID:canonical-id"),
            Mock(name="canonical-object")
        ]
        canonical_issue.get_comments = Mock(return_value=[])
        
        # Create alias issue
        alias_issue = Mock()
        alias_issue.body = json.dumps({"alias_to": "canonical-id"})
        alias_issue.created_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        alias_issue.updated_at = datetime(2025, 1, 3, tzinfo=timezone.utc)
        alias_issue.labels = [
            Mock(name="stored-object"),
            Mock(name="UID:alias-id"),
            Mock(name="alias-object"),
            Mock(name="ALIAS-TO:1")
        ]
        alias_issue.get_comments = Mock(return_value=[])
        
        # Mock repository to return the right issues
        def get_issues_side_effect(**kwargs):
            labels = kwargs.get("labels", [])
            if "UID:canonical-id" in labels:
                return [canonical_issue]
            elif "UID:alias-id" in labels:
                return [alias_issue]
            return []
        
        store.repo.get_issues.side_effect = get_issues_side_effect
        store.repo.get_issue.side_effect = lambda num: canonical_issue if num == 1 else alias_issue
        
        # Mock IssueHandler.get_object_by_number
        def get_object_by_number_side_effect(number):
            if number == 1:
                # Return canonical object
                meta = Mock()
                meta.object_id = "canonical-id"
                meta.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
                meta.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
                meta.version = 1
                return Mock(meta=meta, data={"value": 42})
            else:
                raise ValueError(f"Unexpected issue number: {number}")
        
        store.issue_handler.get_object_by_number = Mock(side_effect=get_object_by_number_side_effect)
        
        # Mock get_object_id_from_labels
        store.issue_handler.get_object_id_from_labels = Mock(side_effect=lambda issue: "canonical-id" if issue == canonical_issue else "alias-id")
        
        # Test getting the alias
        obj = store.get("alias-id")
        
        # Verify we got the canonical object's data
        assert obj.data == {"value": 42}
        assert obj.meta.object_id == "canonical-id"  # Should have the canonical ID
    
    def test_update_object_through_alias(self, store):
        """Test updating an object through its alias"""
        # Create canonical issue
        canonical_issue = Mock()
        canonical_issue.body = json.dumps({"value": 42})
        canonical_issue.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        canonical_issue.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        canonical_issue.labels = [
            Mock(name="stored-object"),
            Mock(name="UID:canonical-id"),
            Mock(name="canonical-object")
        ]
        canonical_issue.get_comments = Mock(return_value=[])
        
        # Create alias issue
        alias_issue = Mock()
        alias_issue.body = json.dumps({"alias_to": "canonical-id"})
        alias_issue.created_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
        alias_issue.updated_at = datetime(2025, 1, 3, tzinfo=timezone.utc)
        alias_issue.state = "closed"
        alias_issue.labels = [
            Mock(name="stored-object"),
            Mock(name="UID:alias-id"),
            Mock(name="alias-object"),
            Mock(name="ALIAS-TO:1")
        ]
        alias_issue.get_comments = Mock(return_value=[])
        
        # Mock repository
        def get_issues_side_effect(**kwargs):
            state = kwargs.get("state", "closed")
            labels = kwargs.get("labels", [])
            
            if state == "open":
                return []  # No open issues
                
            if "UID:canonical-id" in labels:
                return [canonical_issue]
            elif "UID:alias-id" in labels:
                return [alias_issue]
            return []
            
        store.repo.get_issues.side_effect = get_issues_side_effect
        store.repo.get_issue.side_effect = lambda num: canonical_issue if num == 1 else alias_issue
        
        # Mock IssueHandler.get_object_by_number
        def get_object_by_number_side_effect(number):
            if number == 1:
                # Return canonical object
                meta = Mock()
                meta.object_id = "canonical-id"
                meta.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
                meta.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
                meta.version = 1
                return Mock(meta=meta, data={"value": 42})
            else:
                raise ValueError(f"Unexpected issue number: {number}")
        
        store.issue_handler.get_object_by_number = Mock(side_effect=get_object_by_number_side_effect)
        
        # Mock get_object_id_from_labels
        store.issue_handler.get_object_id_from_labels = Mock(side_effect=lambda issue: "canonical-id" if issue == canonical_issue else "alias-id")
        
        # Update through the alias
        store.update("alias-id", {"value": 43})
        
        # Verify the comment was added to the canonical issue
        assert canonical_issue.create_comment.called
        
        # Get the comment content
        comment_args = canonical_issue.create_comment.call_args[0]
        comment_data = json.loads(comment_args[0])
        
        # Verify it has the right data
        assert "_data" in comment_data
        assert comment_data["_data"] == {"value": 43}


class TestCreateAlias:
    """Test creating aliases"""
    
    def test_create_alias(self, store):
        """Test creating a new alias to a canonical object"""
        # Patch the IssueHandler.create_alias method
        with patch.object(store.issue_handler, 'create_alias') as mock_create_alias:
            # Set up mock return value
            meta = Mock()
            meta.object_id = "canonical-id"
            meta.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            meta.updated_at = datetime(2025, 1, 2, tzinfo=timezone.utc)
            meta.version = 1
            mock_create_alias.return_value = Mock(meta=meta, data={"value": 42})
            
            # Create the alias
            result = store.create_alias("canonical-id", "new-alias-id")
            
            # Verify the method was called with correct args
            mock_create_alias.assert_called_once_with("canonical-id", "new-alias-id")
            
            # Verify the result
            assert result.data == {"value": 42}
    
    def test_create_alias_to_nonexistent_object(self, store, mock_repo_factory):
        """Test creating an alias to a nonexistent object fails"""
        # Mock repository to return no issues
        repo = mock_repo_factory()
        store.repo = repo
        repo.get_issues.return_value = []
        
        # Try to create an alias to a nonexistent object
        with pytest.raises(ObjectNotFound):
            store.create_alias("nonexistent", "alias")


class TestProcessUpdates:
    """Test processing updates with aliases"""
    
    def test_process_updates_includes_alias_comments(self, store):
        """Test that process_updates includes comments from aliases"""
        # Create canonical issue
        canonical_issue = Mock()
        canonical_issue.number = 1
        canonical_issue.labels = [
            Mock(name="stored-object"),
            Mock(name="UID:canonical-id"),
            Mock(name="canonical-object")
        ]
        canonical_issue.user = Mock(login="repo-owner")
        
        # Create alias issue
        alias_issue = Mock()
        alias_issue.number = 2
        alias_issue.labels = [
            Mock(name="stored-object"),
            Mock(name="UID:alias-id"),
            Mock(name="alias-object"),
            Mock(name="ALIAS-TO:1")
        ]
        alias_issue.user = Mock(login="repo-owner")
        
        # Create update comments with real timestamp objects
        canonical_update = Mock(
            comment_id=202,
            timestamp=datetime(2025, 1, 2, tzinfo=timezone.utc),
            changes={"from_canonical": True, "value": 60}
        )
        
        alias_update = Mock(
            comment_id=201,
            timestamp=datetime(2025, 1, 3, tzinfo=timezone.utc),
            changes={"from_alias": True, "value": 50}
        )
        
        # Mock repository
        repo = Mock()
        store.repo = repo
        repo.get_issue.side_effect = lambda num: canonical_issue if num == 1 else alias_issue
        
        # Mock issue_handler.find_aliases
        store.issue_handler.find_aliases = Mock(return_value=[2])
        
        # Mock issue_handler.get_object_by_number
        mock_obj = Mock()
        mock_obj.meta = Mock(object_id="canonical-id")
        mock_obj.data = {"value": 42}
        store.issue_handler.get_object_by_number = Mock(return_value=mock_obj)
        
        # Mock comment_handler.get_unprocessed_updates
        def get_unprocessed_updates(issue_number):
            if issue_number == 1:
                return [canonical_update]
            else:
                return [alias_update]
                
        store.comment_handler.get_unprocessed_updates = Mock(side_effect=get_unprocessed_updates)
        
        # Mock comment_handler.apply_update to return the original object
        store.comment_handler.apply_update = Mock(return_value=mock_obj)
        
        # Mock comment_handler.mark_processed
        store.comment_handler.mark_processed = Mock()
        
        # Setup comments on issues for testing processed workflow
        canonical_issue.get_comments = Mock(return_value=[
            Mock(id=202)  # Matching canonical_update.comment_id
        ])
        alias_issue.get_comments = Mock(return_value=[
            Mock(id=201)  # Matching alias_update.comment_id
        ])
        
        # Process updates
        store.process_updates(1)
        
        # Verify unprocessed updates were fetched from both issues
        store.comment_handler.get_unprocessed_updates.assert_any_call(1)
        store.comment_handler.get_unprocessed_updates.assert_any_call(2)
        
        # Verify updates were applied in chronological order
        assert store.comment_handler.apply_update.call_count == 2
        
        # Verify issue body was updated
        store.issue_handler.update_issue_body.assert_called_once()
        
        # Verify all comments were marked as processed
        store.comment_handler.mark_processed.assert_any_call(1, [canonical_update])
        store.comment_handler.mark_processed.assert_any_call(2, [alias_update])
    
    def test_process_updates_redirects_from_alias(self, store):
        """Test that process_updates redirects from alias to canonical issue"""
        # Create canonical issue
        canonical_issue = Mock()
        canonical_issue.number = 1
        canonical_issue.labels = [
            Mock(name="stored-object"),
            Mock(name="UID:canonical-id"),
            Mock(name="canonical-object")
        ]
        canonical_issue.user = Mock(login="repo-owner")
        
        # Create alias issue
        alias_issue = Mock()
        alias_issue.number = 2
        alias_issue.labels = [
            Mock(name="stored-object"),
            Mock(name="UID:alias-id"),
            Mock(name="alias-object"),
            Mock(name="ALIAS-TO:1")
        ]
        alias_issue.user = Mock(login="repo-owner")
        
        # Mock repository
        repo = Mock()
        store.repo = repo
        repo.get_issue.side_effect = lambda num: canonical_issue if num == 1 else alias_issue
        
        # Setup process_updates to track calls
        original_process_updates = store.process_updates
        process_calls = []
        
        def mock_process_updates(issue_number):
            process_calls.append(issue_number)
            if issue_number == 2:  # Only intercept alias call
                return original_process_updates(issue_number)
            return Mock()
            
        with patch.object(store, 'process_updates', side_effect=mock_process_updates):
            # Process the alias issue
            store.process_updates(2)
            
            # Verify it was redirected to process the canonical issue
            assert process_calls == [2, 1]


class TestListAliases:
    """Test listing aliases"""
    
    def test_list_aliases(self, store):
        """Test listing all aliases"""
        # Create alias issues
        alias_issues = [
            Mock(
                number=2,
                labels=[
                    Mock(name="stored-object"),
                    Mock(name="UID:alias-id"),
                    Mock(name="alias-object"),
                    Mock(name="ALIAS-TO:1")
                ]
            ),
            Mock(
                number=3,
                labels=[
                    Mock(name="stored-object"),
                    Mock(name="UID:secondary-alias-id"),
                    Mock(name="alias-object"),
                    Mock(name="ALIAS-TO:1")
                ]
            )
        ]
        
        # Create canonical issue
        canonical_issue = Mock(
            number=1,
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:canonical-id"),
                Mock(name="canonical-object")
            ]
        )
        
        # Mock repository
        repo = Mock()
        store.repo = repo
        repo.get_issues.return_value = alias_issues
        repo.get_issue.return_value = canonical_issue
        
        # Mock get_object_id_from_labels
        store.issue_handler.get_object_id_from_labels = Mock()
        store.issue_handler.get_object_id_from_labels.side_effect = lambda issue: {
            1: "canonical-id",
            2: "alias-id",
            3: "secondary-alias-id"
        }[issue.number]
        
        # List aliases
        aliases = store.list_aliases()
        
        # Verify results
        assert len(aliases) == 2
        assert "alias-id" in aliases
        assert "secondary-alias-id" in aliases
        assert aliases["alias-id"]["id"] == "canonical-id"
        assert aliases["alias-id"]["issue"] == 1
        assert aliases["secondary-alias-id"]["id"] == "canonical-id"
        assert aliases["secondary-alias-id"]["issue"] == 1
        
    def test_list_aliases_for_specific_canonical(self, store):
        """Test listing aliases for a specific canonical object"""
        # Create alias issues
        alias_issues = [
            Mock(
                number=2,
                labels=[
                    Mock(name="stored-object"),
                    Mock(name="UID:alias-id"),
                    Mock(name="alias-object"),
                    Mock(name="ALIAS-TO:1")
                ]
            ),
            Mock(
                number=3,
                labels=[
                    Mock(name="stored-object"),
                    Mock(name="UID:secondary-alias-id"),
                    Mock(name="alias-object"),
                    Mock(name="ALIAS-TO:1")
                ]
            )
        ]
        
        # Mock repository
        repo = Mock()
        store.repo = repo
        repo.get_issues.return_value = alias_issues
        
        # Mock get_issue to return different canonical issues
        def get_issue_side_effect(num):
            if num == 1:
                return Mock(
                    number=1,
                    labels=[
                        Mock(name="stored-object"),
                        Mock(name="UID:canonical-id"),
                        Mock(name="canonical-object")
                    ]
                )
            else:
                return Mock(
                    number=5,
                    labels=[
                        Mock(name="stored-object"),
                        Mock(name="UID:users"),
                        Mock(name="canonical-object")
                    ]
                )
                
        repo.get_issue.side_effect = get_issue_side_effect
        
        # Mock get_object_id_from_labels
        store.issue_handler.get_object_id_from_labels = Mock()
        store.issue_handler.get_object_id_from_labels.side_effect = lambda issue: {
            1: "canonical-id",
            2: "alias-id",
            3: "secondary-alias-id",
            4: "daily-users",
            5: "users"
        }[issue.number]
        
        # List aliases for canonical-id only
        aliases = store.list_aliases("canonical-id")
        
        # Verify results include both aliases for canonical-id
        assert len(aliases) == 2
        assert "alias-id" in aliases
        assert "secondary-alias-id" in aliases
