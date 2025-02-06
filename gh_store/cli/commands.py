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
    """Helper to create GitHubStore instance with CLI parameters"""
    token = token or os.environ["GITHUB_TOKEN"]
    repo = repo or os.environ["GITHUB_REPOSITORY"]
    config_path = Path(config) if config else None
    
    if config_path:
        ensure_config_exists(config_path)
        
    return GitHubStore(token=token, repo=repo, config_path=config_path)

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

def get(
    object_id: str,
    output: str | None = None,
    token: str | None = None,
    repo: str | None = None,
    config: str | None = None,
) -> None:
    """Retrieve an object from the store"""
    try:
        store = get_store(token, repo, config)
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
