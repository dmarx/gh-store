# gh_store/__main__.py

import fire
from pathlib import Path
from loguru import logger

from .cli import commands

class CLI:
    """GitHub Issue Store CLI"""
    
    def __init__(self):
        """Initialize CLI with default config path"""
        self.default_config_path = Path.home() / ".config" / "gh-store" / "config.yml"
    
    def process_updates(
        self,
        issue: int,
        token: str | None = None,
        repo: str | None = None,
        config: str | None = None,
    ) -> None:
        """Process pending updates for a stored object"""
        return commands.process_updates(issue, token, repo, config)

    def snapshot(
        self,
        token: str | None = None,
        repo: str | None = None,
        output: str = "snapshot.json",
        config: str | None = None,
    ) -> None:
        """Create a full snapshot of all objects in the store"""
        return commands.snapshot(token, repo, output, config)

    def update_snapshot(
        self,
        snapshot_path: str,
        token: str | None = None,
        repo: str | None = None,
        config: str | None = None,
    ) -> None:
        """Update an existing snapshot with changes since its creation"""
        return commands.update_snapshot(snapshot_path, token, repo, config)

    def init(
        self,
        config: str | None = None
    ) -> None:
        """Initialize a new configuration file"""
        config_path = Path(config) if config else self.default_config_path
        commands.ensure_config_exists(config_path)
        logger.info(f"Configuration initialized at {config_path}")

    def create(
        self,
        object_id: str,
        data: str,
        token: str | None = None,
        repo: str | None = None,
        config: str | None = None,
    ) -> None:
        """Create a new object in the store
        
        Args:
            object_id: Unique identifier for the object
            data: JSON string containing object data
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """
        return commands.create(object_id, data, token, repo, config)

    def get(
        self,
        object_id: str,
        output: str | None = None,
        token: str | None = None,
        repo: str | None = None,
        config: str | None = None,
    ) -> None:
        """Retrieve an object from the store
        
        Args:
            object_id: Unique identifier for the object
            output: Path to write output (optional)
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """
        return commands.get(object_id, output, token, repo, config)

    def update(
        self,
        object_id: str,
        changes: str,
        token: str | None = None,
        repo: str | None = None,
        config: str | None = None,
    ) -> None:
        """Update an existing object
        
        Args:
            object_id: Unique identifier for the object
            changes: JSON string containing update data
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """
        return commands.update(object_id, changes, token, repo, config)

    def delete(
        self,
        object_id: str,
        token: str | None = None,
        repo: str | None = None,
        config: str | None = None,
    ) -> None:
        """Delete an object from the store
        
        Args:
            object_id: Unique identifier for the object
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """
        return commands.delete(object_id, token, repo, config)

    def history(
        self,
        object_id: str,
        output: str | None = None,
        token: str | None = None,
        repo: str | None = None,
        config: str | None = None,
    ) -> None:
        """Get complete history of an object
        
        Args:
            object_id: Unique identifier for the object
            output: Path to write output (optional)
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """
        return commands.get_history(object_id, output, token, repo, config)

def main():
    fire.Fire(CLI)

if __name__ == "__main__":
    main()
