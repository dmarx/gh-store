# gh_store/tools/mark_duplicates.py

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

from github import Github
from github.GithubException import GithubException

from gh_store.tools.find_duplicates import find_duplicates
from gh_store.tools.label_manager import ensure_special_labels, create_reference_label
from gh_store.core.version import CLIENT_VERSION


def mark_duplicate_relationship(repo, object_id, canonical_number, alias_numbers, uid_prefix="UID:"):
    """Mark relationships between duplicates without changing content.
    
    Args:
        repo: GitHub repository object
        object_id: Object ID (without prefix)
        canonical_number: Issue number for canonical issue
        alias_numbers: List of issue numbers for alias issues
        uid_prefix: Prefix for UID labels
        
    Returns:
        Dict with information about the operation
    """
    # Ensure special labels exist
    ensure_special_labels(repo)
    
    logger.info(f"Marking relationships for {object_id}: "
               f"canonical=#{canonical_number}, aliases={alias_numbers}")
    
    try:
        # Mark canonical
        canonical_issue = repo.get_issue(canonical_number)
        canonical_issue.add_to_labels("canonical-object")
        
        # Create documentation comment for canonical issue
        alias_comment = {
            "_data": {
                "duplicate_relationship": "canonical",
                "alias_issues": alias_numbers,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "_meta": {
                "client_version": CLIENT_VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "update_mode": "append",
                "system": True
            },
            "type": "system_relationship"
        }
        
        canonical_issue.create_comment(json.dumps(alias_comment, indent=2))
        
        # Mark aliases
        for alias_number in alias_numbers:
            alias_issue = repo.get_issue(alias_number)
            alias_issue.add_to_labels("alias-object")
            
            # Add relationship label
            reference_label = create_reference_label(repo, "ALIAS-TO:", canonical_number)
            alias_issue.add_to_labels(reference_label)
            
            # Create documentation comment for alias issue
            alias_comment = {
                "_data": {
                    "duplicate_relationship": "alias",
                    "canonical_issue": canonical_number,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                },
                "_meta": {
                    "client_version": CLIENT_VERSION,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "update_mode": "append",
                    "system": True
                },
                "type": "system_relationship"
            }
            
            alias_issue.create_comment(json.dumps(alias_comment, indent=2))
    
        return {
            "object_id": object_id,
            "canonical": canonical_number,
            "aliases": alias_numbers,
            "status": "success"
        }
    
    except GithubException as e:
        logger.error(f"Error marking relationship for {object_id}: {e}")
        return {
            "object_id": object_id,
            "canonical": canonical_number,
            "aliases": alias_numbers,
            "status": "error",
            "error": str(e)
        }


def main():
    parser = argparse.ArgumentParser(description="Mark duplicate relationships in gh-store")
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument("--repo", required=True, help="Repository in owner/repo format")
    parser.add_argument("--base-label", default="stored-object", 
                        help="Base label for stored objects")
    parser.add_argument("--uid-prefix", default="UID:", 
                        help="Prefix for UID labels")
    parser.add_argument("--object-id", help="Process specific object ID only")
    parser.add_argument("--input", help="Input file with duplicates (from find_duplicates.py)")
    parser.add_argument("--output", help="Output file path (JSON)")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Don't make any changes, just report what would be done")
    args = parser.parse_args()
    
    try:
        github = Github(args.token)
        repo = github.get_repo(args.repo)
        
        # Get duplicates either from input file or by finding them
        if args.input:
            input_path = Path(args.input)
            if not input_path.exists():
                logger.error(f"Input file not found: {input_path}")
                raise SystemExit(1)
                
            input_data = json.loads(input_path.read_text())
            duplicates = input_data.get("objects", {})
            
            # Convert JSON string keys to UIDs
            duplicates = {
                k if k.startswith(args.uid_prefix) else f"{args.uid_prefix}{k}": v 
                for k, v in duplicates.items()
            }
        else:
            # Find duplicates directly
            duplicates = find_duplicates(repo, args.base_label, args.uid_prefix)
        
        # Filter to specific object ID if provided
        if args.object_id:
            object_key = f"{args.uid_prefix}{args.object_id}"
            if object_key in duplicates:
                duplicates = {object_key: duplicates[object_key]}
            else:
                logger.error(f"No duplicates found for object ID: {args.object_id}")
                raise SystemExit(1)
        
        if not duplicates:
            logger.info("No duplicates to process")
            return
            
        # Process duplicates
        results = []
        
        for uid, issue_numbers in duplicates.items():
            # Use oldest issue as canonical
            sorted_numbers = sorted(issue_numbers)
            canonical_number = sorted_numbers[0]
            alias_numbers = sorted_numbers[1:]
            
            # Extract object ID from UID label
            object_id = uid[len(args.uid_prefix):] if uid.startswith(args.uid_prefix) else uid
            
            if args.dry_run:
                logger.info(f"DRY RUN: Would mark {object_id} with canonical=#{canonical_number}, "
                           f"aliases={alias_numbers}")
                results.append({
                    "object_id": object_id,
                    "canonical": canonical_number,
                    "aliases": alias_numbers,
                    "status": "dry_run"
                })
            else:
                # Mark the relationship
                result = mark_duplicate_relationship(
                    repo, object_id, canonical_number, alias_numbers, args.uid_prefix)
                results.append(result)
                
        # Create summary
        summary = {
            "total_processed": len(results),
            "successful": sum(1 for r in results if r.get("status") == "success"),
            "results": results
        }
        
        # Write to file if output specified
        if args.output:
            output_path = Path(args.output)
            output_path.write_text(json.dumps(summary, indent=2))
            logger.info(f"Results written to {output_path}")
        else:
            # Print to stdout
            print(json.dumps(summary, indent=2))
    
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise SystemExit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
