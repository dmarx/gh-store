# gh_store/handlers/issue_handler.py

import json
from datetime import datetime, timezone
from loguru import logger
from github import Repository
from omegaconf import DictConfig

from ..core.types import StoredObject, ObjectMeta, Json, CommentPayload, CommentMeta
from ..core.exceptions import ObjectNotFound, DuplicateUIDError, AliasedObjectError
from ..core.version import CLIENT_VERSION

from time import sleep
from github.GithubException import RateLimitExceededException

class IssueHandler:
    """Handles GitHub Issue operations for stored objects"""
    
    def __init__(self, repo: Repository.Repository, config: DictConfig):
        self.repo = repo
        self.config = config
        self.base_label = config.store.base_label
        self.uid_prefix = config.store.uid_prefix
    
    def create_object(self, object_id: str, data: Json) -> StoredObject:
        """Create a new issue to store an object"""
        logger.info(f"Creating new object: {object_id}")
        
        # Create uid label with prefix
        uid_label = f"{self.uid_prefix}{object_id}"
        
        # Ensure required labels exist
        self._ensure_labels_exist([self.base_label, uid_label])
        
        # Check for existing objects with this ID
        existing = list(self._with_retry(
            self.repo.get_issues,
            labels=[self.base_label, uid_label],
            state="all"
        ))
        
        if existing:
            # Filter out deprecated objects
            active_issues = [i for i in existing if not any(
                l.name == "deprecated-object" for l in i.labels
            )]
            
            if active_issues:
                # Check if any are canonical
                canonical_issues = [i for i in active_issues if any(
                    l.name == "canonical-object" for l in i.labels
                )]
                
                if canonical_issues:
                    # Object already exists and has a canonical issue
                    raise DuplicateUIDError(
                        f"Object with ID {object_id} already exists (#{canonical_issues[0].number})"
                    )
                else:
                    # Object exists but no canonical - we can make one later
                    pass
        
        # Create issue with object data and both required labels
        issue = self.repo.create_issue(
            title=f"Stored Object: {object_id}",
            body=json.dumps(data, indent=2),
            labels=[self.base_label, uid_label]
        )
        
        # Create initial state comment with metadata
        initial_state_comment = CommentPayload(
            _data=data,
            _meta=CommentMeta(
                client_version=CLIENT_VERSION,
                timestamp=datetime.now(timezone.utc).isoformat(),
                update_mode="append"
            ),
            type='initial_state'
        )
        
        comment = issue.create_comment(json.dumps(initial_state_comment.to_dict(), indent=2))
        
        # Mark as processed to prevent update processing
        comment.create_reaction(self.config.store.reactions.processed)
        comment.create_reaction(self.config.store.reactions.initial_state)
        
        # Create metadata
        meta = ObjectMeta(
            object_id=object_id,
            label=uid_label,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            version=1
        )
        
        # Close issue immediately to indicate no processing needed
        issue.edit(state="closed")
        
        return StoredObject(meta=meta, data=data)

    def _ensure_labels_exist(self, labels: list[str]) -> None:
        """Create labels if they don't exist"""
        existing_labels = {label.name for label in self.repo.get_labels()}
        
        for label in labels:
            if label not in existing_labels:
                logger.info(f"Creating label: {label}")
                self.repo.create_label(
                    name=label,
                    color="0366d6"  # GitHub's default blue
                )

    def _with_retry(self, func, *args, **kwargs):
        """Execute a function with retries on rate limit"""
        max_attempts = self.config.store.retries.max_attempts
        backoff = self.config.store.retries.backoff_factor
        
        for attempt in range(max_attempts):
            try:
                return func(*args, **kwargs)
            except RateLimitExceededException:
                if attempt == max_attempts - 1:
                    raise
                sleep(backoff ** attempt)
        
        raise RuntimeError("Should not reach here")

    def get_object(self, object_id: str) -> StoredObject:
        """Retrieve an object by its ID, handling aliases"""
        logger.info(f"Retrieving object: {object_id}")
        
        uid_label = f"{self.uid_prefix}{object_id}"
        
        # Query for issue with matching labels (start with closed issues)
        issues = list(self._with_retry(
            self.repo.get_issues,
            labels=[self.base_label, uid_label],
            state="closed"
        ))
        
        # If no closed issues found, try any state
        if not issues:
            issues = list(self._with_retry(
                self.repo.get_issues,
                labels=[self.base_label, uid_label],
                state="all"
            ))
        
        if not issues:
            raise ObjectNotFound(f"No object found with ID: {object_id}")
        elif len(issues) > 1:
            # Multiple issues found - check for a canonical one
            canonical_issues = [i for i in issues if any(
                l.name == "canonical-object" for l in i.labels
            )]
            
            if canonical_issues:
                # Use the canonical issue
                issue = canonical_issues[0]
            else:
                # No canonical issue designated, use oldest one
                issue = sorted(issues, key=lambda i: i.number)[0]
                issue_numbers = [i.number for i in issues]
                logger.warning(
                    f"Multiple issues ({issue_numbers}) with label: {uid_label}. "
                    f"Using oldest: #{issue.number}"
                )
        else:
            issue = issues[0]
        
        # Check if this is an alias
        is_alias = any(l.name == "alias-object" for l in issue.labels)
        alias_to = None
        
        if is_alias:
            # Find canonical issue reference
            for label in issue.labels:
                if label.name.startswith("ALIAS-TO:"):
                    try:
                        canonical_number = int(label.name.split(":")[1])
                        alias_to = canonical_number
                        break
                    except (ValueError, IndexError):
                        continue
            
            if alias_to:
                logger.info(f"Object {object_id} is an alias to #{alias_to}")
                try:
                    # Get the canonical issue
                    canonical_issue = self.repo.get_issue(alias_to)
                    
                    # Extract object ID from canonical issue
                    canonical_id = self.get_object_id_from_labels(canonical_issue)
                    
                    # Get the canonical object instead
                    return self.get_object(canonical_id)
                except Exception as e:
                    logger.warning(f"Failed to get canonical object: {e}")
                    # Fall back to returning alias object
            else:
                logger.warning(f"Issue #{issue.number} is marked as alias but no canonical reference found")
            
        data = json.loads(issue.body)
        
        meta = ObjectMeta(
            object_id=object_id,
            label=uid_label,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            version=self._get_version(issue)
        )
        
        return StoredObject(meta=meta, data=data)

    def get_object_history(self, object_id: str) -> list[dict]:
        """Get complete history of an object, including initial state"""
        logger.info(f"Retrieving history for object: {object_id}")
        
        uid_label = f"{self.uid_prefix}{object_id}"
        
        # Query for issue with matching labels
        issues = list(self._with_retry(
            self.repo.get_issues,
            labels=[self.base_label, uid_label],
            state="all"
        ))
        
        if not issues:
            raise ObjectNotFound(f"No object found with ID: {object_id}")
        
        # Check if this is an alias
        issue = issues[0]
        is_alias = any(l.name == "alias-object" for l in issue.labels)
        
        if is_alias:
            # Find canonical issue reference
            for label in issue.labels:
                if label.name.startswith("ALIAS-TO:"):
                    try:
                        canonical_number = int(label.name.split(":")[1])
                        # Get the canonical issue
                        canonical_issue = self.repo.get_issue(canonical_number)
                        # Extract object ID from canonical issue
                        canonical_id = self.get_object_id_from_labels(canonical_issue)
                        # Get history from canonical object
                        history = self.get_object_history(canonical_id)
                        logger.info(f"Returning history from canonical object: {canonical_id}")
                        return history
                    except (ValueError, IndexError, Exception) as e:
                        logger.warning(f"Failed to get canonical history: {e}")
                        # Fall back to alias history
        
        history = []
        
        # Process all comments chronologically
        for comment in issue.get_comments():
            try:
                comment_data = json.loads(comment.body)
                
                # Handle old format comments (backwards compatibility)
                if isinstance(comment_data, dict) and 'type' in comment_data and comment_data['type'] == 'initial_state':
                    # Old initial state format
                    comment_type = 'initial_state'
                    data = comment_data['data']
                elif isinstance(comment_data, dict) and '_data' in comment_data:
                    # New format
                    comment_type = comment_data.get('type', 'update')
                    data = comment_data['_data']
                else:
                    # Legacy update format (raw data)
                    comment_type = 'update'
                    data = comment_data

                # Build metadata
                if isinstance(comment_data, dict) and '_meta' in comment_data:
                    metadata = comment_data['_meta']
                else:
                    metadata = {
                        'client_version': 'legacy',
                        'timestamp': comment.created_at.isoformat(),
                        'update_mode': 'append'
                    }
                
                history.append({
                    "timestamp": comment.created_at.isoformat(),
                    "type": comment_type,
                    "data": data,
                    "comment_id": comment.id,
                    "metadata": metadata
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Skipping comment {comment.id}: {e}")
                
        return history
    
    def get_object_id_from_labels(self, issue) -> str:
        """
        Extract bare object ID from issue labels, removing any prefix.
        
        Args:
            issue: GitHub issue object with labels attribute
            
        Returns:
            str: Object ID without prefix
            
        Raises:
            ValueError: If no matching label is found
        """
        for label in issue.labels:
            # Get the actual label name, handling both string and Mock objects
            label_name = getattr(label, 'name', label)
            
            if (label_name != self.base_label and 
                isinstance(label_name, str) and 
                label_name.startswith(self.uid_prefix)):
                return label_name[len(self.uid_prefix):]
                
        raise ValueError(f"No UID label found with prefix {self.uid_prefix}")
        
    def get_object_by_number(self, issue_number: int) -> StoredObject:
        """Retrieve an object by issue number"""
        logger.info(f"Retrieving object by issue #{issue_number}")
        
        issue = self.repo.get_issue(issue_number)
        
        # Check if this is an alias
        is_alias = any(l.name == "alias-object" for l in issue.labels)
        
        if is_alias:
            # Find canonical issue reference
            for label in issue.labels:
                if label.name.startswith("ALIAS-TO:"):
                    try:
                        canonical_number = int(label.name.split(":")[1])
                        logger.info(f"Issue #{issue_number} is an alias to #{canonical_number}")
                        # Get the canonical issue
                        return self.get_object_by_number(canonical_number)
                    except (ValueError, IndexError, Exception) as e:
                        logger.warning(f"Failed to get canonical object: {e}")
                        # Fall back to alias object
        
        object_id = self.get_object_id_from_labels(issue)
        data = json.loads(issue.body)
        
        meta = ObjectMeta(
            object_id=object_id,
            label=object_id,
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            version=self._get_version(issue)
        )
        
        return StoredObject(meta=meta, data=data)

    def update_issue_body(self, issue_number: int, obj: StoredObject) -> None:
        """Update the issue body with new object state"""
        logger.info(f"Updating issue #{issue_number} with new state")
        
        issue = self.repo.get_issue(issue_number)
        issue.edit(
            body=json.dumps(obj.data, indent=2),
            state="closed"
        )

    def update_object(self, object_id: str, changes: Json) -> StoredObject:
        """Update an object by adding a comment and reopening the issue"""
        logger.info(f"Updating object: {object_id}")
        
        # Try to get the object to find its issue
        try:
            obj = self.get_object(object_id)
        except ObjectNotFound as e:
            raise e
            
        # Get the object's issue 
        uid_label = f"{self.config.store.uid_prefix}{object_id}"
        
        # Query for issue with matching labels
        issues = list(self.repo.get_issues(
            labels=[self.base_label, uid_label],
            state="all"
        ))
        
        if not issues:
            raise ObjectNotFound(f"No object found with ID: {object_id}")
        
        # Check for canonical issue
        canonical_issues = [i for i in issues if any(
            l.name == "canonical-object" for l in i.labels
        )]
        
        if canonical_issues:
            # Use the canonical issue
            issue = canonical_issues[0]
        else:
            # Check for aliases
            alias_issues = [i for i in issues if any(
                l.name == "alias-object" for l in i.labels
            )]
            
            if alias_issues:
                # Find canonical reference from first alias
                alias_issue = alias_issues[0]
                for label in alias_issue.labels:
                    if label.name.startswith("ALIAS-TO:"):
                        try:
                            canonical_number = int(label.name.split(":")[1])
                            # Get canonical issue
                            issue = self.repo.get_issue(canonical_number)
                            logger.info(f"Updating canonical issue #{issue.number} for alias {object_id}")
                            break
                        except (ValueError, IndexError):
                            pass
                else:
                    # No canonical found, use the first issue
                    issue = issues[0]
            else:
                # No aliases or canonicals, use the first issue
                issue = issues[0]
        
        # Create update payload with metadata
        update_payload = CommentPayload(
            _data=changes,
            _meta=CommentMeta(
                client_version=CLIENT_VERSION,
                timestamp=datetime.now(timezone.utc).isoformat(),
                update_mode="append"
            ),
            type=None
        )
        
        # Add update comment
        issue.create_comment(json.dumps(update_payload.to_dict(), indent=2))
        
        # Reopen issue to trigger processing
        issue.edit(state="open")
        
        # Return current state
        return self.get_object(object_id)

    def delete_object(self, object_id: str) -> None:
        """Delete an object by closing and archiving its issue"""
        logger.info(f"Deleting object: {object_id}")

        issues = list(self.repo.get_issues(
            labels=[self.base_label, object_id],
            state="all"
        ))

        if not issues:
            raise ObjectNotFound(f"No object found with ID: {object_id}")

        issue = issues[0]
        issue.edit(
            state="closed",
            labels=["archived", self.base_label, object_id]
        )

    def _get_version(self, issue) -> int:
        """Extract version number from issue"""
        comments = list(issue.get_comments())
        return len(comments) + 1
