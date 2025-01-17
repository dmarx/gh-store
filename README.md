# gh-store

A data store implementation using GitHub Issues as a backend. Provides versioned storage and update capabilities for applications running in GitHub's ecosystem.

## Key Features
- Store and version JSON objects using GitHub Issues
- Atomic updates through a comment-based event system
- Point-in-time snapshots for static site generation
- Built-in GitHub Actions integration

## Installation

```bash
pip install gh-store  # Requires Python 3.12+
```

## Prerequisites
- GitHub repository with Issues enabled
- GitHub token with `repo` scope
- For GitHub Actions: `issues` write permission

## Basic Usage

```python
from gh_store.core.store import GitHubStore

store = GitHubStore(
    token="github-token",
    repo="username/repository"
)

# Create object
store.create("metrics", {
    "count": 0,
    "last_updated": "2025-01-16T00:00:00Z"
})

# Update object
store.update("metrics", {"count": 1})

# Get current state
obj = store.get("metrics")
print(f"Current count: {obj.data['count']}")
```

## System Architecture

gh-store uses GitHub Issues as a versioned data store. Here's how the components work together:

### 1. Object Storage Model

Each stored object is represented by a GitHub Issue:
```
Issue #123
├── Labels: ["stored-object", "UID:metrics"]
├── Body: Current object state (JSON)
└── Comments: Update history
    ├── Comment 1: Update {"count": 1}
    ├── Comment 2: Update {"field": "value"}
    └── Each comment includes the 👍 reaction when processed
```

Key components:
- **Base Label** ("stored-object"): Identifies issues managed by gh-store
- **UID Label** ("UID:{object-id}"): Uniquely identifies each stored object
- **Issue Body**: Contains the current state as JSON
- **Comments**: Store update history
- **Reactions**: Track processed updates (👍)

### 2. Update Process

When updating an object:
1. New update is added as a comment with JSON changes
2. Issue is reopened to trigger processing
3. GitHub Actions workflow processes updates:
   - Gets all unprocessed comments (no 👍 reaction)
   - Applies updates in chronological order
   - Adds 👍 reaction to mark comments as processed
   - Updates issue body with new state
   - Closes issue when complete

### 3. Core Components

- **GitHubStore**: Main interface for CRUD operations
- **IssueHandler**: Manages GitHub Issue operations
- **CommentHandler**: Processes update comments

## GitHub Actions Integration

### Process Updates

```yaml
# .github/workflows/process_update.yml
name: Process Updates

on:
  issues:
    types: [reopened]

jobs:
  process:
    runs-on: ubuntu-latest
    if: contains(github.event.issue.labels.*.name, 'stored-object')
    permissions:
      issues: write
    steps:
      - uses: actions/checkout@v4
      - name: Process Updates
        run: |
          gh-store process-updates \
            --issue ${{ github.event.issue.number }} \
            --token ${{ secrets.GITHUB_TOKEN }} \
            --repo ${{ github.repository }}
```

### Create Snapshots

```yaml
# .github/workflows/snapshot.yml
name: Snapshot

on:
  schedule:
    - cron: '0 0 * * *'  # Daily
  workflow_dispatch:

jobs:
  snapshot:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - name: Create Snapshot
        run: |
          gh-store snapshot \
            --token ${{ secrets.GITHUB_TOKEN }} \
            --repo ${{ github.repository }} \
            --output data/store-snapshot.json
```

## CLI Commands

```bash
# Process updates for an issue
gh-store process-updates \
  --issue <issue-number> \
  --token <github-token> \
  --repo <owner/repo>

# Create snapshot
gh-store snapshot \
  --token <github-token> \
  --repo <owner/repo> \
  --output <path>

# Update existing snapshot
gh-store update-snapshot \
  --token <github-token> \
  --repo <owner/repo> \
  --snapshot-path <path>
```

## Configuration

Create `config.yml`:

```yaml
store:
  # Label identifying store issues
  base_label: "stored-object"
  
  # Prefix for object ID labels
  uid_prefix: "UID:"
  
  # Reaction marking processed comments
  processed_reaction: "+1"
  
  # API retry settings
  retries:
    max_attempts: 3
    backoff_factor: 2
    
  # Rate limiting
  rate_limit:
    max_requests_per_hour: 1000
    
  # Logging
  log:
    level: "INFO"
    format: "{time} | {level} | {message}"
```

## Limitations

- Not suitable for high-frequency updates (GitHub API limits)
- Objects limited to Issue size (~65KB)
- Updates processed asynchronously via GitHub Actions
- Consider data visibility in public repositories

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking & linting
mypy .
ruff check .
```

## License

MIT License - see [LICENSE](LICENSE)
