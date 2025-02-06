# gh_store/core/types.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import TypeAlias

from .uid import UIDUtils

Json: TypeAlias = dict[str, "Json"] | list["Json"] | str | int | float | bool | None

@dataclass
class ObjectMeta:
    """Metadata for a stored object"""
    object_id: str  # Raw object ID without prefix
    created_at: datetime
    updated_at: datetime
    version: int
    _uid_utils: UIDUtils = field(repr=False)  # Not included in repr/comparison
    
    @property
    def label(self) -> str:
        """Get the GitHub label for this object (with prefix)"""
        return self._uid_utils.add_prefix(self.object_id)
    
    @classmethod
    def from_raw(cls, 
                object_id: str, 
                created_at: datetime,
                updated_at: datetime,
                version: int,
                uid_utils: UIDUtils) -> "ObjectMeta":
        """Create metadata from raw values, ensuring consistent ID format"""
        # Always store raw ID without prefix
        clean_id = uid_utils.remove_prefix(object_id)
        return cls(clean_id, created_at, updated_at, version, uid_utils)

@dataclass
class StoredObject:
    """An object stored in the GitHub Issues store"""
    meta: ObjectMeta
    data: Json

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

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "client_version": self.client_version,
            "timestamp": self.timestamp,
            "update_mode": self.update_mode
        }

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
