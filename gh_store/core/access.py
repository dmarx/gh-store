# gh_store/core/access.py

from typing import TypedDict, Set
from pathlib import Path
import re
from github import Repository, Issue, IssueComment
from loguru import logger

class UserInfo(TypedDict):
    login: str
    type: str

class AccessControl:
    """Handles access control validation for GitHub store operations"""
    
    def __init__(self, repo: Repository.Repository):
        self.repo = repo
        self._owner_info: UserInfo | None = None
        self._codeowners: Set[str] | None = None

    async def _get_owner_info(self) -> UserInfo:
        """Get repository owner information, caching the result"""
        if not self._owner_info:
            owner = await self.repo.get_owner()
            self._owner_info = {
                'login': owner.login,
                'type': owner.type
            }
        return self._owner_info

    async def _get_codeowners(self) -> Set[str]:
        """Parse CODEOWNERS file and extract authorized users/teams"""
        if self._codeowners is not None:
            return self._codeowners

        codeowners = set()
        codeowners_paths = [
            '.github/CODEOWNERS',
            'docs/CODEOWNERS',
            'CODEOWNERS'
        ]

        # Try to find CODEOWNERS file
        for path in codeowners_paths:
            try:
                content = self.repo.get_contents(path)
                if content:
                    # Decode content and process each line
                    for line in content.decoded_content.decode('utf-8').splitlines():
                        # Skip comments and empty lines
                        if not line or line.startswith('#'):
                            continue
                            
                        # Extract users/teams from the line
                        # Format: path @user1 @org/team1 @user2
                        parts = line.split()
                        if len(parts) > 1:  # Must have path and at least one owner
                            for part in parts[1:]:
                                if part.startswith('@'):
                                    # Remove @ prefix and add to set
                                    owner = part[1:]
                                    # Handle team syntax (@org/team)
                                    if '/' in owner:
                                        org, team = owner.split('/')
                                        # Get team members from GitHub API
                                        try:
                                            team_obj = self.repo.organization.get_team_by_slug(team)
                                            for member in team_obj.get_members():
                                                codeowners.add(member.login)
                                        except Exception as e:
                                            logger.warning(f"Failed to fetch team members for {owner}: {e}")
                                    else:
                                        codeowners.add(owner)
                    break  # Stop after finding first valid CODEOWNERS file
            except Exception as e:
                logger.debug(f"No CODEOWNERS found at {path}: {e}")
                continue

        self._codeowners = codeowners
        return codeowners

    async def _is_authorized(self, username: str | None) -> bool:
        """Check if a user is authorized (owner or in CODEOWNERS)"""
        if not username:
            return False
            
        # Repository owner is always authorized
        owner = await self._get_owner_info()
        if username == owner['login']:
            return True
            
        # Check CODEOWNERS
        codeowners = await self._get_codeowners()
        return username in codeowners

    async def validate_issue_creator(self, issue: Issue.Issue) -> bool:
        """Check if issue was created by authorized user"""
        creator = issue.user.login if issue.user else None
        
        if not await self._is_authorized(creator):
            logger.warning(
                f"Unauthorized creator for issue #{issue.number}: {creator}"
            )
            return False
            
        return True

    async def validate_comment_author(self, comment: IssueComment.IssueComment) -> bool:
        """Check if comment was created by authorized user"""
        author = comment.user.login if comment.user else None
        
        if not await self._is_authorized(author):
            logger.warning(
                f"Unauthorized author for comment {comment.id}: {author}"
            )
            return False
            
        return True

    async def validate_update_request(self, issue_number: int) -> bool:
        """Validate update request by checking issue and comment authors"""
        issue = self.repo.get_issue(issue_number)
        
        # First check issue creator
        if not await self.validate_issue_creator(issue):
            return False
            
        # Then check all unprocessed comments
        for comment in issue.get_comments():
            # Skip comments that are already processed
            if any(reaction.content == '+1' for reaction in comment.get_reactions()):
                continue
                
            if not await self.validate_comment_author(comment):
                return False
                
        return True

    def clear_cache(self) -> None:
        """Clear cached owner and CODEOWNERS information"""
        self._owner_info = None
        self._codeowners = None
