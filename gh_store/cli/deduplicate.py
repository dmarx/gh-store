# gh_store/cli/deduplicate.py

import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from loguru import logger

from gh_store.core.store import GitHubStore
from gh_store.tools.find_duplicates import find_duplicates
from gh_store.tools.mark_duplicates import mark_duplicate_relationship


def find_all_duplicates(token: str, repo: str, base_label: str, uid_prefix: str) -> Dict[str, List[int]]:
    """Find all duplicate objects in the repository."""
    store = GitHubStore(token=token, repo=repo)
    github_repo = store.repo
    
    # Find duplicates
    duplicates = find_duplicates(github_repo, base_label, uid_prefix)
    
    # Convert from UID keys to object ID keys
    result = {}
    for uid, issues in duplicates.items():
        # Extract object ID from UID
        object_id = uid[len(uid_prefix):] if uid.startswith(uid_prefix) else uid
        result[object_id] = issues
        
    return result


def deduplicate_objects(
    token: str, 
    repo: str, 
    duplicates: Dict[str, List[int]], 
    dry_run: bool = False,
    uid_prefix: str = "UID:"
) -> Dict[str, Any]:
    """Set up aliases for duplicate objects."""
    if dry_run:
        logger.info("DRY RUN - no changes will be made")
        return {"status": "dry_run", "objects": duplicates}
        
    store = GitHubStore(token=token, repo=repo)
    github_repo = store.repo
    
    results = []
    
    for object_id, issue_numbers in duplicates.items():
        # Use oldest issue as canonical
        sorted_numbers = sorted(issue_numbers)
        canonical_number = sorted_numbers[0]
        alias_numbers = sorted_numbers[1:]
        
        if not alias_numbers:
            logger.info(f"Skipping {object_id} - only one instance found")
            results.append({
                "object_id": object_id,
                "canonical": canonical_number,
                "aliases": [],
                "status": "skipped",
                "reason": "Only one instance found"
            })
            continue
            
        try:
            # Mark the relationship
            logger.info(f"Setting up aliases for {object_id}: canonical=#{canonical_number}, aliases={alias_numbers}")
            result = mark_duplicate_relationship(
                github_repo, object_id, canonical_number, alias_numbers, uid_prefix)
            
            # Process updates to ensure canonical has proper state
            try:
                store.process_updates(canonical_number)
                result["processed"] = True
            except Exception as e:
                logger.error(f"Error processing updates for {object_id}: {e}")
                result["processed"] = False
                result["process_error"] = str(e)
                
            results.append(result)
        except Exception as e:
            logger.error(f"Error deduplicating {object_id}: {e}")
            results.append({
                "object_id": object_id,
                "canonical": canonical_number,
                "aliases": alias_numbers,
                "status": "error",
                "error": str(e)
            })
    
    # Create summary
    summary = {
        "total_processed": len(results),
        "successful": sum(1 for r in results if r.get("status") == "success"),
        "results": results
    }
    
    return summary


def create_alias(
    token: str,
    repo: str,
    canonical_id: str,
    alias_id: str
) -> Dict[str, Any]:
    """Create a new alias to a canonical object."""
    store = GitHubStore(token=token, repo=repo)
    
    try:
        # Create the alias
        obj = store.create_alias(canonical_id, alias_id)
        
        return {
            "status": "success",
            "canonical_id": canonical_id,
            "alias_id": alias_id,
            "data": {
                "created_at": obj.meta.created_at.isoformat(),
                "updated_at": obj.meta.updated_at.isoformat(),
                "version": obj.meta.version
            }
        }
    except Exception as e:
        logger.error(f"Error creating alias: {e}")
        return {
            "status": "error",
            "canonical_id": canonical_id,
            "alias_id": alias_id,
            "error": str(e)
        }


def list_aliases(
    token: str,
    repo: str,
    canonical_id: Optional[str] = None
) -> Dict[str, Any]:
    """List all aliases in the store."""
    store = GitHubStore(token=token, repo=repo)
    
    try:
        # Get aliases
        aliases = store.list_aliases(canonical_id)
        
        return {
            "status": "success",
            "count": len(aliases),
            "aliases": aliases
        }
    except Exception as e:
        logger.error(f"Error listing aliases: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


def deduplicate_command(
    token: Optional[str] = None,
    repo: Optional[str] = None,
    object_id: Optional[str] = None,
    input_path: Optional[str] = None,
    output_path: Optional[str] = None,
    dry_run: bool = False,
    base_label: str = "stored-object",
    uid_prefix: str = "UID:"
) -> None:
    """Command to deduplicate objects."""
    # Get token and repo from environment if not provided
    token = token or os.environ.get("GITHUB_TOKEN")
    repo = repo or os.environ.get("GITHUB_REPOSITORY")
    
    if not token or not repo:
        logger.error("GitHub token and repository must be provided")
        raise SystemExit(1)
    
    try:
        # Get duplicates from input file or by finding them
        if input_path:
            input_file = Path(input_path)
            if not input_file.exists():
                logger.error(f"Input file not found: {input_path}")
                raise SystemExit(1)
                
            input_data = json.loads(input_file.read_text())
            duplicates = input_data.get("objects", {})
        else:
            # Find duplicates
            duplicates = find_all_duplicates(token, repo, base_label, uid_prefix)
        
        # Filter to specific object ID if provided
        if object_id:
            if object_id in duplicates:
                duplicates = {object_id: duplicates[object_id]}
            else:
                logger.error(f"No duplicates found for object ID: {object_id}")
                raise SystemExit(1)
        
        if not duplicates:
            logger.info("No duplicates found")
            return
            
        # Process duplicates
        results = deduplicate_objects(token, repo, duplicates, dry_run, uid_prefix)
        
        # Output results
        if output_path:
            output_file = Path(output_path)
            output_file.write_text(json.dumps(results, indent=2))
            logger.info(f"Results written to {output_path}")
        else:
            # Print summary
            print(json.dumps(results, indent=2))
            
    except Exception as e:
        logger.exception(f"Error deduplicating objects: {e}")
        raise SystemExit(1)


def create_alias_command(
    canonical_id: str,
    alias_id: str,
    token: Optional[str] = None,
    repo: Optional[str] = None,
    output_path: Optional[str] = None
) -> None:
    """Command to create an alias."""
    # Get token and repo from environment if not provided
    token = token or os.environ.get("GITHUB_TOKEN")
    repo = repo or os.environ.get("GITHUB_REPOSITORY")
    
    if not token or not repo:
        logger.error("GitHub token and repository must be provided")
        raise SystemExit(1)
    
    try:
        # Create alias
        result = create_alias(token, repo, canonical_id, alias_id)
        
        # Output results
        if output_path:
            output_file = Path(output_path)
            output_file.write_text(json.dumps(result, indent=2))
            logger.info(f"Results written to {output_path}")
        else:
            # Print summary
            print(json.dumps(result, indent=2))
            
    except Exception as e:
        logger.exception(f"Error creating alias: {e}")
        raise SystemExit(1)


def list_aliases_command(
    token: Optional[str] = None,
    repo: Optional[str] = None,
    canonical_id: Optional[str] = None,
    output_path: Optional[str] = None
) -> None:
    """Command to list all aliases."""
    # Get token and repo from environment if not provided
    token = token or os.environ.get("GITHUB_TOKEN")
    repo = repo or os.environ.get("GITHUB_REPOSITORY")
    
    if not token or not repo:
        logger.error("GitHub token and repository must be provided")
        raise SystemExit(1)
    
    try:
        # List aliases
        result = list_aliases(token, repo, canonical_id)
        
        # Output results
        if output_path:
            output_file = Path(output_path)
            output_file.write_text(json.dumps(result, indent=2))
            logger.info(f"Results written to {output_path}")
        else:
            # Print summary
            print(json.dumps(result, indent=2))
            
    except Exception as e:
        logger.exception(f"Error listing aliases: {e}")
        raise SystemExit(1)
