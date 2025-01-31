# gh_store/handlers/issue.py

import json
from datetime import datetime, timezone
from loguru import logger
from github import Repository
from omegaconf import DictConfig

from ..core.types import StoredObject, ObjectMeta, Json, CommentPayload, CommentMeta
from ..core.exceptions import ObjectNotFound, DuplicateUIDError
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
        """Retrieve an object by its ID"""
        logger.info(f"Retrieving object: {object_id}")
        
        uid_label = f"{self.uid_prefix}{object_id}"
        
        # Query for issue with matching labels
        issues = list(self._with_retry(
            self.repo.get_issues,
            labels=[self.base_label, uid_label],
            state="closed"
        ))
        
        if not issues:
            raise ObjectNotFound(f"No object found with ID: {object_id}")
        elif len(issues) > 1:
            issue_numbers = [i.number for i in issues]
            raise DuplicateUIDError(
                f"Found multiple issues ({issue_numbers}) with label: {uid_label}"
            )
        
        issue = issues[0]
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
            
        issue = issues[0]
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
        
        # Get the object's issue
        issues = list(self.repo.get_issues(
            labels=[self.base_label, object_id],
            state="closed"
        ))
        
        if not issues:
            raise ObjectNotFound(f"No object found with ID: {object_id}")
        
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
