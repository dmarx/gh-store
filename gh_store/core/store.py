# gh_store/core/store.py

from datetime import datetime
from pathlib import Path
import importlib.resources

from loguru import logger
from github import Github
from omegaconf import OmegaConf

from ..core.access import AccessControl
from .exceptions import AccessDeniedError, ConcurrentUpdateError
from .types import StoredObject, Update, Json
from ..handlers.issue import IssueHandler
from ..handlers.comment import CommentHandler


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "gh-store" / "config.yml"

class GitHubStore:
    """Interface for storing and retrieving objects using GitHub Issues"""
    
    def __init__(self, token: str, repo: str, config_path: Path | None = None):
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
        uid_label = f"{self.config.store.uid_prefix}{object_id}"
        issues = list(self.repo.get_issues(
            labels=[self.config.store.base_label, uid_label],
            state="open"
        ))
        
        if issues:
            raise ConcurrentUpdateError(f"Object {object_id} is currently being processed")
            
        return self.issue_handler.update_object(object_id, changes)

    def delete(self, object_id: str) -> None:
        """Delete an object from the store"""
        self.issue_handler.delete_object(object_id)
        
    def process_updates(self, issue_number: int) -> StoredObject:
        """Process any unhandled updates on an issue and its aliases"""
        logger.info(f"Processing updates for issue #{issue_number}")
        
        issue = self.repo.get_issue(issue_number)
        if not self.access_control.validate_issue_creator(issue):
            raise AccessDeniedError(
                "Updates can only be processed for issues created by "
                "repository owner or authorized CODEOWNERS"
            )
        
        # Check if issue is canonical or alias
        is_canonical = any(label.name == "canonical-object" for label in issue.labels)
        
        # If it's an alias, find and process the canonical issue instead
        if not is_canonical:
            for label in issue.labels:
                if label.name.startswith("ALIAS-TO:"):
                    try:
                        canonical_number = int(label.name.split(":")[1])
                        logger.info(f"Redirecting to process canonical issue #{canonical_number}")
                        return self.process_updates(canonical_number)
                    except (ValueError, IndexError):
                        # If we can't parse the alias, continue with this issue
                        pass
        
        # Get all unprocessed comments from this issue
        updates = self.comment_handler.get_unprocessed_updates(issue_number)
        
        # If canonical, also collect updates from aliases
        if is_canonical:
            # Find all aliases
            alias_issues = self.issue_handler.find_aliases(issue_number)
            
            # Get updates from each alias
            for alias_number in alias_issues:
                try:
                    alias_issue = self.repo.get_issue(alias_number)
                    if not self.access_control.validate_issue_creator(alias_issue):
                        logger.warning(f"Skipping unauthorized alias issue #{alias_number}")
                        continue
                        
                    alias_updates = self.comment_handler.get_unprocessed_updates(alias_number)
                    updates.extend(alias_updates)
                except Exception as e:
                    logger.warning(f"Error processing alias #{alias_number}: {e}")
            
            # Resort all updates by timestamp
            updates.sort(key=lambda u: u.timestamp)
        
        # Apply updates in sequence
        obj = self.issue_handler.get_object_by_number(issue_number)
        for update in updates:
            obj = self.comment_handler.apply_update(obj, update)
        
        # Persist final state to issue
        self.issue_handler.update_issue_body(issue_number, obj)
        
        # Mark comments as processed on this issue
        this_issue_updates = [u for u in updates if any(
            c.id == u.comment_id for c in issue.get_comments()
        )]
        if this_issue_updates:
            self.comment_handler.mark_processed(issue_number, this_issue_updates)
            
        # Mark comments as processed on alias issues
        if is_canonical:
            for alias_number in alias_issues:
                try:
                    alias_issue = self.repo.get_issue(alias_number)
                    alias_updates = [u for u in updates if any(
                        c.id == u.comment_id for c in alias_issue.get_comments()
                    )]
                    if alias_updates:
                        self.comment_handler.mark_processed(alias_number, alias_updates)
                except Exception as e:
                    logger.warning(f"Error marking processed on alias #{alias_number}: {e}")
        
        return obj
    
    def list_all(self) -> dict[str, StoredObject]:
        """List all objects in the store, indexed by object ID"""
        logger.info("Fetching all stored objects")
        
        # Get all closed issues with base label
        issues = list(self.repo.get_issues(
            state="closed",
            labels=[self.config.store.base_label]
        ))
        
        objects = {}
        for issue in issues:
            # Skip archived objects or aliases
            if any(label.name in ["archived", "alias-object", "deprecated-object"] 
                  for label in issue.labels):
                continue
                
            try:
                # Get object ID from labels
                object_id = self.issue_handler.get_object_id_from_labels(issue)
                
                # Load object
                obj = self.issue_handler.get_object_by_number(issue.number)
                objects[object_id] = obj
                
            except ValueError as e:
                logger.warning(f"Skipping issue #{issue.number}: {e}")
        
        logger.info(f"Found {len(objects)} stored objects")
        return objects
    
    def list_updated_since(self, timestamp: datetime) -> dict[str, StoredObject]:
        """List objects updated since given timestamp"""
        logger.info(f"Fetching objects updated since {timestamp}")
        
        # Get all objects with base label that are closed
        issues = list(self.repo.get_issues(
            state="closed",
            labels=[self.config.store.base_label],
            since=timestamp  # GitHub API's since parameter
        ))
        
        objects = {}
        for issue in issues:
            # Skip archived objects or aliases
            if any(label.name in ["archived", "alias-object", "deprecated-object"] 
                  for label in issue.labels):
                continue
                
            try:
                # Get object ID from labels - strip prefix to get bare ID
                object_id = self.issue_handler.get_object_id_from_labels(issue)
                
                # Load object
                obj = self.issue_handler.get_object_by_number(issue.number)
                
                # Double check the timestamp (since GitHub's since parameter includes issue comments)
                if obj.meta.updated_at > timestamp:
                    objects[object_id] = obj
                
            except ValueError as e:
                logger.warning(f"Skipping issue #{issue.number}: {e}")
        
        logger.info(f"Found {len(objects)} updated objects")
        return objects
        
    def get_object_history(self, object_id: str) -> list[dict]:
        """Get the complete history of an object, including from aliases"""
        return self.issue_handler.get_object_history(object_id)
        
    def create_alias(self, canonical_id: str, alias_id: str) -> StoredObject:
        """Create a new alias to a canonical object"""
        return self.issue_handler.create_alias(canonical_id, alias_id)
        
    def list_aliases(self, canonical_id: str = None) -> dict:
        """List all aliases in the store"""
        # Get all alias objects
        alias_issues = list(self.repo.get_issues(
            state="all",
            labels=["alias-object"]
        ))
        
        results = {}
        
        for issue in alias_issues:
            try:
                # Get alias ID
                alias_id = self.issue_handler.get_object_id_from_labels(issue)
                
                # Find canonical reference
                canonical_ref = None
                for label in issue.labels:
                    if label.name.startswith("ALIAS-TO:"):
                        try:
                            canonical_number = int(label.name.split(":")[1])
                            canonical_issue = self.repo.get_issue(canonical_number)
                            canonical_id = self.issue_handler.get_object_id_from_labels(canonical_issue)
                            canonical_ref = {
                                "id": canonical_id, 
                                "issue": canonical_number
                            }
                            break
                        except (ValueError, IndexError):
                            pass
                
                if canonical_ref and (canonical_id is None or canonical_ref["id"] == canonical_id):
                    results[alias_id] = canonical_ref
                    
            except ValueError:
                continue
                
        return results
