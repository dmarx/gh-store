# gh_store/core/access.py

from typing import TypedDict, Set
from pathlib import Path
import re
from github import Repository, Issue, IssueComment, GithubException
from loguru import logger

class UserInfo(TypedDict):
    login: str
    type: str

class AccessControl:
    """Handles access control validation for GitHub store operations"""
    
    CODEOWNERS_PATHS = [
        '.github/CODEOWNERS',
        'docs/CODEOWNERS',
        'CODEOWNERS'
    ]
    
    def __init__(self, repo: Repository.Repository):
        self.repo = repo
        self._owner_info: UserInfo | None = None
        self._codeowners: Set[str] | None = None

    def _get_owner_info(self) -> UserInfo:
        """Get repository owner information, caching the result"""
        if not self._owner_info:
            #owner = self.repo._owner
            owner = self.repo.owner
            # PyGithub returns ValuedAttribute objects, so we need to get their values
            self._owner_info = {
                'login': str(owner.login),  # Convert to string to ensure we have a plain value
                'type': str(owner.type)
            }
        return self._owner_info

    def _get_codeowners(self) -> Set[str]:
        """Parse CODEOWNERS file and extract authorized users"""
        if self._codeowners is not None:
            return self._codeowners

        content = self._find_codeowners_file()
        if not content:
            return set()

        self._codeowners = self._parse_codeowners_content(content)
        return self._codeowners
    
    def _find_codeowners_file(self) -> str | None:
        """Find and read the CODEOWNERS file content"""
        for path in self.CODEOWNERS_PATHS:
            try:
                content = self.repo.get_contents(path)
                if content:
                    return content.decoded_content.decode('utf-8')
            except GithubException:
                logger.debug(f"No CODEOWNERS found at {path}")
        return None
    
    def _parse_codeowners_content(self, content: str) -> Set[str]:
        """Parse CODEOWNERS content and extract authorized users"""
        codeowners = set()
        
        for line in content.splitlines():
            if self._should_skip_line(line):
                continue
                
            codeowners.update(self._extract_users_from_line(line))
                
        return codeowners
    
    def _should_skip_line(self, line: str) -> bool:
        """Check if line should be skipped (empty or comment)"""
        line = line.strip()
        return not line or line.startswith('#')
    
    def _extract_users_from_line(self, line: str) -> Set[str]:
        """Extract user and team names from a CODEOWNERS line"""
        users = set()
        parts = line.split()
        
        # Skip the path (first element)
        for part in parts[1:]:
            if part.startswith('@'):
                owner = part[1:]  # Remove @ prefix
                if '/' in owner:
                    # Handle team syntax (@org/team)
                    users.update(self._get_team_members(owner))
                else:
                    users.add(owner)
                    
        return users
    
    def _get_team_members(self, team_spec: str) -> Set[str]:
        """Get members of a team from GitHub API"""
        try:
            org, team = team_spec.split('/')
            team_obj = self.repo.organization.get_team_by_slug(team)
            return {member.login for member in team_obj.get_members()}
        except Exception as e:
            logger.warning(f"Failed to fetch team members for {team_spec}: {e}")
            return set()

    def _is_authorized(self, username: str | None) -> bool:
        """Check if a user is authorized (owner or in CODEOWNERS)"""
        if not username:
            return False
            
        # Repository owner is always authorized
        owner = self._get_owner_info()
        if username == owner['login']:
            return True
            
        # Check CODEOWNERS
        codeowners = self._get_codeowners()
        return username in codeowners

    def validate_issue_creator(self, issue: Issue.Issue) -> bool:
        """Check if issue was created by authorized user"""
        creator = issue.user.login if issue.user else None
        
        if not self._is_authorized(creator):
            logger.warning(
                f"Unauthorized creator for issue #{issue.number}: {creator}"
            )
            return False
            
        return True

    def validate_comment_author(self, comment: IssueComment.IssueComment) -> bool:
        """Check if comment was created by authorized user"""
        author = comment.user.login if comment.user else None
        
        if not self._is_authorized(author):
            logger.warning(
                f"Unauthorized author for comment {comment.id}: {author}"
            )
            return False
            
        return True

    def clear_cache(self) -> None:
        """Clear cached owner and CODEOWNERS information"""
        self._owner_info = None
        self._codeowners = None
