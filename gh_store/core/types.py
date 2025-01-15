# gh_store/core/types.py

from dataclasses import dataclass
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
