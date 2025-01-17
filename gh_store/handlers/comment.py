# gh_store/handlers/comment.py

import json
from typing import Sequence
from loguru import logger
from github import Repository, IssueComment
from omegaconf import DictConfig

from ..core.types import StoredObject, Update
from ..core.exceptions import InvalidUpdate

class CommentHandler:
    """Handles processing of update comments"""
    
    def __init__(self, repo: Repository.Repository, config: DictConfig):
        self.repo = repo
        self.config = config
        self.processed_reaction = config.store.reactions.processed
        self.initial_state_reaction = config.store.reactions.initial_state

    def get_unprocessed_updates(self, issue_number: int) -> list[Update]:
        """Get all unprocessed updates from issue comments"""
        logger.info(f"Fetching unprocessed updates for issue #{issue_number}")
        
        issue = self.repo.get_issue(issue_number)
        updates = []
        
        for comment in issue.get_comments():
            if not self._is_processed(comment):
                try:
                    update_data = json.loads(comment.body)
                    
                    # Skip initial state comments - they shouldn't be processed as updates
                    if isinstance(update_data, dict) and update_data.get("type") == "initial_state":
                        logger.debug(f"Skipping initial state comment {comment.id}")
                        continue
                        
                    updates.append(Update(
                        comment_id=comment.id,
                        timestamp=comment.created_at,
                        changes=update_data if isinstance(update_data, dict) else {"data": update_data}
                    ))
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in comment {comment.id}: {e}")
                    raise InvalidUpdate(f"Comment {comment.id} contains invalid JSON")
        
        return sorted(updates, key=lambda u: u.timestamp)

    def apply_update(self, obj: StoredObject, update: Update) -> StoredObject:
        """Apply an update to an object"""
        logger.info(f"Applying update {update.comment_id} to {obj.meta.object_id}")
        
        # Deep merge the changes into the existing data
        updated_data = self._deep_merge(obj.data, update.changes)
        
        # Create new object with updated data and incremented version
        return StoredObject(
            meta=obj.meta,
            data=updated_data
        )

    def mark_processed(
        self, 
        issue_number: int,
        updates: Sequence[Update]
    ) -> None:
        """Mark comments as processed by adding reactions"""
        logger.info(f"Marking {len(updates)} comments as processed")
        
        issue = self.repo.get_issue(issue_number)
        
        for update in updates:
            for comment in issue.get_comments():
                if comment.id == update.comment_id:
                    comment.create_reaction(self.processed_reaction)
                    break

    def _is_processed(self, comment: IssueComment.IssueComment) -> bool:
        """Check if a comment has been processed"""
        for reaction in comment.get_reactions():
            if reaction.content == self.processed_reaction:
                return True
        return False

    def _deep_merge(self, base: dict, update: dict) -> dict:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
