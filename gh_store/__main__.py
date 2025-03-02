# gh_store/__main__.py

import fire
from pathlib import Path
from loguru import logger
from typing import Optional

from .cli import commands
from .cli.deduplicate import deduplicate_command, create_alias_command, list_aliases_command

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
        
    def deduplicate(
        self,
        token: str | None = None,
        repo: str | None = None,
        object_id: str | None = None,
        input: str | None = None,
        output: str | None = None,
        dry_run: bool = False,
        base_label: str = "stored-object",
        uid_prefix: str = "UID:",
    ) -> None:
        """Find and deduplicate objects with multiple issues
        
        Args:
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            object_id: Process specific object ID only (optional)
            input: Input file with duplicates to process (optional)
            output: Path to write output (optional)
            dry_run: Only report what would be done, don't make changes
            base_label: Base label for stored objects
            uid_prefix: Prefix for UID labels
        """
        return deduplicate_command(
            token=token,
            repo=repo,
            object_id=object_id,
            input_path=input,
            output_path=output,
            dry_run=dry_run,
            base_label=base_label,
            uid_prefix=uid_prefix
        )
        
    def create_alias(
        self,
        canonical_id: str,
        alias_id: str,
        token: str | None = None,
        repo: str | None = None,
        output: str | None = None,
    ) -> None:
        """Create an alias to a canonical object
        
        Args:
            canonical_id: Object ID of the canonical object
            alias_id: Object ID to use for the alias
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            output: Path to write output (optional)
        """
        return create_alias_command(
            canonical_id=canonical_id,
            alias_id=alias_id,
            token=token,
            repo=repo,
            output_path=output
        )
        
    def list_aliases(
        self,
        token: str | None = None,
        repo: str | None = None,
        canonical_id: str | None = None,
        output: str | None = None,
    ) -> None:
        """List all aliases in the store
        
        Args:
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            canonical_id: List aliases for specific canonical object only (optional)
            output: Path to write output (optional)
        """
        return list_aliases_command(
            token=token,
            repo=repo,
            canonical_id=canonical_id,
            output_path=output
        )


def main():
    fire.Fire(CLI)

if __name__ == "__main__":
    main()
