# gh_store/cli.py

from pathlib import Path
import fire
from loguru import logger

from .core.store import GitHubStore
from .core.exceptions import GitHubStoreError

def setup_logging(config_path: Path):
    """Configure logging based on config file"""
    import yaml
    
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    logger.configure(
        handlers=[{"sink": "stderr", "format": config["store"]["log"]["format"]}]
    )
    logger.level(config["store"]["log"]["level"])

def process_updates(
    issue: int,
    token: str,
    repo: str,
    config: str = "config.yml"
) -> None:
    """
    Process pending updates for a stored object
    
    Args:
        issue: Issue number to process
        token: GitHub token with repo access
        repo: Repository in format 'owner/name'
        config: Path to config file
    """
    try:
        config_path = Path(config)
        setup_logging(config_path)
        
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

if __name__ == "__main__":
    fire.Fire({
        "process-updates": process_updates
    })
