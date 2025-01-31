# gh_store/handlers/comment.py

import json
from typing import Sequence
from datetime import datetime, timezone
from loguru import logger
from github import Repository, IssueComment
from omegaconf import DictConfig

from ..core.types import StoredObject, Update, CommentPayload, CommentMeta
from ..core.exceptions import InvalidUpdate
from ..core.access import AccessControl
from ..core.version import CLIENT_VERSION

class CommentHandler:
    """Handles processing of update comments"""
    
    def __init__(self, repo: Repository.Repository, config: DictConfig):
        self.repo = repo
        self.config = config
        self.processed_reaction = config.store.reactions.processed
        self.initial_state_reaction = config.store.reactions.initial_state
        self.access_control = AccessControl(repo)

    def _validate_metadata(self, metadata: dict) -> bool:
        """Validate that metadata contains all required fields"""
        return all(
            key in metadata and metadata[key] is not None
            for key in ['client_version', 'timestamp', 'update_mode']
        )

    def get_unprocessed_updates(self, issue_number: int) -> list[Update]:
        """Get all unprocessed updates from issue comments"""
        logger.info(f"Fetching unprocessed updates for issue #{issue_number}")
        
        issue = self.repo.get_issue(issue_number)
        updates = []
        
        for comment in issue.get_comments():
            if self._is_processed(comment):
                continue
                
            try:
                comment_payload = json.loads(comment.body)
                
                # Handle old format comments (backwards compatibility)
                if not isinstance(comment_payload, dict) or ('_data' not in comment_payload):
                    comment_payload = {
                        '_data': comment_payload,
                        '_meta': {
                            'client_version': 'legacy',
                            'timestamp': comment.created_at.isoformat(),
                            'update_mode': 'append'
                        }
                    }
                elif not self._validate_metadata(comment_payload.get('_meta', {})):
                    logger.warning(f"Skipping comment {comment.id} due to invalid metadata")
                    continue

                # Skip initial state comments
                if comment_payload.get('type') == 'initial_state':
                    logger.debug(f"Skipping initial state comment {comment.id}")
                    continue
                    
                # Skip comments from unauthorized users
                if not self.access_control.validate_comment_author(comment):
                    logger.debug(f"Skipping unauthorized comment {comment.id}")
                    continue
                    
                updates.append(Update(
                    comment_id=comment.id,
                    timestamp=comment.created_at,
                    changes=comment_payload['_data']
                ))
            except json.JSONDecodeError:
                # Not JSON, skip it
                logger.debug(f"Skipping non-JSON comment {comment.id}")
                continue
            except KeyError as e:
                logger.warning(f"Malformed comment payload in {comment.id}: {e}")
                continue
        
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

    def create_comment_payload(self, data: dict, comment_type: str | None = None) -> CommentPayload:
        """Create a properly structured comment payload"""
        meta = CommentMeta(
            client_version=CLIENT_VERSION,
            timestamp=datetime.now(timezone.utc).isoformat(),
            update_mode="append"
        )
        
        return CommentPayload(
            _data=data,
            _meta=meta,
            type=comment_type
        )

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
