# Python Project Structure

## gh_store/__main__.py
```python
class CLI
    """GitHub Issue Store CLI"""

    def __init__(self)
        """Initialize CLI with default config path"""

    def process_updates(self, issue: int, token: str | None, repo: str | None, config: str | None) -> None
        """Process pending updates for a stored object"""

    def snapshot(self, token: str | None, repo: str | None, output: str, config: str | None) -> None
        """Create a full snapshot of all objects in the store"""

    def update_snapshot(self, snapshot_path: str, token: str | None, repo: str | None, config: str | None) -> None
        """Update an existing snapshot with changes since its creation"""

    def init(self, config: str | None) -> None
        """Initialize a new configuration file"""

    def create(self, object_id: str, data: str, token: str | None, repo: str | None, config: str | None) -> None
        """
        Create a new object in the store
        Args:
            object_id: Unique identifier for the object
            data: JSON string containing object data
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """

    def get(self, object_id: str, output: str | None, token: str | None, repo: str | None, config: str | None) -> None
        """
        Retrieve an object from the store
        Args:
            object_id: Unique identifier for the object
            output: Path to write output (optional)
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """

    def update(self, object_id: str, changes: str, token: str | None, repo: str | None, config: str | None) -> None
        """
        Update an existing object
        Args:
            object_id: Unique identifier for the object
            changes: JSON string containing update data
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """

    def delete(self, object_id: str, token: str | None, repo: str | None, config: str | None) -> None
        """
        Delete an object from the store
        Args:
            object_id: Unique identifier for the object
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """

    def history(self, object_id: str, output: str | None, token: str | None, repo: str | None, config: str | None) -> None
        """
        Get complete history of an object
        Args:
            object_id: Unique identifier for the object
            output: Path to write output (optional)
            token: GitHub token (optional)
            repo: GitHub repository (optional)
            config: Path to config file (optional)
        """


def main()

```

## gh_store/cli/commands.py
```python
def ensure_config_exists(config_path: Path) -> None
    """Create default config file if it doesn't exist"""

def get_store(token: str | None, repo: str | None, config: str | None) -> GitHubStore
    """Helper to create GitHubStore instance with CLI parameters using keyword arguments"""

def get(object_id: str, output: str | None, token: str | None, repo: str | None, config: str | None) -> None
    """Retrieve an object from the store"""

def create(object_id: str, data: str, token: str | None, repo: str | None, config: str | None) -> None
    """Create a new object in the store"""

def update(object_id: str, changes: str, token: str | None, repo: str | None, config: str | None) -> None
    """Update an existing object"""

def delete(object_id: str, token: str | None, repo: str | None, config: str | None) -> None
    """Delete an object from the store"""

def get_history(object_id: str, output: str | None, token: str | None, repo: str | None, config: str | None) -> None
    """Get complete history of an object"""

def process_updates(issue: int, token: str | None, repo: str | None, config: str | None) -> None
    """Process pending updates for a stored object"""

def snapshot(token: str | None, repo: str | None, output: str, config: str | None) -> None
    """Create a full snapshot of all objects in the store, including relationship info."""

def update_snapshot(snapshot_path: str, token: str | None, repo: str | None, config: str | None) -> None
    """Update an existing snapshot with changes since its creation"""

```

## gh_store/core/access.py
```python
class UserInfo(TypedDict)

class AccessControl
    """Handles access control validation for GitHub store operations"""

    def __init__(self, repo: Any)

    def _get_owner_info(self) -> UserInfo
        """Get repository owner information, caching the result"""

    def _get_codeowners(self) -> Set[str]
        """Parse CODEOWNERS file and extract authorized users"""

    def _find_codeowners_file(self) -> str | None
        """Find and read the CODEOWNERS file content"""

    def _parse_codeowners_content(self, content: str) -> Set[str]
        """Parse CODEOWNERS content and extract authorized users"""

    def _should_skip_line(self, line: str) -> bool
        """Check if line should be skipped (empty or comment)"""

    def _extract_users_from_line(self, line: str) -> Set[str]
        """Extract user and team names from a CODEOWNERS line"""

    def _get_team_members(self, team_spec: str) -> Set[str]
        """Get members of a team from GitHub API"""

    def _is_authorized(self, username: str | None) -> bool
        """Check if a user is authorized (owner or in CODEOWNERS)"""

    def validate_issue_creator(self, issue: Any) -> bool
        """Check if issue was created by authorized user"""

    def validate_comment_author(self, comment: Any) -> bool
        """Check if comment was created by authorized user"""

    def clear_cache(self) -> None
        """Clear cached owner and CODEOWNERS information"""


```

## gh_store/core/constants.py
```python
class LabelNames(StrEnum)
    """
    Constants for label names used by the gh-store system.
    Using str as a base class allows the enum values to be used directly as strings
    while still maintaining the benefits of an enumeration.
    """

class DeprecationReason(StrEnum)
    """Constants for deprecation reasons stored in metadata."""

```

## gh_store/core/exceptions.py
```python
class GitHubStoreError(Exception)
    """Base exception for GitHub store errors"""

class ObjectNotFound(GitHubStoreError)
    """Raised when attempting to access a non-existent object"""

class InvalidUpdate(GitHubStoreError)
    """Raised when an update comment contains invalid JSON or schema"""

class ConcurrentUpdateError(GitHubStoreError)
    """Raised when concurrent updates are detected"""

class ConfigurationError(GitHubStoreError)
    """Raised when there's an error in the store configuration"""

class DuplicateUIDError(GitHubStoreError)
    """Raised when multiple issues have the same UID label"""

class AccessDeniedError(GitHubStoreError)

```

## gh_store/core/store.py
```python
class GitHubStore
    """Interface for storing and retrieving objects using GitHub Issues"""

    def __init__(self, repo: str, token: str | None, config_path: Path | None, max_concurrent_updates: int)
        """Initialize the store with GitHub credentials and optional config"""

    def create(self, object_id: str, data: Json) -> StoredObject
        """Create a new object in the store"""

    def get(self, object_id: str) -> StoredObject
        """Retrieve an object from the store"""

    def update(self, object_id: str, changes: Json) -> StoredObject
        """Update an existing object"""

    def delete(self, object_id: str) -> None
        """Delete an object from the store"""

    def process_updates(self, issue_number: int) -> StoredObject
        """Process any unhandled updates on an issue"""

    def list_all(self) -> Iterator[StoredObject]
        """List all objects in the store, indexed by object ID"""

    def list_updated_since(self, timestamp: datetime) -> Iterator[StoredObject]
        """
        List objects updated since given timestamp.
        The main purpose of this function is for delta updating snapshots.
        The use of "updated" here specifically refers to updates *which have already been processed*
        with respect to the "view" on the object provided by the issue description body, i.e. it
        only fetches closed issued.
        Issues that have updates pending processing (i.e. which are open and have unreacted update comments) 
        are processed on an issue-by-issue basis by `GitHubStore.process_updates`.
        """

    def get_object_history(self, object_id: str) -> list[dict]
        """Get complete history of an object"""


```

## gh_store/core/types.py
```python
def get_object_id_from_labels(issue: Issue) -> str
    """
    Extract bare object ID from issue labels, removing any prefix.
    Args:
        issue: GitHub issue object with labels attribute
    Returns:
        str: Object ID without prefix
    Raises:
        ValueError: If no matching label is found
    """

@dataclass
class ObjectMeta
    """Metadata for a stored object"""

@dataclass
class StoredObject
    """An object stored in the GitHub Issues store"""

    @classmethod
    def from_issue(cls, issue: Issue, version: int) -> Self


@dataclass
class Update
    """An update to be applied to a stored object"""

@dataclass
class CommentMeta
    """Metadata included with each comment"""

    def to_dict(self) -> dict
        """Convert to dictionary for JSON serialization"""


@dataclass
class CommentPayload
    """Full comment payload structure"""

    def to_dict(self) -> dict
        """Convert to dictionary for JSON serialization"""


```

## gh_store/core/version.py
```python
def get_version() -> str
    """Get version from pyproject.toml metadata or fallback to manual version"""

```

## gh_store/handlers/comment.py
```python
class CommentHandler
    """Handles processing of update comments"""

    def __init__(self, repo: Any, config: DictConfig)

    def _validate_metadata(self, metadata: dict) -> bool
        """Validate that metadata contains all required fields"""

    def get_unprocessed_updates(self, issue_number: int) -> list[Update]
        """Get all unprocessed updates from issue comments"""

    def apply_update(self, obj: StoredObject, update: Update) -> StoredObject
        """Apply an update to an object"""

    def mark_processed(self, issue_number: int, updates: Sequence[Update]) -> None
        """Mark comments as processed by adding reactions"""

    @staticmethod
    def create_comment_payload(data: dict, issue_number: int, comment_type: str | None, update_mode: str) -> CommentPayload
        """Create a properly structured comment payload"""

    def _is_processed(self, comment: Any) -> bool
        """Check if a comment has been processed"""

    def _deep_merge(self, base: dict, update: dict) -> dict
        """Deep merge two dictionaries"""


```

## gh_store/handlers/issue.py
```python
class IssueHandler
    """Handles GitHub Issue operations for stored objects"""

    def __init__(self, repo: Any, config: DictConfig)

    def create_object(self, object_id: str, data: Json) -> StoredObject
        """Create a new issue to store an object"""

    def _ensure_labels_exist(self, labels: list[str]) -> None
        """Create labels if they don't exist"""

    def _with_retry(self, func)
        """Execute a function with retries on rate limit"""

    def get_object(self, object_id: str) -> StoredObject
        """Retrieve an object by its ID"""

    def get_object_history(self, object_id: str) -> list[dict]
        """Get complete history of an object, including initial state"""

    def get_object_by_number(self, issue_number: int) -> StoredObject
        """Retrieve an object by issue number"""

    def update_issue_body(self, issue_number: int, obj: StoredObject) -> None
        """Update the issue body with new object state"""

    def update_object(self, object_id: str, changes: Json) -> StoredObject
        """Update an object by adding a comment and reopening the issue"""

    def delete_object(self, object_id: str) -> None
        """Delete an object by closing and archiving its issue"""

    def _get_version(self, issue) -> int
        """Extract version number from issue"""


```

## gh_store/tools/canonicalize.py
```python
class CanonicalStore(GitHubStore)
    """Extended GitHub store with canonicalization and aliasing support."""

    def __init__(self, token: str, repo: str, config_path: Path | None)
        """Initialize with GitHub credentials."""

    def _ensure_special_labels(self) -> None
        """Create special labels used by the canonicalization system if needed."""

    def resolve_canonical_object_id(self, object_id: str, max_depth: int) -> str
        """
        Resolve an object ID to its canonical object ID with loop prevention.
        Args:
            object_id: Object ID to resolve
            max_depth: Maximum depth to prevent infinite loops with circular references
        Returns:
            The canonical object ID
        """

    def _extract_comment_metadata(self, comment, issue_number: int, object_id: str) -> dict
        """Extract metadata from a comment."""

    def collect_all_comments(self, object_id: str) -> List[Dict[[str, Any]]]
        """Collect comments from canonical issue and all aliases."""

    def process_with_virtual_merge(self, object_id: str) -> StoredObject
        """Process an object with virtual merging of related issues."""

    def _deep_merge(self, base: dict, update: dict) -> dict
        """Deep merge two dictionaries."""

    def get_object(self, object_id: str, canonicalize: bool) -> StoredObject
        """
        Retrieve an object.
        - If canonicalize=True (default), follow the alias chain and merge updates from all related issues.
        - If canonicalize=False, return the object as stored for the given object_id without alias resolution.
        """

    def update_object(self, object_id: str, changes: Json) -> StoredObject
        """Update an object by adding a comment to the appropriate issue."""

    def create_alias(self, source_id: str, target_id: str) -> dict
        """Create an alias from source_id to target_id."""

    def deprecate_issue(self, issue_number: int, target_issue_number: int, reason: str) -> dict
        """
        Deprecate a specific issue by making another issue canonical.
        Args:
            issue_number: The number of the issue to deprecate
            target_issue_number: The number of the canonical issue
            reason: Reason for deprecation ("duplicate", "merged", "replaced")
        """

    def deprecate_object(self, object_id: str, target_id: str, reason: str) -> dict
        """
        Deprecate an object by merging it into a target object.
        Args:
            object_id: The ID of the object to deprecate
            target_id: The ID of the canonical object to merge into
            reason: Reason for deprecation ("duplicate", "merged", "replaced")
        """

    def deduplicate_object(self, object_id: str, canonical_id: str) -> dict
        """
        Handle duplicate issues for an object ID by choosing one as canonical
        and deprecating the others.
        Args:
            object_id: The object ID to deduplicate
            canonical_id: Optional specific canonical object ID to use
                         (must match object_id unless aliasing)
        Returns:
            Dictionary with deduplication results
        """

    def _get_object_id(self, issue) -> str
        """Extract object ID from an issue's labels."""

    def find_duplicates(self) -> Dict[[str, List[Issue]]]
        """Find all duplicate objects in the store."""

    def find_aliases(self, object_id: str) -> Dict[[str, str]]
        """
        Find all aliases, or aliases for a specific object.
        Args:
            object_id: Optional object ID to find aliases for
        Returns:
            Dictionary mapping alias_id -> canonical_id
        """


def main()
    """Command line interface for canonicalization tools."""

```

## tests/unit/fixtures/canonical.py
```python
def mock_canonical_store()
    """Create a mock for CanonicalStore class."""

def mock_labels_response()
    """Mock the response for get_labels to return iterable labels."""

def canonical_store_with_mocks(mock_repo_factory, default_config, mock_labels_response)
    """Create a CanonicalStore instance with mocked repo and methods."""

def mock_issue_with_initial_state(mock_issue_factory, mock_comment_factory)
    """Create a mock issue with initial state for canonicalization tests."""

```

## tests/unit/fixtures/cli.py
```python
def cli_env_vars(monkeypatch)
    """Setup environment variables for CLI testing."""

def mock_config(tmp_path)
    """Create a mock config file for testing."""

def mock_gh_repo()
    """Create a mocked GitHub repo for testing."""

class InterceptHandler

    def emit(self, record)


def setup_loguru(caplog)
    """Configure loguru for testing with pytest caplog."""

def mock_cli(mock_config, mock_gh_repo)
    """Create a CLI instance with mocked dependencies."""

def mock_store_response()
    """Mock common GitHubStore responses."""

def mock_stored_objects()
    """Create mock stored objects for testing."""

def mock_snapshot_file_factory(tmp_path, mock_stored_objects)
    """Factory for creating snapshot files with configurable timestamps."""

def mock_snapshot_file(mock_snapshot_file_factory)
    """Create a default mock snapshot file for testing."""

def log_to_caplog(message)

def _create_snapshot(snapshot_time, include_objects)
    """
    Create a mock snapshot file with configurable timestamp and objects.
    Args:
        snapshot_time: Custom snapshot timestamp (defaults to 1 day ago)
        include_objects: List of indices from mock_stored_objects to include
                        (defaults to all objects)
    Returns:
        Path to the created snapshot file
    """

```

## tests/unit/fixtures/config.py
```python
def default_config()
    """Create a consistent default config for testing."""

def mock_config_file(default_config)
    """Mock OmegaConf config loading."""

def test_config_dir(tmp_path: Path) -> Path
    """Provide a temporary directory for config files during testing."""

def test_config_file(test_config_dir: Path, default_config: OmegaConf) -> Path
    """Create a test config file with minimal valid content."""

```

## tests/unit/fixtures/github.py
```python
def mock_label_factory()
    """
    Create GitHub-style label objects.
    Example:
        label = mock_label_factory("enhancement")
        label = mock_label_factory("bug", "fc2929")
        label = mock_label_factory("bug", "fc2929", "Bug description")
    """

class CommentMetadata(TypedDict)
    """Metadata for comment creation."""

class CommentBody(TypedDict)
    """Structure for comment body data."""

def mock_comment_factory()
    """
    Create GitHub comment mocks with standard structure.
    This factory creates mock comment objects that mirror GitHub's API structure,
    with proper typing and validation for reactions and metadata.
    Args in create_comment:
        body: Comment body (dict will be JSON serialized)
        user_login: GitHub username of comment author
        comment_id: Unique comment ID (auto-generated if None)
        reactions: List of reaction types or mock reactions
        created_at: Comment creation timestamp
        **kwargs: Additional attributes to set on the comment
    Examples:
        # Basic comment with data
        comment = mock_comment_factory(
            body={"value": 42},
            user_login="owner"
        )
        # Comment with metadata
        comment = mock_comment_factory(
            body={
                "_data": {"value": 42},
                "_meta": {
                    "client_version": "0.5.1",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "update_mode": "append"
                }
            }
        )
        # Initial state comment
        comment = mock_comment_factory(
            body={
                "type": "initial_state",
                "_data": {"initial": "state"},
                "_meta": {
                    "client_version": "0.5.1",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "update_mode": "append"
                }
            }
        )
        # Comment with reactions
        comment = mock_comment_factory(
            body={"value": 42},
            reactions=["+1", "rocket"]
        )
    """

def mock_issue_factory(mock_comment_factory, mock_label_factory)
    """
    Create GitHub issue mocks with standard structure.
    Examples:
        # Basic issue
        issue = mock_issue_factory(
            body={"test": "data"}
        )
        # Issue with explicit number
        issue = mock_issue_factory(
            number=123,
            labels=["stored-object", "UID:test-123"]
        )
        # Issue with comments
        issue = mock_issue_factory(
            comments=[
                mock_comment_factory(
                    body={"value": 42},
                    comment_id=1
                )
            ]
        )
    """

def mock_repo_factory(mock_label_factory)
    """
    Create GitHub repository mocks with standard structure.
    Note: Creates basic repository structure. Labels, issues, and permissions
    should be explicitly set up in tests where they matter.
    """

def mock_github()
    """Create a mock Github instance with proper repository structure."""

def create_label(name: str, color: str, description: str) -> Mock
    """
    Create a mock label with GitHub-like structure.
    Args:
        name: Name of the label
        color: Color hex code without #
        description: Optional description for the label
    """

def create_comment(body: dict[[str, Any]] | CommentBody, user_login: str, comment_id: int | None, reactions: list[str | Mock] | None, created_at: datetime | None) -> Mock
    """Create a mock comment with GitHub-like structure."""

def create_issue(number: int | None, body: dict[[str, Any]] | str | None, labels: list[str] | None, comments: list[Mock] | None, state: str, user_login: str, created_at: datetime | None, updated_at: datetime | None) -> Mock
    """
    Create a mock issue with GitHub-like structure.
    Args:
        number: Issue number (defaults to 1 if not provided)
        body: Issue body content (dict will be JSON serialized)
        labels: List of label names to add
        comments: List of mock comments
        state: Issue state (open/closed)
        user_login: GitHub username of issue creator
        created_at: Issue creation timestamp
        updated_at: Issue last update timestamp
        **kwargs: Additional attributes to set
    """

def create_repo(name: str, owner_login: str, owner_type: str, labels: list[str] | None, issues: list[Mock] | None) -> Mock
    """
    Create a mock repository with GitHub-like structure.
    Args:
        name: Repository name in owner/repo format
        owner_login: Repository owner's login
        owner_type: Owner type ("User" or "Organization")
        labels: Initial repository labels
        issues: Initial repository issues
        **kwargs: Additional attributes to set
    """

def create_label(name: str, color: str, description: str) -> Mock

def get_issue(number)

def get_contents(path: str) -> Mock

def create_label(name: str, color: str) -> Mock

def get_contents_side_effect(path: str) -> Mock

```

## tests/unit/fixtures/store.py
```python
def setup_mock_auth(store, authorized_users: Sequence[str] | None)
    """
    Set up mocked authorization for testing.
    Args:
        store: GitHubStore instance to configure
        authorized_users: List of usernames to authorize (defaults to ['repo-owner'])
    """

def store(mock_repo_factory, default_config)
    """Create GitHubStore instance with mocked dependencies."""

def authorized_store(store)
    """Create store with additional authorized users for testing."""

def history_mock_comments(mock_comment)
    """Create series of comments representing object history."""

def _authorized_store(authorized_users: Sequence[str])

```

## tests/unit/test_canonicalization.py
```python
def canonical_store(store, mock_repo_factory, default_config)
    """Create a CanonicalStore with mocked dependencies."""

def mock_alias_issue(mock_issue_factory)
    """Create a mock issue that is an alias to another object."""

def mock_canonical_issue(mock_issue_factory)
    """Create a mock issue that is the canonical version of an object."""

def mock_duplicate_issue(mock_issue_factory, mock_label_factory)
    """Create a mock issue that is a duplicate to be deprecated."""

def mock_deprecated_issue(mock_issue_factory, mock_label_factory)
    """Create a mock issue that has already been deprecated."""

class TestCanonicalStoreObjectResolution
    """Test object resolution functionality."""

    def test_resolve_canonical_object_id_direct(self, canonical_store, mock_canonical_issue)
        """Test resolving a canonical object ID (direct match)."""

    def test_resolve_canonical_object_id_alias(self, canonical_store, mock_alias_issue)
        """Test resolving an alias to find its canonical object ID."""

    def test_resolve_canonical_object_id_nonexistent(self, canonical_store)
        """Test resolving a non-existent object ID."""

    def test_resolve_canonical_object_id_circular_prevention(self, canonical_store, mock_label_factory)
        """Test prevention of circular references in alias resolution."""


class TestCanonicalStoreAliasing
    """Test alias creation and handling."""

    def test_create_alias(self, canonical_store, mock_canonical_issue, mock_alias_issue, mock_label_factory, mock_issue_factory)
        """Test creating an alias relationship."""

    def test_create_alias_already_alias(self, canonical_store, mock_alias_issue)
        """Test error when creating an alias for an object that is already an alias."""

    def test_create_alias_source_not_found(self, canonical_store)
        """Test error when source object is not found."""

    def test_create_alias_target_not_found(self, canonical_store, mock_duplicate_issue)
        """Test error when target object is not found."""


class TestCanonicalStoreDeprecation
    """Test object deprecation functionality."""

    def test_deprecate_object(self, canonical_store_with_mocks, mock_issue_factory)
        """Test deprecating an object properly calls deprecate_issue."""

    def test_deprecate_object_self_reference(self, canonical_store_with_mocks, mock_issue_factory)
        """Test that deprecating an object as itself raises an error."""

    def test_deduplicate_object(self, canonical_store_with_mocks, mock_issue_factory)
        """Test deduplication of an object with multiple issues."""

    def test_deprecate_issue(self, canonical_store_with_mocks, mock_issue_factory)
        """Test deprecating a specific issue."""

    def test_deduplicate_object_no_duplicates(self, canonical_store, mock_canonical_issue)
        """Test deduplication when no duplicates exist."""


class TestCanonicalStoreVirtualMerge
    """Test virtual merge processing."""

    def test_collect_all_comments(self, canonical_store, mock_canonical_issue, mock_alias_issue, mock_comment_factory)
        """Test collecting comments from canonical and alias issues."""

    def test_process_with_virtual_merge(self, canonical_store, mock_canonical_issue, mock_comment_factory)
        """Test processing virtual merge to build object state."""


class TestCanonicalStoreGetUpdate
    """Test get and update object operations with virtual merging."""

    def test_get_object_direct(self, canonical_store, mock_canonical_issue)
        """Test getting an object directly."""

    def test_get_object_via_alias(self, canonical_store)
        """Test getting an object via its alias."""

    def test_update_object_alias(self, canonical_store, mock_alias_issue)
        """Test updating an object via its alias."""

    def test_update_object_deprecated(self, canonical_store, mock_deprecated_issue, mock_canonical_issue, mock_label_factory)
        """Test updating a deprecated object."""

    def test_update_object_on_alias_preserves_identity(self, canonical_store, mock_alias_issue)
        """Test that an update on an alias returns the object without merging into the canonical record."""


class TestCanonicalStoreFinding
    """Test finding duplicates and aliases."""

    def test_find_duplicates(self, canonical_store_with_mocks, mock_issue_factory)
        """Test finding duplicate objects."""

    def test_find_aliases(self, canonical_store, mock_alias_issue)
        """Test finding aliases for objects."""

    def test_find_aliases_for_specific_object(self, canonical_store, mock_alias_issue)
        """Test finding aliases for a specific object."""


def mock_get_issues_side_effect()

def mock_get_issues_side_effect()

def mock_get_issues_side_effect()

def mock_get_issues()

def mock_get_issue(issue_number)

def mock_get_issue(issue_number)

def mock_get_object_id(issue)

def mock_get_issues_side_effect()

def mock_extract_metadata(comment, issue_number, object_id)

def mock_get_issues_side_effect()

```

## tests/unit/test_cli.py
```python
class TestCLIBasicOperations
    """Test basic CLI operations like create, get, update, delete"""

    def test_create_object(self, mock_cli, mock_store_response, tmp_path, caplog)
        """Test creating a new object via CLI"""

    def test_get_object(self, mock_cli, mock_store_response, tmp_path)
        """Test retrieving an object via CLI"""

    def test_delete_object(self, mock_cli, mock_store_response, caplog)
        """Test deleting an object via CLI"""


class TestCLIUpdateOperations
    """Test update-related CLI operations"""

    def test_update_object(self, mock_cli, mock_store_response, caplog)
        """Test updating an object via CLI"""

    def test_process_updates(self, mock_cli, mock_store_response, caplog)
        """Test processing pending updates via CLI"""


class TestCLISnapshotOperations
    """Test snapshot-related CLI operations"""

    def test_create_snapshot(self, mock_cli, mock_stored_objects, tmp_path, caplog)
        """Test creating a snapshot via CLI"""

    def test_update_snapshot_with_changes(self, mock_cli, mock_stored_objects, mock_snapshot_file_factory, caplog)
        """Test updating snapshot when objects have actually changed."""

    def test_update_snapshot_no_changes(self, mock_cli, mock_stored_objects, mock_snapshot_file_factory, caplog)
        """Test not updating snapshot when no objects have changed."""

    def test_update_snapshot_empty_file(self, mock_cli, mock_stored_objects, tmp_path, caplog)
        """Test error handling when updating a snapshot with invalid content."""


class TestCLIErrorHandling
    """Test CLI error handling scenarios"""

    def test_invalid_json_data(self, mock_cli)
        """Test handling of invalid JSON input"""

    def test_file_not_found(self, mock_cli, caplog)
        """Test handling of missing snapshot file"""


```

## tests/unit/test_comment_handler.py
```python
def mock_repo()

def mock_config()

def comment_handler(mock_repo, mock_config)

def test_get_unprocessed_updates_mixed_comments(comment_handler, mock_repo)
    """Test processing a mix of valid and invalid comments"""

def test_get_unprocessed_updates_unauthorized_json(comment_handler, mock_repo)
    """Test that valid JSON updates from unauthorized users are skipped"""

def test_get_unprocessed_updates_with_codeowners(comment_handler, mock_repo)
    """Test processing updates with CODEOWNERS authorization"""

def test_get_unprocessed_updates_empty(comment_handler, mock_repo)
    """Test behavior with no comments"""

def test_get_unprocessed_updates_all_processed(comment_handler, mock_repo)
    """Test behavior when all comments are already processed"""

def test_create_comment_payload(comment_handler)
    """Test creation of properly structured comment payloads"""

def test_get_unprocessed_updates_malformed_metadata(comment_handler, mock_repo)
    """Test handling of malformed metadata in comments"""

def test_apply_update_preserves_metadata(comment_handler)
    """Test that applying updates preserves any existing metadata"""

```

## tests/unit/test_config.py
```python
def test_store_uses_default_config_when_no_path_provided(mock_github, mock_config_file)
    """Test that store uses packaged default config when no config exists"""

def test_store_uses_provided_config_path(mock_github, tmp_path)
    """Test that store uses provided config path when it exists"""

def test_store_raises_error_for_nonexistent_custom_config(mock_github)
    """Test that store raises error when custom config path doesn't exist"""

def test_default_config_path_is_in_user_config_dir()
    """Test that default config path is in user's config directory"""

```

## tests/unit/test_object_history.py
```python
def history_mock_comments(mock_comment)
    """Create series of comments representing object history"""

def test_get_object_history_initial_state(store, mock_issue, history_mock_comments)
    """Test that initial state is correctly extracted from history"""

def test_get_object_history_updates_sequence(store, mock_issue, history_mock_comments)
    """Test that updates are returned in correct chronological order"""

def test_get_object_history_metadata_handling(store, mock_issue, history_mock_comments)
    """Test that metadata is correctly preserved in history"""

def test_get_object_history_legacy_format(store, mock_issue, mock_comment)
    """Test handling of legacy format comments in history"""

def test_comment_history_json_handling(store, mock_issue, mock_comment)
    """Test processing of valid JSON comments in history"""

def test_get_object_history_nonexistent(store)
    """Test retrieving history for nonexistent object"""

```

## tests/unit/test_security.py
```python
def test_owner_always_authorized(mock_github)
    """Test that repository owner is always authorized regardless of CODEOWNERS"""

def test_codeowners_authorization(mock_github)
    """Test authorization via CODEOWNERS file"""

def test_organization_ownership(mock_github)
    """Test authorization with organization ownership"""

def test_codeowners_file_locations(mock_github)
    """Test CODEOWNERS file location precedence"""

def test_unauthorized_update_rejection(store, mock_comment)
    """Test that updates from unauthorized users are rejected"""

def test_unauthorized_issue_creator_denied(store, mock_issue)
    """Test that updates are blocked for issues created by unauthorized users"""

def test_authorized_codeowners_updates(authorized_store, mock_comment)
    """Test that CODEOWNERS team members can make updates"""

def test_metadata_tampering_protection(store, mock_comment)
    """Test protection against metadata tampering in updates"""

def test_reaction_based_processing_protection(store, mock_comment)
    """Test that processed updates cannot be reprocessed"""

def get_contents_side_effect(path)

```

## tests/unit/test_store_basic_ops.py
```python
def test_create_object_with_initial_state(store, mock_label_factory, mock_comment_factory, mock_issue_factory)
    """Test that creating an object stores the initial state in a comment"""

def test_get_object(store)
    """Test retrieving an object"""

def test_get_nonexistent_object(store)
    """Test getting an object that doesn't exist"""

def test_create_object_ensures_labels_exist(store, mock_issue_factory, mock_label_factory)

```

## tests/unit/test_store_list_ops.py
```python
def test_list_updated_since(store, mock_issue_factory)
    """Test fetching objects updated since timestamp"""

def test_list_updated_since_no_updates(store, mock_issue)
    """Test when no updates since timestamp"""

def test_list_all_objects(store, mock_issue, mock_label_factory)
    """Test listing all objects in store"""

def test_list_all_skips_archived(store, mock_issue, mock_label_factory)
    """Test that archived objects are skipped in listing"""

def test_list_all_handles_invalid_labels(store, mock_issue, mock_label_factory)
    """Test handling of issues with invalid label structure"""

def get_object_by_number(number)

def get_object_by_number(number)

def get_object_by_number(number)

```

## tests/unit/test_store_update_ops.py
```python
def test_process_update(store, mock_issue_factory)
    """Test processing an update"""

def test_concurrent_update_prevention(store, mock_issue_factory, mock_comment_factory)
    """Test that concurrent updates are prevented"""

def test_update_metadata_structure(store, mock_issue_factory)
    """Test that updates include properly structured metadata"""

def test_update_nonexistent_object(store)
    """Test updating an object that doesn't exist"""

def get_issues_side_effect()

def open_issue_with_n_comments(n)

def set_store_with_issue_n_comments(n)

def get_issues_side_effect()

def get_issues_side_effect()

```

## tests/unit/test_types.py
```python
class TestStoredObject
    """Tests for StoredObject class."""

    def test_from_issue(self, mock_issue_factory, mock_label_factory)
        """Test correctly creating a StoredObject from an issue."""

    def test_from_issue_with_explicit_version(self, mock_issue_factory)
        """Test creating a StoredObject with explicit version number."""

    def test_from_issue_missing_uid_label(self, mock_issue_factory)
        """Test that creating a StoredObject fails when UID label is missing."""

    def test_from_issue_invalid_body(self, mock_issue_factory)
        """Test that creating a StoredObject fails with invalid JSON body."""


class TestObjectIDFromLabels
    """Tests for get_object_id_from_labels function."""

    def test_get_object_id_from_labels(self, mock_label_factory)
        """Test extracting object ID from issue labels."""

    def test_get_object_id_from_labels_no_match(self, mock_label_factory)
        """Test that ValueError is raised when no UID label exists."""


```
