# gh_store/core/store.py

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
import importlib.resources

from loguru import logger
from github import Github
from omegaconf import OmegaConf

from ..core.access import AccessControl
from ..core.constants import LabelNames
from ..handlers.issue import IssueHandler
from ..handlers.comment import CommentHandler
from .exceptions import AccessDeniedError, ConcurrentUpdateError
from .types import StoredObject, Update, Json


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "gh-store" / "config.yml"

class GitHubStore:
    """Interface for storing and retrieving objects using GitHub Issues"""
    
    def __init__(self, repo: str, token: str|None = None,  config_path: Path | None = None):
        """Initialize the store with GitHub credentials and optional config"""
        self.gh = Github(token)
        self.repo = self.gh.get_repo(repo)
        self.access_control = AccessControl(self.repo)
        
        config_path = config_path or DEFAULT_CONFIG_PATH
        if not config_path.exists():
            # If default config doesn't exist, but we have a packaged default, use that
            if config_path == DEFAULT_CONFIG_PATH:
                with importlib.resources.files('gh_store').joinpath('default_config.yml').open('rb') as f:
                    self.config = OmegaConf.load(f)
            else:
                raise FileNotFoundError(f"Config file not found: {config_path}")
        else:
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
        """Update an existing object"""
        # Check if object is already being processed
        issues = list(self.repo.get_issues(
            labels=[LabelNames.GH_STORE, self.config.store.base_label, f"UID:{object_id}"],
            state="open"
        ))
        
        if issues:
            raise ConcurrentUpdateError(f"Object {object_id} is currently being processed")
        
        return self.issue_handler.update_object(object_id, changes)

    def delete(self, object_id: str) -> None:
        """Delete an object from the store"""
        self.issue_handler.delete_object(object_id)
        
    def process_updates(self, issue_number: int) -> StoredObject:
        """Process any unhandled updates on an issue"""
        logger.info(f"Processing updates for issue #{issue_number}")
        
        issue = self.repo.get_issue(issue_number)
        if not self.access_control.validate_issue_creator(issue):
            raise AccessDeniedError(
                "Updates can only be processed for issues created by "
                "repository owner or authorized CODEOWNERS"
            )
        
        # Get all unprocessed comments - this handles comment-level auth
        updates = self.comment_handler.get_unprocessed_updates(issue_number)
        
        # Apply updates in sequence
        obj = self.issue_handler.get_object_by_number(issue_number)
        for update in updates:
            obj = self.comment_handler.apply_update(obj, update)
        
        # Persist final state and mark comments as processed
        self.issue_handler.update_issue_body(issue_number, obj)
        self.comment_handler.mark_processed(issue_number, updates)
        
        return obj
    
    def list_all(self) -> Iterator[StoredObject]:
        """List all objects in the store, indexed by object ID"""
        logger.info("Fetching all stored objects")
        
        # Get all closed issues with base label (active objects)
        issues_generator = self.repo.get_issues(
            state="closed",
            labels=[LabelNames.GH_STORE, self.config.store.base_label]
        )
        
        for idx, issue in enumerate(issues_generator):
            if any(label.name == "archived" for label in issue.labels):
                continue
            try:
                yield StoredObject.from_issue(issue)
            except ValueError as e:
                logger.warning(f"Skipping issue #{issue.number}: {e}")        
        logger.info(f"Found {idx+1} stored objects")

    def list_updated_since(self, timestamp: datetime) -> Iterator[StoredObject]:
        """List objects updated since given timestamp"""
        logger.info(f"Fetching objects updated since {timestamp}")
        
        # Get all objects with base label that are closed (active objects)
        # on the `since` parameter:
        #     "Only show results that were last updated after the given time. This is a timestamp in ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ."
        # https://docs.github.com/en/rest/issues/issues?apiVersion=2022-11-28#list-repository-issues
        issues_generator = self.repo.get_issues(
            state="closed",
            labels=[LabelNames.GH_STORE, self.config.store.base_label],
            since=timestamp 
        )

        # Get object ID from labels - strip prefix to get bare ID
        # object_id = self.issue_handler.get_object_id_from_labels(issue)
        
        # # Load object
        # obj = self.issue_handler.get_object_by_number(issue.number)
                
        for idx, issue in enumerate(issues_generator):
            if any(label.name == "archived" for label in issue.labels):
                continue
            try:
                obj = StoredObject.from_issue(issue)
                # Double check the timestamp (since GitHub's since parameter includes issue comments)
                # ....except, I think we want those, no? or do we only want objects whose updates have been "processed" into the view on the object?
                # Isn't this the function we use to figure out which comments need to be processed???
                # ...can't be, right? Because we're only querying for closed issues. 
                # So this must be for delta updating the snapshot.
                if obj.meta.updated_at > timestamp:
                    yield obj
                logger.info(f"Skipping issue #{issue.number}: failed `obj.meta.updated_at > timestamp` check.") 
                
            except ValueError as e:
                logger.warning(f"Skipping issue #{issue.number}: {e}")        
        logger.info(f"Found {idx+1} stored objects")
    
    def get_object_history(self, object_id: str) -> list[dict]:
        """Get complete history of an object"""
        return self.issue_handler.get_object_history(object_id)
