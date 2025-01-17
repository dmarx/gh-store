# gh_store/__main__.py

from pathlib import Path
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import importlib.resources
import shutil
import fire
from loguru import logger

from .core.store import GitHubStore
from .core.exceptions import GitHubStoreError, ConfigurationError

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

class CLI:
    """GitHub Issue Store CLI"""
    
    def __init__(self):
        """Initialize CLI with default config path"""
        self.default_config_path = Path.home() / ".config" / "gh-store" / "config.yml"
    
    def process_updates(
        self,
        issue: int,
        token: str,
        repo: str,
        config: str | None = None
    ) -> None:
        """Process pending updates for a stored object"""
        try:
            # Use provided config path or default
            config_path = Path(config) if config else self.default_config_path
            
            # Ensure config exists
            ensure_config_exists(config_path)
            
            logger.info(f"Processing updates for issue #{issue}")
            
            store = GitHubStore(token=token, repo=repo, config_path=config_path)
            obj = store.process_updates(issue)
            
            logger.info(f"Successfully processed updates for {obj.meta.object_id}")
            
        except GitHubStoreError as e:
            logger.error(f"Failed to process updates: {e}")
            raise SystemExit(1)
        except Exception as e:
            logger.exception("Unexpected error occurred")
            raise SystemExit(1)

    def snapshot(
        self,
        token: str,
        repo: str,
        output: str = "snapshot.json",
        config: str | None = None
    ) -> None:
        """Create a full snapshot of all objects in the store"""
        try:
            # Use provided config path or default
            config_path = Path(config) if config else self.default_config_path
            
            # Ensure config exists
            ensure_config_exists(config_path)
            
            store = GitHubStore(token=token, repo=repo, config_path=config_path)
            
            # Get all stored objects
            objects = store.list_all()
            
            # Create snapshot data
            snapshot_data = {
                "snapshot_time": datetime.now(ZoneInfo("UTC")).isoformat(),
                "repository": repo,
                "objects": {
                    obj_id: {
                        "data": obj.data,
                        "meta": {
                            "created_at": obj.meta.created_at.isoformat(),
                            "updated_at": obj.meta.updated_at.isoformat(),
                            "version": obj.meta.version
                        }
                    }
                    for obj_id, obj in objects.items()
                }
            }
            
            # Write to file
            output_path = Path(output)
            output_path.write_text(json.dumps(snapshot_data, indent=2))
            logger.info(f"Snapshot written to {output_path}")
            logger.info(f"Captured {len(objects)} objects")
            
        except GitHubStoreError as e:
            logger.error(f"Failed to create snapshot: {e}")
            raise SystemExit(1)
        except Exception as e:
            logger.exception("Unexpected error occurred")
            raise SystemExit(1)

    def update_snapshot(
        self,
        token: str,
        repo: str,
        snapshot_path: str,
        config: str | None = None
    ) -> None:
        """Update an existing snapshot with changes since its creation"""
        try:
            # Use provided config path or default
            config_path = Path(config) if config else self.default_config_path
            
            # Ensure config exists
            ensure_config_exists(config_path)
            
            # Read existing snapshot
            snapshot_path = Path(snapshot_path)
            if not snapshot_path.exists():
                raise FileNotFoundError(f"Snapshot file not found: {snapshot_path}")
            
            with open(snapshot_path) as f:
                snapshot_data = json.load(f)
            
            # Parse snapshot timestamp
            last_snapshot = datetime.fromisoformat(snapshot_data["snapshot_time"])
            logger.info(f"Updating snapshot from {last_snapshot}")
            
            # Get updated objects
            store = GitHubStore(token=token, repo=repo, config_path=config_path)
            updated_objects = store.list_updated_since(last_snapshot)
            
            if not updated_objects:
                logger.info("No updates found since last snapshot")
                return
            
            # Update snapshot data
            snapshot_data["snapshot_time"] = datetime.now(ZoneInfo("UTC")).isoformat() # should probably use latest object updated time here
            for obj_id, obj in updated_objects.items():
                snapshot_data["objects"][obj_id] = {
                    "data": obj.data,
                    "meta": {
                        "created_at": obj.meta.created_at.isoformat(),
                        "updated_at": obj.meta.updated_at.isoformat(),
                        "version": obj.meta.version
                    }
                }
            
            # Write updated snapshot
            snapshot_path.write_text(json.dumps(snapshot_data, indent=2))
            logger.info(f"Updated {len(updated_objects)} objects in snapshot")
            
        except GitHubStoreError as e:
            logger.error(f"Failed to update snapshot: {e}")
            raise SystemExit(1)
        except Exception as e:
            logger.exception("Unexpected error occurred")
            raise SystemExit(1)

    def init(self, config: str | None = None) -> None:
        """Initialize a new configuration file"""
        try:
            config_path = Path(config) if config else self.default_config_path
            
            if config_path.exists():
                logger.warning(f"Configuration file already exists at {config_path}")
                return
            
            ensure_config_exists(config_path)
            logger.info(f"Configuration initialized at {config_path}")
            
        except Exception as e:
            logger.exception("Failed to initialize configuration")
            raise SystemExit(1)

def main():
    fire.Fire(CLI)

if __name__ == "__main__":
    main()
