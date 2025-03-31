# gh_store/core/types.py

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Self, TypeAlias
import json

from github import Issue

from .constants import LabelNames

Json: TypeAlias = dict[str, "Json"] | list["Json"] | str | int | float | bool | None


# This one method feels like it belongs on the IssueHandler, but really it pairs with StoredObject.from_issue
def get_object_id_from_labels(issue: Issue) -> str:
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
        # ... or are we just mocking poorly?
        label_name = getattr(label, 'name', label)
        
        if (isinstance(label_name, str) and label_name.startswith(LabelNames.UID_PREFIX)):
            return label_name[len(LabelNames.UID_PREFIX):]
            
    raise ValueError(f"No UID label found with prefix {LabelNames.UID_PREFIX}")

@dataclass
class ObjectMeta:
    """Metadata for a stored object"""
    object_id: str
    label: str
    issue_number: int  # Added field to track GitHub issue number
    created_at: datetime
    updated_at: datetime
    version: int

@dataclass
class StoredObject:
    """An object stored in the GitHub Issues store"""
    meta: ObjectMeta
    data: Json

    @classmethod
    def from_issue(cls, issue: Issue, version: int = 1) -> Self:
        object_id = get_object_id_from_labels(issue)
        data = json.loads(issue.body)
        meta = ObjectMeta(
            object_id=object_id,
            label=object_id,
            issue_number=issue.number,  # Include issue number
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            version=version,
        )
        return cls(meta=meta, data=data)

@dataclass
class Update:
    """An update to be applied to a stored object"""
    comment_id: int
    timestamp: datetime
    changes: Json

@dataclass
class CommentMeta:
    """Metadata included with each comment"""
    client_version: str
    timestamp: str
    update_mode: str
    issue_number: int  # Added field to track GitHub issue number
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

@dataclass
class CommentPayload:
    """Full comment payload structure"""
    _data: Json
    _meta: CommentMeta
    type: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "_data": self._data,
            "_meta": self._meta.to_dict(),
            **({"type": self.type} if self.type is not None else {})
        }
