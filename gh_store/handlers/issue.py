# gh_store/handlers/issue.py

import json
from datetime import datetime
from loguru import logger
from github import Repository
from omegaconf import DictConfig

from ..core.types import StoredObject, ObjectMeta, Json
from ..core.exceptions import ObjectNotFound

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

    def _get_object_id(self, issue) -> str:
        """Extract object ID from issue labels"""
        for label in issue.labels:
            if label.name != self.base_label and label.name.startswith(self.uid_prefix):
                return label.name[len(self.uid_prefix):]  # Remove prefix to get ID
        raise ValueError("No UID label found")
        
    def get_object_by_number(self, issue_number: int) -> StoredObject:
        """Retrieve an object by issue number"""
        logger.info(f"Retrieving object by issue #{issue_number}")
        
        issue = self.repo.get_issue(issue_number)
        object_id = self._get_object_id(issue)
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
        
        # Add update comment
        issue.create_comment(json.dumps(changes, indent=2))
        
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

    def _get_object_id(self, issue) -> str:
        """Extract object ID from issue labels"""
        for label in issue.labels:
            if label.name != self.base_label:
                return label.name
        raise ValueError("No object ID label found")
