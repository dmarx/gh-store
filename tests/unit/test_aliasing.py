# tests/unit/test_aliasing.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock, patch

from gh_store.core.exceptions import AliasedObjectError
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
    
    def test_find_duplicates_with_duplicates(self, mock_repo_factory, mock_issue_factory, mock_label_factory):
        """Test finding duplicates with multiple issues for the same object"""
        repo = mock_repo_factory()
        
        # Create issues with the same UID label
        issues = [
            mock_issue_factory(
                number=1,
                labels=["stored-object", "UID:test-1"]
            ),
            mock_issue_factory(
                number=2,
                labels=["stored-object", "UID:test-1"]
            ),
            mock_issue_factory(
                number=3,
                labels=["stored-object", "UID:test-2"]
            )
        ]
        
        repo.get_issues.return_value = issues
        
        duplicates = find_duplicates(repo)
        assert len(duplicates) == 1
        assert "UID:test-1" in duplicates
        assert duplicates["UID:test-1"] == [1, 2]
    
    def test_find_duplicates_skips_archived(self, mock_repo_factory, mock_issue_factory):
        """Test that archived issues are skipped"""
        repo = mock_repo_factory()
        
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
        
        repo.get_issues.return_value = issues
        
        duplicates = find_duplicates(repo)
        assert len(duplicates) == 0  # No duplicates since one is archived


class TestMarkDuplicates:
    """Test marking duplicate relationships"""
    
    def test_mark_duplicate_relationship(self, mock_repo_factory, mock_issue_factory):
        """Test marking a duplicate relationship"""
        repo = mock_repo_factory()
        
        # Mock issues
        canonical_issue = mock_issue_factory(
            number=1,
            labels=["stored-object", "UID:test-1"]
        )
        alias_issue = mock_issue_factory(
            number=2,
            labels=["stored-object", "UID:test-1"]
        )
        
        # Set up repository to return our mock issues
        repo.get_issue.side_effect = lambda num: canonical_issue if num == 1 else alias_issue
        
        # Mock label creation
        repo.create_label = Mock()
        
        # Call function
        result = mark_duplicate_relationship(repo, "test-1", 1, [2])
        
        # Verify canonical issue was marked
        canonical_issue.add_to_labels.assert_called_with("canonical-object")
        
        # Verify alias issue was marked
        alias_issue.add_to_labels.assert_called_with("alias-object")
        
        # Verify ALIAS-TO label was added
        assert any(call.args[0] == "ALIAS-TO:1" for call in alias_issue.add_to_labels.call_args_list)
        
        # Verify comments were added to both issues
        assert canonical_issue.create_comment.called
        assert alias_issue.create_comment.called
        
        # Verify result
        assert result["object_id"] == "test-1"
        assert result["canonical"] == 1
        assert result["aliases"] == [2]
        assert result["status"] == "success"


class TestAliasResolution:
    """Test resolving aliases to canonical objects"""
    
    def test_get_object_resolves_alias(self, store, mock_repo_factory, mock_issue_factory):
        """Test that get_object resolves aliases to canonical objects"""
        # Set up a canonical issue
        canonical_issue = mock_issue_factory(
            number=1,
            labels=["stored-object", "UID:metrics", "canonical-object"],
            body=json.dumps({"value": 42})
        )
        
        # Set up an alias issue
        alias_issue = mock_issue_factory(
            number=2,
            labels=["stored-object", "UID:daily-metrics", "alias-object", "ALIAS-TO:1"]
        )
        
        # Mock repository to return the right issues
        repo = mock_repo_factory()
        store.repo = repo
        
        def get_issues_side_effect(**kwargs):
            labels = kwargs.get("labels", [])
            if "UID:metrics" in labels:
                return [canonical_issue]
            elif "UID:daily-metrics" in labels:
                return [alias_issue]
            return []
            
        repo.get_issues.side_effect = get_issues_side_effect
        repo.get_issue.side_effect = lambda num: canonical_issue if num == 1 else alias_issue
        
        # Test getting the alias
        obj = store.get("daily-metrics")
        
        # Verify we got the canonical object's data
        assert obj.data == {"value": 42}
        assert obj.meta.object_id == "metrics"  # Should have the canonical ID
    
    def test_update_object_through_alias(self, store, mock_repo_factory, mock_issue_factory):
        """Test updating an object through its alias"""
        # Set up a canonical issue
        canonical_issue = mock_issue_factory(
            number=1,
            labels=["stored-object", "UID:metrics", "canonical-object"],
            body=json.dumps({"value": 42})
        )
        
        # Set up an alias issue
        alias_issue = mock_issue_factory(
            number=2,
            labels=["stored-object", "UID:daily-metrics", "alias-object", "ALIAS-TO:1"]
        )
        
        # Mock repository to return the right issues
        repo = mock_repo_factory()
        store.repo = repo
        
        def get_issues_side_effect(**kwargs):
            state = kwargs.get("state", "closed")
            labels = kwargs.get("labels", [])
            
            if state == "open":
                return []  # No open issues
                
            if "UID:metrics" in labels:
                return [canonical_issue]
            elif "UID:daily-metrics" in labels:
                return [alias_issue]
            return []
            
        repo.get_issues.side_effect = get_issues_side_effect
        repo.get_issue.side_effect = lambda num: canonical_issue if num == 1 else alias_issue
        
        # Update through the alias
        store.update("daily-metrics", {"value": 43})
        
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
    
    def test_create_alias(self, store, mock_repo_factory, mock_issue_factory):
        """Test creating a new alias to a canonical object"""
        # Set up a canonical issue
        canonical_issue = mock_issue_factory(
            number=1,
            labels=["stored-object", "UID:metrics"],
            body=json.dumps({"value": 42})
        )
        
        # Mock repository
        repo = mock_repo_factory()
        store.repo = repo
        
        # Set up get_issues to return canonical issue for metrics
        def get_issues_side_effect(**kwargs):
            labels = kwargs.get("labels", [])
            if "UID:metrics" in labels:
                return [canonical_issue]
            return []
            
        repo.get_issues.side_effect = get_issues_side_effect
        repo.get_issue.return_value = canonical_issue
        
        # Mock issue creation for alias
        alias_issue = mock_issue_factory(
            number=2,
            labels=[],
            body="{}"
        )
        repo.create_issue.return_value = alias_issue
        
        # Create the alias
        result = store.create_alias("metrics", "daily-metrics")
        
        # Verify canonical issue was marked
        canonical_issue.add_to_labels.assert_called_with("canonical-object")
        
        # Verify alias issue was created with right title and labels
        repo.create_issue.assert_called_once()
        call_kwargs = repo.create_issue.call_args[1]
        assert "Alias: daily-metrics" in call_kwargs["title"]
        assert "stored-object" in call_kwargs["labels"]
        assert "UID:daily-metrics" in call_kwargs["labels"]
        
        # Verify alias issue was marked correctly
        alias_issue.add_to_labels.assert_called_with("alias-object")
        
        # Verify ALIAS-TO label was created and added
        repo.create_label.assert_called_once()
        assert "ALIAS-TO:1" in repo.create_label.call_args[0]
        assert any(call.args[0] == "ALIAS-TO:1" for call in alias_issue.add_to_labels.call_args_list)
        
        # Verify result is the canonical object
        assert result.data == {"value": 42}
    
    def test_create_alias_to_nonexistent_object(self, store, mock_repo_factory):
        """Test creating an alias to a nonexistent object fails"""
        # Mock repository to return no issues
        repo = mock_repo_factory()
        store.repo = repo
        repo.get_issues.return_value = []
        
        # Try to create an alias to a nonexistent object
        with pytest.raises(Exception):  # Should raise ObjectNotFound
            store.create_alias("nonexistent", "alias")


class TestProcessUpdates:
    """Test processing updates with aliases"""
    
    def test_process_updates_includes_alias_comments(self, store, mock_repo_factory, mock_issue_factory, mock_comment_factory):
        """Test that process_updates includes comments from aliases"""
        # Create canonical issue
        canonical_issue = mock_issue_factory(
            number=1,
            labels=["stored-object", "UID:metrics", "canonical-object"],
            body=json.dumps({"value": 42})
        )
        
        # Create alias issue
        alias_issue = mock_issue_factory(
            number=2,
            labels=["stored-object", "UID:daily-metrics", "alias-object", "ALIAS-TO:1"],
            body=json.dumps({"alias_to": "metrics"})
        )
        
        # Create comments for both issues
        canonical_comment = mock_comment_factory(
            comment_id=101,
            user_login="repo-owner",
            body={
                "_data": {"canonical_update": True},
                "_meta": {
                    "client_version": "0.7.0",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "update_mode": "append"
                }
            }
        )
        
        alias_comment = mock_comment_factory(
            comment_id=102,
            user_login="repo-owner",
            body={
                "_data": {"alias_update": True},
                "_meta": {
                    "client_version": "0.7.0",
                    "timestamp": "2025-01-02T00:00:00Z",
                    "update_mode": "append"
                }
            }
        )
        
        # Set up comments on issues
        canonical_issue.get_comments.return_value = [canonical_comment]
        alias_issue.get_comments.return_value = [alias_comment]
        
        # Mock repository
        repo = mock_repo_factory()
        store.repo = repo
        repo.get_issue.side_effect = lambda num: canonical_issue if num == 1 else alias_issue
        
        # Mock issue_handler.find_aliases
        store.issue_handler.find_aliases = Mock(return_value=[2])
        
        # Mock issue_handler.get_object_by_number
        store.issue_handler.get_object_by_number = Mock()
        store.issue_handler.get_object_by_number.return_value = Mock(
            meta=Mock(object_id="metrics"),
            data={"value": 42}
        )
        
        # Mock comment_handler.get_unprocessed_updates
        def get_unprocessed_updates(issue_number):
            if issue_number == 1:
                return [Mock(comment_id=101, changes={"canonical_update": True})]
            else:
                return [Mock(comment_id=102, changes={"alias_update": True})]
                
        store.comment_handler.get_unprocessed_updates = Mock(side_effect=get_unprocessed_updates)
        
        # Mock comment_handler.apply_update
        store.comment_handler.apply_update = Mock()
        store.comment_handler.apply_update.side_effect = lambda obj, update: obj
        
        # Process updates
        store.process_updates(1)
        
        # Verify unprocessed updates were fetched from both issues
        store.comment_handler.get_unprocessed_updates.assert_any_call(1)
        store.comment_handler.get_unprocessed_updates.assert_any_call(2)
        
        # Verify all comments were marked as processed
        assert store.comment_handler.mark_processed.call_count == 2
    
    def test_process_updates_redirects_from_alias(self, store, mock_repo_factory, mock_issue_factory):
        """Test that process_updates redirects from alias to canonical issue"""
        # Create canonical issue
        canonical_issue = mock_issue_factory(
            number=1,
            labels=["stored-object", "UID:metrics", "canonical-object"],
            body=json.dumps({"value": 42})
        )
        
        # Create alias issue
        alias_issue = mock_issue_factory(
            number=2,
            labels=["stored-object", "UID:daily-metrics", "alias-object", "ALIAS-TO:1"],
            body=json.dumps({"alias_to": "metrics"})
        )
        
        # Mock repository
        repo = mock_repo_factory()
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
    
    def test_list_aliases(self, store, mock_repo_factory, mock_issue_factory):
        """Test listing all aliases"""
        # Create alias issues
        alias_issues = [
            mock_issue_factory(
                number=2,
                labels=["stored-object", "UID:daily-metrics", "alias-object", "ALIAS-TO:1"]
            ),
            mock_issue_factory(
                number=3,
                labels=["stored-object", "UID:weekly-metrics", "alias-object", "ALIAS-TO:1"]
            )
        ]
        
        # Create canonical issue
        canonical_issue = mock_issue_factory(
            number=1,
            labels=["stored-object", "UID:metrics", "canonical-object"]
        )
        
        # Mock repository
        repo = mock_repo_factory()
        store.repo = repo
        repo.get_issues.return_value = alias_issues
        repo.get_issue.return_value = canonical_issue
        
        # Mock get_object_id_from_labels
        store.issue_handler.get_object_id_from_labels = Mock()
        store.issue_handler.get_object_id_from_labels.side_effect = lambda issue: {
            1: "metrics",
            2: "daily-metrics",
            3: "weekly-metrics"
        }[issue.number]
        
        # List aliases
        aliases = store.list_aliases()
        
        # Verify results
        assert len(aliases) == 2
        assert "daily-metrics" in aliases
        assert "weekly-metrics" in aliases
        assert aliases["daily-metrics"]["id"] == "metrics"
        assert aliases["daily-metrics"]["issue"] == 1
        assert aliases["weekly-metrics"]["id"] == "metrics"
        assert aliases["weekly-metrics"]["issue"] == 1
    
    def test_list_aliases_for_specific_canonical(self, store, mock_repo_factory, mock_issue_factory):
        """Test listing aliases for a specific canonical object"""
        # Create alias issues for two different canonical objects
        alias_issues = [
            mock_issue_factory(
                number=2,
                labels=["stored-object", "UID:daily-metrics", "alias-object", "ALIAS-TO:1"]
            ),
            mock_issue_factory(
                number=3,
                labels=["stored-object", "UID:weekly-metrics", "alias-object", "ALIAS-TO:1"]
            ),
            mock_issue_factory(
                number=4,
                labels=["stored-object", "UID:daily-users", "alias-object", "ALIAS-TO:5"]
            )
        ]
        
        # Mock repository
        repo = mock_repo_factory()
        store.repo = repo
        repo.get_issues.return_value = alias_issues
        
        # Mock get_issue to return different canonical issues
        def get_issue_side_effect(num):
            if num == 1:
                return mock_issue_factory(
                    number=1,
                    labels=["stored-object", "UID:metrics", "canonical-object"]
                )
            else:
                return mock_issue_factory(
                    number=5,
                    labels=["stored-object", "UID:users", "canonical-object"]
                )
                
        repo.get_issue.side_effect = get_issue_side_effect
        
        # Mock get_object_id_from_labels
        store.issue_handler.get_object_id_from_labels = Mock()
        store.issue_handler.get_object_id_from_labels.side_effect = lambda issue: {
            1: "metrics",
            2: "daily-metrics",
            3: "weekly-metrics",
            4: "daily-users",
            5: "users"
        }[issue.number]
        
        # List aliases for metrics only
        aliases = store.list_aliases("metrics")
        
        # Verify results include only metrics aliases
        assert len(aliases) == 2
        assert "daily-metrics" in aliases
        assert "weekly-metrics" in aliases
        assert "daily-users" not in aliases
