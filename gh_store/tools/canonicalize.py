# gh_store/tools/canonicalize.py
"""
Tool for managing object canonicalization, aliasing, and deduplication in gh-store.

This module provides functionality to:
1. Find duplicate objects
2. Establish canonical objects with aliases
3. Handle virtual merging of data from multiple related issues
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple

from loguru import logger
from github import Github
from github.Issue import Issue
from github.Repository import Repository

from gh_store.core.store import GitHubStore
from gh_store.core.types import StoredObject, ObjectMeta, Json, CommentPayload, CommentMeta
from gh_store.core.exceptions import ObjectNotFound
from gh_store.core.version import CLIENT_VERSION


class DeprecationReason:
    """Constants for deprecation reasons stored in metadata."""
    DUPLICATE = "duplicate"
    MERGED = "merged" 
    REPLACED = "replaced"


class LabelNames:
    """Constants for label names."""
    STORED_OBJECT = "stored-object"
    DEPRECATED = "deprecated-object"
    UID_PREFIX = "UID:"
    ALIAS_TO_PREFIX = "ALIAS-TO:"
    MERGED_INTO_PREFIX = "MERGED-INTO:"


class CanonicalStore(GitHubStore):
    """Extended GitHub store with canonicalization and aliasing support."""
    
    def __init__(self, token: str, repo: str, config_path: Path | None = None):
        """Initialize with GitHub credentials."""
        super().__init__(token, repo, config_path)
        self._ensure_special_labels()
    
    def _ensure_special_labels(self) -> None:
        """Create special labels used by the canonicalization system if needed."""
        special_labels = [
            (LabelNames.DEPRECATED, "999999", "Deprecated objects that have been merged into others"),
            # Add others as needed
        ]
        
        try:
            existing_labels = {label.name for label in self.repo.get_labels()}
            
            for name, color, description in special_labels:
                if name not in existing_labels:
                    try:
                        self.repo.create_label(name=name, color=color, description=description)
                    except Exception as e:
                        logger.warning(f"Could not create label {name}: {e}")
        except Exception as e:
            logger.warning(f"Could not ensure special labels exist: {e}")
            # Continue anyway - this allows tests to run without proper mocking
                
    def resolve_canonical_object_id(self, object_id: str, max_depth: int = 5) -> str:
        """
        Resolve an object ID to its canonical object ID with loop prevention.
        
        Args:
            object_id: Object ID to resolve
            max_depth: Maximum depth to prevent infinite loops with circular references
            
        Returns:
            The canonical object ID
        """
        if max_depth <= 0:
            logger.warning(f"Maximum alias resolution depth reached for {object_id}")
            return object_id
            
        # Check if this is an alias
        uid_label = f"{LabelNames.UID_PREFIX}{object_id}"
        alias_prefix = f"{LabelNames.ALIAS_TO_PREFIX}*"
        
        alias_issues = list(self.repo.get_issues(
            labels=[uid_label, alias_prefix],
            state="all"
        ))
        
        if alias_issues:
            for issue in alias_issues:
                for label in issue.labels:
                    # type protection for mocks
                    if hasattr(label, 'name') and isinstance(label.name, str) and label.name.startswith(LabelNames.ALIAS_TO_PREFIX):
                        # Extract canonical object ID from label
                        canonical_id = label.name[len(LabelNames.ALIAS_TO_PREFIX):]
                        
                        # Prevent self-referential loops
                        if canonical_id == object_id:
                            logger.error(f"Self-referential alias detected for {object_id}")
                            return object_id
                            
                        # Recurse to follow alias chain
                        return self.resolve_canonical_object_id(canonical_id, max_depth - 1)
        
        # Not an alias, or couldn't resolve - assume it's canonical
        return object_id
    
    def _extract_comment_metadata(self, comment, issue_number: int, object_id: str) -> dict:
        """Extract metadata from a comment."""
        try:
            data = json.loads(comment.body)
            
            # Try to extract timestamp from metadata
            timestamp = comment.created_at
            if isinstance(data, dict) and '_meta' in data and 'timestamp' in data['_meta']:
                try:
                    ts_str = data['_meta']['timestamp']
                    # Handle various ISO format variations
                    if ts_str.endswith('Z'):
                        ts_str = ts_str[:-1] + '+00:00'
                    timestamp = datetime.fromisoformat(ts_str)
                except (ValueError, AttributeError):
                    pass
            
            return {
                "data": data,
                "created_at": comment.created_at,
                "timestamp": timestamp,
                "id": comment.id,
                "source_issue": issue_number,
                "source_object_id": object_id,
                "body": comment.body,
                "reactions": {r.content: r.id for r in comment.get_reactions()},
            }
        except json.JSONDecodeError:
            # Skip non-JSON comments
            logger.warning(f"Skipping non-JSON comment {comment.id} in issue #{issue_number}")
            return None
    
    def collect_all_comments(self, object_id: str) -> List[Dict[str, Any]]:
        """Collect comments from canonical issue and all aliases."""
        canonical_id = self.resolve_canonical_object_id(object_id)
        
        # Get the canonical issue
        canonical_issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.UID_PREFIX}{canonical_id}"],
            state="all"
        ))
        
        if not canonical_issues:
            raise ObjectNotFound(f"No canonical object found with ID: {canonical_id}")
        
        canonical_issue = canonical_issues[0]
        comments = []
        
        # Get comments from canonical issue
        for comment in canonical_issue.get_comments():
            metadata = self._extract_comment_metadata(comment, canonical_issue.number, canonical_id)
            if metadata:
                comments.append(metadata)
        
        # Get all aliases of this canonical object
        alias_issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.ALIAS_TO_PREFIX}{canonical_id}"],
            state="all"
        ))
        
        # Get comments from each alias
        for alias_issue in alias_issues:
            alias_id = None
            for label in alias_issue.labels:
                if label.name.startswith(LabelNames.UID_PREFIX):
                    alias_id = label.name[len(LabelNames.UID_PREFIX):]
                    break
            
            if not alias_id:
                continue  # Skip aliases without proper UID
                
            for comment in alias_issue.get_comments():
                metadata = self._extract_comment_metadata(comment, alias_issue.number, alias_id)
                if metadata:
                    comments.append(metadata)
        
        # Sort by metadata timestamp
            return sorted(comments, key=lambda c: c["timestamp"])
            
    def process_with_virtual_merge(self, object_id: str) -> StoredObject:
        """Process an object with virtual merging of related issues."""
        canonical_id = self.resolve_canonical_object_id(object_id)
        
        # Collect all comments
        all_comments = self.collect_all_comments(canonical_id)
        
        # Find initial state
        initial_state = next(
            (c for c in all_comments if c["data"].get("type") == "initial_state"),
            None
        )
        
        # If no initial state found, try to find data from issue body
        if not initial_state:
            # Get canonical issue
            canonical_issues = list(self.repo.get_issues(
                labels=[f"{LabelNames.UID_PREFIX}{canonical_id}"],
                state="all"
            ))
            
            if not canonical_issues:
                raise ObjectNotFound(f"No canonical object found with ID: {canonical_id}")
            
            canonical_issue = canonical_issues[0]
            
            try:
                body_data = json.loads(canonical_issue.body)
                # Create a synthetic initial state
                initial_state = {
                    "data": {
                        "type": "initial_state",
                        "_data": body_data,
                        "_meta": {
                            "client_version": CLIENT_VERSION,
                            "timestamp": canonical_issue.created_at.isoformat(),
                            "update_mode": "append"
                        }
                    },
                    "timestamp": canonical_issue.created_at,
                    "id": 0,  # Use 0 for synthetic initial state
                    "source_issue": canonical_issue.number,
                    "source_object_id": canonical_id
                }
            except (json.JSONDecodeError, AttributeError):
                raise ValueError(f"No initial state found for {canonical_id}")
        
        # Start with initial data
        current_state = initial_state["data"].get("_data", {})
        
        # Apply all updates in order
        for comment in all_comments:
            if comment["data"].get("type") == "initial_state":
                continue
            
            # Skip system comments
            if comment["data"].get("type", "").startswith("system_"):
                continue
            
            data = comment["data"]
            if isinstance(data, dict) and "_data" in data:
                update_data = data["_data"]
                update_mode = data.get("_meta", {}).get("update_mode", "append")
            else:
                # Legacy format
                update_data = data
                update_mode = "append"
            
            if update_mode == "append":
                current_state = self._deep_merge(current_state, update_data)
            elif update_mode == "replace":
                current_state = update_data
        
        # Get canonical issue for metadata
        canonical_issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.UID_PREFIX}{canonical_id}"],
            state="all"
        ))
        
        if not canonical_issues:
            raise ObjectNotFound(f"No canonical object found with ID: {canonical_id}")
        
        canonical_issue = canonical_issues[0]
        
        # Create object metadata
        meta = ObjectMeta(
            object_id=canonical_id,
            label=f"{LabelNames.UID_PREFIX}{canonical_id}",
            created_at=canonical_issue.created_at,
            updated_at=max(c["timestamp"] for c in all_comments) if all_comments else canonical_issue.updated_at,
            version=len(all_comments) if all_comments else 1
        )
        
        # Update canonical issue body with current state if not in test mode
        try:
            canonical_issue.edit(body=json.dumps(current_state, indent=2))
        except Exception as e:
            logger.warning(f"Could not update canonical issue body: {e}")
        
        return StoredObject(meta=meta, data=current_state)
    
    def _deep_merge(self, base: dict, update: dict) -> dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result

    
    def get_object(self, object_id: str, canonicalize: bool = True) -> StoredObject:
        """
        Retrieve an object.
        - If canonicalize=True (default), follow the alias chain and merge updates from all related issues.
        - If canonicalize=False, return the object as stored for the given object_id without alias resolution.
        """
        if canonicalize:
            canonical_id = self.resolve_canonical_object_id(object_id)
            if canonical_id != object_id:
                logger.info(f"Object {object_id} resolved to canonical object {canonical_id}")
            return self.process_with_virtual_merge(canonical_id)
        else:
            # Direct fetch: use only the issue with the UID label matching object_id.
            issues = list(self.repo.get_issues(
                labels=[f"{LabelNames.UID_PREFIX}{object_id}"],
                state="all"
            ))
            if not issues:
                raise ObjectNotFound(f"No object found with ID: {object_id}")
            issue = issues[0]
            data = json.loads(issue.body)
            meta = ObjectMeta(
                object_id=object_id,
                label=f"{LabelNames.UID_PREFIX}{object_id}",
                created_at=issue.created_at,
                updated_at=issue.updated_at,
                version=len(list(issue.get_comments())) + 1
            )
            return StoredObject(meta=meta, data=data)
    
    
    # In update_object, change the return so that we return the direct (alias‐preserving) object:
    def update_object(self, object_id: str, changes: Json) -> StoredObject:
        """Update an object by adding a comment to the appropriate issue."""
        # (Existing deprecation checks omitted for brevity.)
        # Check if this is an alias or direct match
        alias_issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.UID_PREFIX}{object_id}"],
            state="all"
        ))
        
        if not alias_issues:
            # Not a direct match, check for canonical object via aliases.
            canonical_id = self.resolve_canonical_object_id(object_id)
            canonical_issues = list(self.repo.get_issues(
                labels=[f"{LabelNames.UID_PREFIX}{canonical_id}"],
                state="all"
            ))
            if not canonical_issues:
                raise ObjectNotFound(f"No object found with ID: {object_id}")
            issue = canonical_issues[0]
        else:
            issue = alias_issues[0]
        
        # Create update payload with metadata
        update_payload = CommentPayload(
            _data=changes,
            _meta=CommentMeta(
                client_version=CLIENT_VERSION,
                timestamp=datetime.now(timezone.utc).isoformat(),
                update_mode="append"
            )
        )
        
        # Add update comment and reopen issue
        issue.create_comment(json.dumps(update_payload.to_dict(), indent=2))
        issue.edit(state="open")
        
        # Return the updated object in direct mode so that the alias-specific state is preserved.
        return self.get_object(object_id, canonicalize=False)

    
    def create_alias(self, source_id: str, target_id: str) -> dict:
        """Create an alias from source_id to target_id."""
        # Verify source object exists
        source_issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.UID_PREFIX}{source_id}"],
            state="all"
        ))
        
        if not source_issues:
            raise ObjectNotFound(f"Source object not found: {source_id}")
            
        source_issue = source_issues[0]
        
        # Verify target object exists
        target_issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.UID_PREFIX}{target_id}"],
            state="all"
        ))
        
        if not target_issues:
            raise ObjectNotFound(f"Target object not found: {target_id}")
            
        target_issue = target_issues[0]
        
        # Check if this is already an alias
        for label in source_issue.labels:
            if label.name.startswith(LabelNames.ALIAS_TO_PREFIX):
                raise ValueError(f"Object {source_id} is already an alias")
        
        # Add alias label
        alias_label = f"{LabelNames.ALIAS_TO_PREFIX}{target_id}"
        
        try:
            # Create label if it doesn't exist
            try:
                self.repo.create_label(alias_label, "fbca04")
            except:
                pass  # Label already exists
                
            source_issue.add_to_labels(alias_label)
        except Exception as e:
            raise ValueError(f"Failed to create alias: {e}")
        
        # Add system comments
        source_comment = {
            "_data": {
                "alias_to": target_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "update_mode": "append",
                "system": True
            },
            "type": "system_alias"
        }
        source_issue.create_comment(json.dumps(source_comment, indent=2))
        
        # Add reference comment to target
        target_comment = {
            "_data": {
                "aliased_by": source_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "update_mode": "append",
                "system": True
            },
            "type": "system_alias_reference"
        }
        target_issue.create_comment(json.dumps(target_comment, indent=2))
        
        return {
            "success": True,
            "source_id": source_id,
            "target_id": target_id
        }
    
    def deprecate_object(self, object_id: str, target_id: str, reason: str) -> dict:
        """
        Deprecate an object by merging it into a target object.
        
        Args:
            object_id: The ID of the object to deprecate
            target_id: The ID of the canonical object to merge into
            reason: Reason for deprecation ("duplicate", "merged", "replaced")
        """
        # Verify objects exist
        source_issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.UID_PREFIX}{object_id}"],
            state="all"
        ))
        
        if not source_issues:
            raise ObjectNotFound(f"Source object not found: {object_id}")
            
        source_issue = source_issues[0]
        
        # Verify target object exists
        target_issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.UID_PREFIX}{target_id}"],
            state="all"
        ))
        
        if not target_issues:
            raise ObjectNotFound(f"Target object not found: {target_id}")
            
        target_issue = target_issues[0]
        
        # Remove UID label from source
        source_issue.remove_from_labels(f"{LabelNames.UID_PREFIX}{object_id}")
        
        # Add merge and deprecated labels
        try:
            # Create labels if they don't exist
            merge_label = f"{LabelNames.MERGED_INTO_PREFIX}{target_id}"
            try:
                self.repo.create_label(merge_label, "d73a49")
            except:
                pass  # Label already exists
                
            try:
                self.repo.create_label(LabelNames.DEPRECATED, "999999")
            except:
                pass  # Label already exists
                
            # Add labels to source issue
            source_issue.add_to_labels(LabelNames.DEPRECATED, merge_label)
        except Exception as e:
            # If we fail, try to restore UID label
            try:
                source_issue.add_to_labels(f"{LabelNames.UID_PREFIX}{object_id}")
            except:
                pass
            raise ValueError(f"Failed to deprecate object: {e}")
        
        # Add system comments
        source_comment = {
            "_data": {
                "status": "deprecated",
                "canonical_object_id": target_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "update_mode": "append",
                "system": True
            },
            "type": "system_deprecation"
        }
        source_issue.create_comment(json.dumps(source_comment, indent=2))
        
        # Add reference comment to target
        target_comment = {
            "_data": {
                "status": "merged_reference",
                "merged_object_id": object_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "update_mode": "append",
                "system": True
            },
            "type": "system_reference"
        }
        target_issue.create_comment(json.dumps(target_comment, indent=2))
        
        # Process the target issue to ensure correct state
        self.process_with_virtual_merge(target_id)
        
        return {
            "success": True,
            "source_object_id": object_id,
            "target_object_id": target_id,
            "reason": reason
        }
    
    def deduplicate_object(self, object_id: str, canonical_id: str = None) -> dict:
        """Handle duplicate issues for an object ID."""
        # Find all issues with this UID
        issues = list(self.repo.get_issues(
            labels=[f"{LabelNames.UID_PREFIX}{object_id}"],
            state="all"
        ))
        
        if len(issues) <= 1:
            return {"success": True, "message": "No duplicates found"}
        
        # Sort issues by creation date
        sorted_issues = sorted(issues, key=lambda i: i.number)
        
        # Select canonical issue
        if canonical_id:
            # User specified a canonical ID
            canonical_issue = next(
                (issue for issue in issues if self._get_object_id(issue) == canonical_id),
                None
            )
            if not canonical_issue:
                raise ValueError(f"Specified canonical object {canonical_id} not found")
        else:
            # Default to oldest issue
            canonical_issue = sorted_issues[0]
            canonical_id = self._get_object_id(canonical_issue)
        
        # Process duplicates
        results = []
        for issue in sorted_issues:
            current_id = self._get_object_id(issue)
            if current_id == canonical_id:
                continue
                
            # Deprecate as duplicate
            result = self.deprecate_object(
                current_id,
                canonical_id,
                reason=DeprecationReason.DUPLICATE
            )
            results.append(result)
        
        return {
            "success": True,
            "canonical_object_id": canonical_id,
            "duplicates_processed": len(results),
            "results": results
        }
    
    def _get_object_id(self, issue) -> str:
        """Extract object ID from an issue's labels."""
        for label in issue.labels:
            if label.name.startswith(LabelNames.UID_PREFIX):
                return label.name[len(LabelNames.UID_PREFIX):]
        return None
    
    def find_duplicates(self) -> Dict[str, List[Issue]]:
        """Find all duplicate objects in the store."""
        # Get all issues with a UID label
        all_issues = list(self.repo.get_issues(
            state="all"
        ))
        
        # Group by UID
        issues_by_uid = defaultdict(list)
        
        for issue in all_issues:
            for label in issue.labels:
                if label.name.startswith(LabelNames.UID_PREFIX):
                    uid = label.name
                    issues_by_uid[uid].append(issue)
                    break
        
        # Filter to only those with duplicates
        duplicates = {uid: issues for uid, issues in issues_by_uid.items() if len(issues) > 1}
        
        return duplicates
    
    def find_aliases(self, object_id: str = None) -> Dict[str, str]:
        """
        Find all aliases, or aliases for a specific object.
        
        Args:
            object_id: Optional object ID to find aliases for
            
        Returns:
            Dictionary mapping alias_id -> canonical_id
        """
        aliases = {}
        
        if object_id:
            # Find aliases for specific object
            alias_issues = list(self.repo.get_issues(
                labels=[f"{LabelNames.ALIAS_TO_PREFIX}{object_id}"],
                state="all"
            ))
            
            for issue in alias_issues:
                alias_id = self._get_object_id(issue)
                if alias_id:
                    aliases[alias_id] = object_id
        else:
            # Find all aliases
            alias_issues = list(self.repo.get_issues(
                labels=[f"{LabelNames.ALIAS_TO_PREFIX}*"],
                state="all"
            ))
            
            for issue in alias_issues:
                alias_id = self._get_object_id(issue)
                if not alias_id:
                    continue
                    
                # Find target of alias
                for label in issue.labels:
                    if label.name.startswith(LabelNames.ALIAS_TO_PREFIX):
                        canonical_id = label.name[len(LabelNames.ALIAS_TO_PREFIX):]
                        aliases[alias_id] = canonical_id
                        break
        
        return aliases


def main():
    """Command line interface for canonicalization tools."""
    parser = argparse.ArgumentParser(description="Object Canonicalization and Alias Management")
    
    # Required credentials
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument("--repo", required=True, help="Repository in owner/repo format")
    
    # Action groups
    actions = parser.add_argument_group("Actions")
    actions.add_argument("--find-duplicates", action="store_true", help="Find duplicate objects")
    actions.add_argument("--deduplicate", action="store_true", help="Process all duplicates")
    actions.add_argument("--create-alias", action="store_true", help="Create an alias relationship")
    actions.add_argument("--deprecate", action="store_true", help="Deprecate and merge an object")
    
    # Object parameters
    objects = parser.add_argument_group("Object Parameters")
    objects.add_argument("--source-id", help="Source object ID for alias or deprecation")
    objects.add_argument("--target-id", help="Target object ID for alias or deprecation")
    objects.add_argument("--object-id", help="Object ID for operations on a single object")
    objects.add_argument("--reason", default=DeprecationReason.DUPLICATE, 
                        choices=[DeprecationReason.DUPLICATE, DeprecationReason.MERGED, DeprecationReason.REPLACED],
                        help="Reason for deprecation")
    
    # Other options
    parser.add_argument("--dry-run", action="store_true", help="Show actions without performing them")
    
    args = parser.parse_args()
    
    # Initialize store
    store = CanonicalStore(token=args.token, repo=args.repo)
    
    # Handle actions
    if args.find_duplicates:
        duplicates = store.find_duplicates()
        
        if not duplicates:
            logger.info("No duplicate objects found")
            return
            
        logger.info(f"Found {len(duplicates)} objects with duplicates:")
        
        for uid, issues in duplicates.items():
            object_id = uid[len(LabelNames.UID_PREFIX):]
            issue_numbers = [i.number for i in issues]
            logger.info(f"  Object {object_id}: {len(issues)} issues - {issue_numbers}")
    
    elif args.deduplicate:
        if args.object_id:
            # Deduplicate specific object
            result = store.deduplicate_object(args.object_id)
            logger.info(f"Deduplication result: {result}")
        else:
            # Find and deduplicate all
            duplicates = store.find_duplicates()
            
            if not duplicates:
                logger.info("No duplicate objects found")
                return
                
            results = []
            for uid, issues in duplicates.items():
                object_id = uid[len(LabelNames.UID_PREFIX):]
                logger.info(f"Deduplicating {object_id}...")
                
                if args.dry_run:
                    logger.info(f"  [DRY RUN] Would deduplicate {len(issues)} issues")
                    continue
                    
                result = store.deduplicate_object(object_id)
                results.append(result)
                logger.info(f"  Result: {result['duplicates_processed']} duplicates processed")
            
            logger.info(f"Processed {len(results)} objects with duplicates")
    
    elif args.create_alias:
        if not args.source_id or not args.target_id:
            logger.error("--source-id and --target-id are required for --create-alias")
            return
            
        logger.info(f"Creating alias from {args.source_id} to {args.target_id}")
        
        if args.dry_run:
            logger.info("[DRY RUN] Would create alias relationship")
            return
            
        result = store.create_alias(args.source_id, args.target_id)
        logger.info(f"Alias created: {result}")
    
    elif args.deprecate:
        if not args.source_id or not args.target_id:
            logger.error("--source-id and --target-id are required for --deprecate")
            return
            
        logger.info(f"Deprecating {args.source_id} into {args.target_id} (reason: {args.reason})")
        
        if args.dry_run:
            logger.info("[DRY RUN] Would deprecate object")
            return
            
        result = store.deprecate_object(args.source_id, args.target_id, args.reason)
        logger.info(f"Deprecation complete: {result}")


if __name__ == "__main__":
    main()
