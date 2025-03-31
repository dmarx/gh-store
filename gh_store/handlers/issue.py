# gh_store/handlers/issue.py

from datetime import datetime, timezone
from loguru import logger
from github import Repository, Issue
import json
from omegaconf import DictConfig

from ..core.constants import LabelNames
from ..core.exceptions import ObjectNotFound, DuplicateUIDError
from ..core.types import StoredObject, ObjectMeta, Json, CommentPayload, CommentMeta
from ..core.version import CLIENT_VERSION
from .comment import CommentHandler


from time import sleep
from github.GithubException import RateLimitExceededException


class IssueHandler:
    """Handles GitHub Issue operations for stored objects"""
    
    def __init__(self, repo: Repository.Repository, config: DictConfig):
        self.repo = repo
        self.config = config
        self.base_label = LabelNames.STORED_OBJECT # could this be an OR?
            
    def create_object(self, object_id: str, data: Json) -> StoredObject:
        """Create a new issue to store an object"""
        logger.info(f"Creating new object: {object_id}")
        
        # Create uid label with prefix
        uid_label = f"{LabelNames.UID_PREFIX}{object_id}"
        
        # Get labels to apply - includes LabelNames.GH_STORE for system boundary
        # Note: The str() conversion is handled automatically due to our __str__ method
        labels_to_apply = [LabelNames.GH_STORE, self.base_label, uid_label]
        
        # Ensure required labels exist
        self._ensure_labels_exist(labels_to_apply)
        
        # Create issue with object data and all required labels
        issue = self.repo.create_issue(
            title=f"Stored Object: {object_id}",
            body=json.dumps(data, indent=2),
            labels=labels_to_apply
        )
        
        # Create initial state comment with metadata including issue number
        initial_state_comment = CommentHandler.create_comment_payload(
            data=data,
            issue_number=issue.number,  # Include issue number
            comment_type='initial_state'
        )
        
        comment = issue.create_comment(json.dumps(initial_state_comment.to_dict(), indent=2))
        
        # Mark as processed to prevent update processing
        comment.create_reaction(self.config.store.reactions.processed)
        comment.create_reaction(self.config.store.reactions.initial_state)

        # Close issue immediately to indicate no processing needed
        issue.edit(state="closed")

        # # Create metadata
        # meta = ObjectMeta(
        #     object_id=object_id,
        #     label=uid_label,
        #     issue_number=issue.number,  # Include issue number
        #     created_at=issue.created_at,
        #     updated_at=issue.updated_at,
        #     version=1
        # )
        
        # return StoredObject(meta=meta, data=data)
    
        return StoredObject.from_issue(issue, version=1)

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
        
        uid_label = f"{LabelNames.UID_PREFIX}{object_id}"
        
        # Query for issue with matching labels - must have stored-object (active)
        issues = list(self._with_retry(
            self.repo.get_issues,
            labels=[LabelNames.GH_STORE, self.base_label, uid_label],
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
        return StoredObject.from_issue(issue, version=self._get_version(issue))

    def get_object_history(self, object_id: str) -> list[dict]:
        """Get complete history of an object, including initial state"""
        logger.info(f"Retrieving history for object: {object_id}")
        
        uid_label = f"{LabelNames.UID_PREFIX}{object_id}"
        
        # Query for issue with matching labels
        issues = list(self._with_retry(
            self.repo.get_issues,
            labels=[LabelNames.GH_STORE, self.base_label, uid_label],
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
        
    def get_object_by_number(self, issue_number: int) -> StoredObject:
        """Retrieve an object by issue number"""
        logger.info(f"Retrieving object by issue #{issue_number}")
        
        issue = self.repo.get_issue(issue_number)
        return StoredObject.from_issue(issue, version=self._get_version(issue))


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
            labels=[LabelNames.GH_STORE, self.base_label, f"{LabelNames.UID_PREFIX}{object_id}"],
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
                issue_number=issue.number,  # Include issue number
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
            labels=[LabelNames.GH_STORE, self.base_label, f"{LabelNames.UID_PREFIX}{object_id}"],
            state="all"
        ))
        
        if not issues:
            raise ObjectNotFound(f"No object found with ID: {object_id}")
        
        issue = issues[0]
        issue.edit(
            state="closed",
            labels=[LabelNames.DELETED, LabelNames.GH_STORE, f"{LabelNames.UID_PREFIX}{object_id}"]
        )
        
        # Remove stored-object label to mark as inactive
        issue.remove_from_labels(self.base_label)

    def _get_version(self, issue) -> int:
        """Extract version number from issue"""
        comments = list(issue.get_comments())
        return len(comments) + 1
