# gh_store/__main__.py

from pathlib import Path
import json
from datetime import datetime
import fire
from loguru import logger

from .core.store import GitHubStore
from .core.exceptions import GitHubStoreError

class CLI:
    """GitHub Issue Store CLI"""
    
    def process_updates(
        self,
        issue: int,
        token: str,
        repo: str,
        config: str = "config.yml"
    ) -> None:
        """Process pending updates for a stored object"""
        try:
            config_path = Path(config)
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
        config: str = "config.yml"
    ) -> None:
        """Create a snapshot of all objects in the store"""
        try:
            store = GitHubStore(token=token, repo=repo, config_path=Path(config))
            
            # Get all stored objects
            objects = store.list_all()
            
            # Create snapshot data
            snapshot_data = {
                "timestamp": datetime.utcnow().isoformat(),
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

def main():
    fire.Fire(CLI)

if __name__ == "__main__":
    main()
