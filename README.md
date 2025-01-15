# GitHub Issue Store

A lightweight data store using GitHub Issues as a backend. Store and update JSON objects using GitHub Issues as a persistent storage layer, with automatic update processing via GitHub Actions.

## Features

- Store JSON objects in GitHub Issues
- Update objects through issue comments
- Automatic update processing via GitHub Actions
- Sequential update handling with atomic operations
- Full audit trail of all changes
- Idempotent processing with reaction-based tracking
- Configurable via YAML
- Type-safe Python interface

## Installation

```bash
pip install gh-store
```

Or install from source:

```bash
git clone https://github.com/dmarx/gh-store.git
cd gh-store
pip install -e .
```

## Quick Start

1. Add the GitHub Actions workflow to your repository:

```bash
mkdir -p .github/workflows
cp gh_store/workflows/process_update.yml .github/workflows/
```

2. Configure your GitHub token with repo access:

```python
from gh_store import GitHubStore

store = GitHubStore(
    token="your-github-token",
    repo="owner/repository"
)
```

3. Start using the store:

```python
# Create an object
data = {"name": "test", "value": 42}
obj = store.create("my-object", data)

# Retrieve an object
obj = store.get("my-object")

# Update an object
store.update("my-object", {"value": 43})
```

## How It Works

### Object Storage

Each object is stored in a dedicated GitHub Issue:

- The issue body contains the current object state as JSON
- Each object has two labels:
  - `stored-object`: Base label for all stored objects
  - Custom label matching the object ID
- Issue state indicates processing status:
  - `closed`: Object is stable
  - `open`: Updates are being processed

### Update Flow

1. Updates are submitted as JSON comments on the object's issue
2. The issue is reopened to trigger processing
3. GitHub Actions runs the update processor
4. Each comment is processed in chronological order
5. Processed comments receive a "👍" reaction
6. The issue is closed when all updates are processed

Example update flow:

```python
# Initial state
obj = store.get("user-123")
print(obj.data)
# {"name": "Alice", "score": 10}

# Submit an update
store.update("user-123", {"score": 15})

# After processing
obj = store.get("user-123")
print(obj.data)
# {"name": "Alice", "score": 15}
```

### Deep Updates

The store supports deep dictionary updates:

```python
# Initial state
{
    "user": {
        "profile": {
            "name": "Alice",
            "settings": {"theme": "dark"}
        },
        "score": 10
    }
}

# Update
store.update("user-123", {
    "user": {
        "profile": {
            "settings": {"theme": "light"}
        },
        "score": 15
    }
})

# Final state
{
    "user": {
        "profile": {
            "name": "Alice",
            "settings": {"theme": "light"}
        },
        "score": 15
    }
}
```

## Configuration

Create a `config.yml` file:

```yaml
store:
  base_label: "stored-object"
  processed_reaction: "+1"
  retries:
    max_attempts: 3
    backoff_factor: 2
  rate_limit:
    max_requests_per_hour: 1000
  log:
    level: "INFO"
    format: "{time} | {level} | {message}"
```

Pass the config file path when initializing:

```python
store = GitHubStore(
    token="your-token",
    repo="owner/repo",
    config_path=Path("config.yml")
)
```

## Error Handling

The store provides specific exceptions for common error cases:

```python
from gh_store.core.exceptions import (
    ObjectNotFound,
    InvalidUpdate,
    ConcurrentUpdateError
)

try:
    obj = store.get("nonexistent")
except ObjectNotFound:
    print("Object doesn't exist")

try:
    store.update("user-123", "invalid json")
except InvalidUpdate:
    print("Invalid update format")
```

## Command Line Interface

The package includes a CLI for use in GitHub Actions:

```bash
# Process updates for an issue
python -m gh_store process-updates \
    --issue 123 \
    --token $GITHUB_TOKEN \
    --repo "owner/repository"
```

## Use Cases

The GitHub Issue Store is particularly useful for:

- Lightweight data storage without additional infrastructure
- Applications that need a full audit trail of changes
- Collaborative data management with GitHub-based workflows
- Prototypes and small projects
- Data that changes infrequently but needs version history

## Limitations

- Not suitable for high-frequency updates
- GitHub API rate limits apply
- Maximum issue size limits apply
- Not recommended for sensitive data
- No transactional guarantees across multiple objects

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## Testing

Run the test suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=gh_store
```

## License

MIT License - see LICENSE file for details
