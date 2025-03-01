# gh_store/tools/find_duplicates.py

import argparse
import json
from collections import defaultdict
from pathlib import Path
from loguru import logger

from github import Github
from github.GithubException import GithubException


def find_duplicates(repo, base_label="stored-object", uid_prefix="UID:"):
    """Find objects with multiple issues.
    
    Args:
        repo: GitHub repository object
        base_label: Base label used for all stored objects
        uid_prefix: Prefix for unique identifier labels
        
    Returns:
        Dict mapping UID labels to lists of issue numbers
    """
    # Get all issues with the base label
    logger.info(f"Fetching all issues with {base_label} label")
    issues = list(repo.get_issues(state="all", labels=[base_label]))
    logger.info(f"Found {len(issues)} issues")
    
    # Group issues by their UID label
    objects_by_uid = defaultdict(list)
    
    for issue in issues:
        # Skip archived issues
        if any(label.name == "archived" for label in issue.labels):
            continue
            
        # Find UID label
        for label in issue.labels:
            if label.name.startswith(uid_prefix):
                uid = label.name
                objects_by_uid[uid].append(issue.number)
                break
    
    # Filter to only objects with duplicates
    duplicates = {uid: issues for uid, issues in objects_by_uid.items() if len(issues) > 1}
    return duplicates


def main():
    parser = argparse.ArgumentParser(description="Find duplicate objects in gh-store")
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument("--repo", required=True, help="Repository in owner/repo format")
    parser.add_argument("--base-label", default="stored-object", 
                        help="Base label for stored objects")
    parser.add_argument("--uid-prefix", default="UID:", 
                        help="Prefix for UID labels")
    parser.add_argument("--output", help="Output file path (JSON)")
    args = parser.parse_args()
    
    try:
        github = Github(args.token)
        repo = github.get_repo(args.repo)
        
        # Find duplicates
        duplicates = find_duplicates(repo, args.base_label, args.uid_prefix)
        
        # Summary information
        total_dupes = sum(len(issues) - 1 for issues in duplicates.values())
        object_count = len(duplicates)
        
        if object_count == 0:
            logger.info("No duplicate objects found.")
        else:
            logger.info(f"Found {object_count} objects with duplicates, {total_dupes} duplicate issues total")
            
            # Print details
            for uid, issues in duplicates.items():
                logger.info(f"{uid}: {issues}")
                
            # Create result object
            result = {
                "duplicate_count": object_count,
                "total_duplicates": total_dupes,
                "objects": {uid: issues for uid, issues in duplicates.items()}
            }
            
            # Write to file if output specified
            if args.output:
                output_path = Path(args.output)
                output_path.write_text(json.dumps(result, indent=2))
                logger.info(f"Results written to {output_path}")
            else:
                # Print to stdout
                print(json.dumps(result, indent=2))
                
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise SystemExit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
