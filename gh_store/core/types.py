# gh_store/core/types.py

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import TypeAlias

Json: TypeAlias = dict[str, "Json"] | list["Json"] | str | int | float | bool | None

@dataclass
class ObjectMeta:
    """Metadata for a stored object"""
    object_id: str
    label: str
    created_at: datetime
    updated_at: datetime
    version: int

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
