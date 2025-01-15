# gh_store/core/store.py

from pathlib import Path
from loguru import logger
from github import Github
from omegaconf import OmegaConf

from .types import StoredObject, Update, Json
from ..handlers.issue import IssueHandler
from ..handlers.comment import CommentHandler

class GitHubStore:
    """Interface for storing and retrieving objects using GitHub Issues"""
    
    def __init__(self, token: str, repo: str, config_path: Path | None = None):
        """Initialize the store with GitHub credentials and optional config"""
        self.gh = Github(token)
        self.repo = self.gh.get_repo(repo)
        
        config_path = config_path or Path("config.yml")
        self.config = OmegaConf.load(config_path)
        
        self.issue_handler = IssueHandler(self.repo, self.config)
        self.comment_handler = CommentHandler(self.repo, self.config)
        
        logger.info(f"Initialized GitHub store for repository: {repo}")

    def create(self, object_id: str, data: Json) -> StoredObject:
        """Create a new object in the store"""
        return self.issue_handler.create_object(object_id, data)

    def get(self, object_id: str) -> StoredObject:
        """Retrieve an object from the store"""
        return self.issue_handler.get_object(object_id)

    def update(self, object_id: str, changes: Json) -> StoredObject:
        # Check if object is already being processed
        issues = list(self.repo.get_issues(
            labels=[self.config.store.base_label, object_id],
            state="open"
        ))
        
        if issues:
            raise ConcurrentUpdateError(f"Object {object_id} is currently being processed")
        """Update an existing object"""
        return self.issue_handler.update_object(object_id, changes)

    def delete(self, object_id: str) -> None:
        """Delete an object from the store"""
        self.issue_handler.delete_object(object_id)

    def process_updates(self, issue_number: int) -> StoredObject:
        """Process any unhandled updates on an issue"""
        logger.info(f"Processing updates for issue #{issue_number}")
        
        # Get all unprocessed comments
        updates = self.comment_handler.get_unprocessed_updates(issue_number)
        
        # Apply updates in sequence
        obj = self.issue_handler.get_object_by_number(issue_number)
        for update in updates:
            obj = self.comment_handler.apply_update(obj, update)
            
        # Persist final state and mark comments as processed
        self.issue_handler.update_issue_body(issue_number, obj)
        self.comment_handler.mark_processed(issue_number, updates)
        
        return obj
