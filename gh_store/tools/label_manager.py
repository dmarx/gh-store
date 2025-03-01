# gh_store/tools/label_manager.py

import argparse
from loguru import logger
from github import Github
from github.GithubException import GithubException


def ensure_special_labels(repo):
    """Create special labels for aliasing if they don't exist.
    
    Args:
        repo: GitHub repository object
        
    Returns:
        List of labels that were created
    """
    special_labels = [
        ("canonical-object", "0366d6", "Canonical object that may have aliases"),
        ("alias-object", "fbca04", "Object that is an alias to a canonical object"),
        ("deprecated-object", "999999", "Objects that have been deprecated")
    ]
    
    existing_labels = {label.name for label in repo.get_labels()}
    created_labels = []
    
    for name, color, description in special_labels:
        if name not in existing_labels:
            try:
                repo.create_label(name=name, color=color, description=description)
                logger.info(f"Created label: {name}")
                created_labels.append(name)
            except GithubException as e:
                logger.error(f"Failed to create label {name}: {e}")
        else:
            logger.info(f"Label already exists: {name}")
    
    return created_labels


def create_reference_label(repo, prefix, number):
    """Create a reference label if it doesn't exist.
    
    Args:
        repo: GitHub repository object
        prefix: Label prefix (e.g., "ALIAS-TO:")
        number: Issue number to reference
        
    Returns:
        Label name
    """
    label_name = f"{prefix}{number}"
    
    try:
        # Check if label exists
        try:
            repo.get_label(label_name)
            logger.debug(f"Label already exists: {label_name}")
        except GithubException:
            # Create if it doesn't exist
            repo.create_label(label_name, "fbca04")
            logger.info(f"Created label: {label_name}")
    except GithubException as e:
        logger.error(f"Failed to create label {label_name}: {e}")
    
    return label_name


def main():
    parser = argparse.ArgumentParser(description="Manage special labels for gh-store")
    parser.add_argument("--token", required=True, help="GitHub token")
    parser.add_argument("--repo", required=True, help="Repository in owner/repo format")
    parser.add_argument("--create-reference", action="store_true", 
                        help="Create a reference label")
    parser.add_argument("--prefix", default="ALIAS-TO:", 
                        help="Reference label prefix")
    parser.add_argument("--number", type=int, 
                        help="Issue number for reference label")
    args = parser.parse_args()
    
    try:
        github = Github(args.token)
        repo = github.get_repo(args.repo)
        
        # Ensure special labels exist
        created = ensure_special_labels(repo)
        
        if created:
            logger.info(f"Created {len(created)} special labels")
        else:
            logger.info("All special labels already exist")
        
        # Create reference label if requested
        if args.create_reference and args.number:
            label_name = create_reference_label(repo, args.prefix, args.number)
            logger.info(f"Reference label: {label_name}")
            
    except GithubException as e:
        logger.error(f"GitHub API error: {e}")
        raise SystemExit(1)
    except Exception as e:
        logger.exception("Unexpected error")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
