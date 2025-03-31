# gh_store/cli/commands.py

import os
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
import importlib.resources
from typing import Any
from loguru import logger

from ..core.store import GitHubStore
from ..core.exceptions import GitHubStoreError, ConfigurationError
from ..core.types import Json


def ensure_config_exists(config_path: Path) -> None:
    """Create default config file if it doesn't exist"""
    if not config_path.exists():
        logger.info(f"Creating default configuration at {config_path}")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy default config from package
        with importlib.resources.files('gh_store').joinpath('default_config.yml').open('rb') as src:
            with open(config_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
        
        logger.info("Default configuration created. You can modify it at any time.")

def get_store(token: str | None = None, repo: str | None = None, config: str | None = None) -> GitHubStore:
    """Helper to create GitHubStore instance with CLI parameters using keyword arguments"""
    token = token or os.environ["GITHUB_TOKEN"]
    repo = repo or os.environ["GITHUB_REPOSITORY"]
    config_path = Path(config) if config else None
    
    if config_path:
        ensure_config_exists(config_path)
        
    return GitHubStore(token=token, repo=repo, config_path=config_path)

def get(
    object_id: str,
    output: str | None = None,
    token: str | None = None,
    repo: str | None = None,
    config: str | None = None,
) -> None:
    """Retrieve an object from the store"""
    try:
        store = get_store(token=token, repo=repo, config=config)
        obj = store.get(object_id)
        
        # Format output
        result = {
            "object_id": obj.meta.object_id,
            "created_at": obj.meta.created_at.isoformat(),
            "updated_at": obj.meta.updated_at.isoformat(),
            "version": obj.meta.version,
            "data": obj.data
        }
        
        if output:
            Path(output).write_text(json.dumps(result, indent=2))
            logger.info(f"Object written to {output}")
        else:
            print(json.dumps(result, indent=2))
            
    except Exception as e:
        logger.exception("Failed to get object")
        raise SystemExit(1)

def create(
    object_id: str,
    data: str,
    token: str | None = None,
    repo: str | None = None,
    config: str | None = None,
) -> None:
    """Create a new object in the store"""
    try:
        store = get_store(token, repo, config)
        # Parse data as JSON
        data_dict = json.loads(data)
        obj = store.create(object_id, data_dict)
        logger.info(f"Created object {obj.meta.object_id}")
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON data provided")
        raise SystemExit(1)
    except Exception as e:
        logger.exception("Failed to create object")
        raise SystemExit(1)

def update(
    object_id: str,
    changes: str,
    token: str | None = None,
    repo: str | None = None,
    config: str | None = None,
) -> None:
    """Update an existing object"""
    try:
        store = get_store(token, repo, config)
        # Parse changes as JSON
        changes_dict = json.loads(changes)
        obj = store.update(object_id, changes_dict)
        logger.info(f"Updated object {obj.meta.object_id}")
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON changes provided")
        raise SystemExit(1)
    except Exception as e:
        logger.exception("Failed to update object")
        raise SystemExit(1)

def delete(
    object_id: str,
    token: str | None = None,
    repo: str | None = None,
    config: str | None = None,
) -> None:
    """Delete an object from the store"""
    try:
        store = get_store(token, repo, config)
        store.delete(object_id)
        logger.info(f"Deleted object {object_id}")
        
    except Exception as e:
        logger.exception("Failed to delete object")
        raise SystemExit(1)

def get_history(
    object_id: str,
    output: str | None = None,
    token: str | None = None,
    repo: str | None = None,
    config: str | None = None,
) -> None:
    """Get complete history of an object"""
    try:
        store = get_store(token, repo, config)
        history = store.get_object_history(object_id)
        
        if output:
            Path(output).write_text(json.dumps(history, indent=2))
            logger.info(f"History written to {output}")
        else:
            print(json.dumps(history, indent=2))
            
    except Exception as e:
        logger.exception("Failed to get object history")
        raise SystemExit(1)

# Adding to gh_store/cli/commands.py

def process_updates(
    issue: int,
    token: str | None = None,
    repo: str | None = None,
    config: str | None = None,
) -> None:
    """Process pending updates for a stored object"""
    try:
        store = get_store(token, repo, config)
        obj = store.process_updates(issue)
        logger.info(f"Successfully processed updates for {obj.meta.object_id}")
        
    except GitHubStoreError as e:
        logger.error(f"Failed to process updates: {e}")
        raise SystemExit(1)
    except Exception as e:
        logger.exception("Unexpected error occurred")
        raise SystemExit(1)

def snapshot(
    token: str | None = None,
    repo: str | None = None,
    output: str = "snapshot.json",
    config: str | None = None,
) -> None:
    """Create a full snapshot of all objects in the store, including relationship info."""
    try:
        store = get_store(token, repo, config)
        
        # Use CanonicalStore if available for enhanced relationship handling
        has_canonical = False
        canonical_store = None
        
        try:
            from gh_store.tools.canonicalize import CanonicalStore
            canonical_store = CanonicalStore(token, repo, config_path=Path(config) if config else None)
            has_canonical = True
        except ImportError:
            logger.warning("Canonical store functionality not available")
        except Exception as e:
            logger.warning(f"Error initializing canonical store: {e}")
        
        # Create snapshot data
        snapshot_data = {
            "snapshot_time": datetime.now(ZoneInfo("UTC")).isoformat(),
            "repository": repo or os.environ.get("GITHUB_REPOSITORY", ""),
            "objects": {},
        }
        
        # Add relationships data if CanonicalStore is available
        if has_canonical and canonical_store:
            try:
                # Find all aliases
                aliases = canonical_store.find_aliases()
                if aliases:
                    snapshot_data["relationships"] = {
                        "aliases": aliases
                    }
            except Exception as e:
                logger.warning(f"Error finding aliases: {e}")
        
        # Add objects to snapshot
        object_count = 0
        for obj in store.list_all():
            object_count += 1
            snapshot_data["objects"][obj.meta.object_id] = {
                "data": obj.data,
                "meta": {
                    "issue_number": obj.meta.issue_number,
                    "object_id": obj.meta.object_id, # there's also an obj.meta.label field we can probably just drop?
                    "created_at": obj.meta.created_at.isoformat(),
                    "updated_at": obj.meta.updated_at.isoformat(),
                    "version": obj.meta.version,
                }
            }
        
        # Write to file
        output_path = Path(output)
        output_path.write_text(json.dumps(snapshot_data, indent=2))
        logger.info(f"Snapshot written to {output_path}")
        logger.info(f"Captured {object_count} objects")
        
        if has_canonical and "relationships" in snapshot_data:
            aliases_count = len(snapshot_data["relationships"].get("aliases", {}))
            logger.info(f"Included {aliases_count} alias relationships")
        
    except GitHubStoreError as e:
        logger.error(f"Failed to create snapshot: {e}")
        raise SystemExit(1)
    except Exception as e:
        logger.exception("Unexpected error occurred")
        raise SystemExit(1)

def update_snapshot(
    snapshot_path: str,
    token: str | None = None,
    repo: str | None = None,
    config: str | None = None,
) -> None:
    """Update an existing snapshot with changes since its creation"""
    try:
        store = get_store(token, repo, config)
        
        # Read existing snapshot
        snapshot_path = Path(snapshot_path)
        if not snapshot_path.exists():
            raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")
        
        with open(snapshot_path) as f:
            snapshot_data = json.loads(f.read())
        
        # Parse snapshot timestamp
        last_snapshot = datetime.fromisoformat(snapshot_data["snapshot_time"])
        logger.info(f"Updating snapshot from {last_snapshot}")
        
        # Track updated objects count
        updated_count = 0
        
        # Get updated objects and add them to snapshot
        for obj in store.list_updated_since(last_snapshot):
            updated_count += 1
            snapshot_data["objects"][obj.meta.object_id] = {
                "data": obj.data,
                "meta": {
                    "issue_number": obj.meta.issue_number,
                    "object_id": obj.meta.object_id, # there's also an obj.meta.label field we can probably just drop?
                    "created_at": obj.meta.created_at.isoformat(),
                    "updated_at": obj.meta.updated_at.isoformat(),
                    "version": obj.meta.version,
                }
            }
        
        # Update snapshot timestamp
        snapshot_data["snapshot_time"] = datetime.now(ZoneInfo("UTC")).isoformat()
        
        # Write updated snapshot
        snapshot_path.write_text(json.dumps(snapshot_data, indent=2))
        logger.info(f"Updated {updated_count} objects in snapshot")
        
    except GitHubStoreError as e:
        logger.error(f"Failed to update snapshot: {e}")
        raise e
    except Exception as e:
        logger.exception("Unexpected error occurred")
        raise e
