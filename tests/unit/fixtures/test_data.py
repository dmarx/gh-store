# tests/unit/fixtures/test_data.py
"""Standard test data for gh-store unit tests."""

from datetime import datetime, timezone
from typing import Any

# Common test objects
DEFAULT_TEST_DATA = {
    "name": "test",
    "value": 42,
    "_meta": {
        "client_version": "0.5.1",
        "timestamp": "2025-01-01T00:00:00Z",
        "update_mode": "append"
    }
}

SAMPLE_UPDATES = [
    {"value": 43},
    {"value": 44, "new_field": "test"},
    {"nested": {"field": "value"}}
]

SAMPLE_CONFIGS = {
    "minimal": {
        "store": {
            "base_label": "stored-object",
            "uid_prefix": "UID:",
            "reactions": {
                "processed": "+1",
                "initial_state": "rocket"
            }
        }
    },
    "full": {
        "store": {
            "base_label": "stored-object",
            "uid_prefix": "UID:",
            "reactions": {
                "processed": "+1",
                "initial_state": "rocket"
            },
            "retries": {
                "max_attempts": 3,
                "backoff_factor": 2
            },
            "rate_limit": {
                "max_requests_per_hour": 1000
            },
            "log": {
                "level": "INFO",
                "format": "{time} | {level} | {message}"
            }
        }
    }
}

def create_test_object(
    object_id: str,
    data: dict[str, Any] | None = None,
    **kwargs
) -> dict[str, Any]:
    """
    Create a standardized test object with metadata.
    
    Args:
        object_id: Unique object identifier
        data: Object data (uses DEFAULT_TEST_DATA if None)
        **kwargs: Additional metadata fields

    Returns:
        Dict containing object data and metadata
    """
    return {
        "object_id": object_id,
        "data": data or DEFAULT_TEST_DATA.copy(),
        "created_at": kwargs.get("created_at", datetime(2025, 1, 1, tzinfo=timezone.utc)),
        "updated_at": kwargs.get("updated_at", datetime(2025, 1, 2, tzinfo=timezone.utc)),
        "version": kwargs.get("version", 1)
    }

def create_update_sequence(
    base_data: dict[str, Any],
    updates: list[dict[str, Any]] | None = None,
    start_date: datetime | None = None
) -> list[dict[str, Any]]:
    """
    Create a sequence of updates with proper timestamps.
    
    Args:
        base_data: Initial object data
        updates: List of update payloads
        start_date: Starting timestamp for the sequence

    Returns:
        List of update payloads with timestamps
    """
    start = start_date or datetime(2025, 1, 1, tzinfo=timezone.utc)
    sequence = []
    
    # Add initial state
    sequence.append({
        "type": "initial_state",
        "_data": base_data,
        "_meta": {
            "client_version": "0.5.1",
            "timestamp": start.isoformat(),
            "update_mode": "append"
        }
    })
    
    # Add updates
    if updates:
        for i, update in enumerate(updates, start=1):
            sequence.append({
                "_data": update,
                "_meta": {
                    "client_version": "0.5.1",
                    "timestamp": (start + timedelta(days=i)).isoformat(),
                    "update_mode": "append"
                }
            })
    
    return sequence
