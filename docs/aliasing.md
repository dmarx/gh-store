# Object Aliasing in gh-store

The gh-store system supports object aliasing, which allows multiple object IDs to reference the same underlying data. This is useful for several scenarios:

1. **Deduplication**: Handling cases where duplicate objects were created
2. **Aliases**: Creating alternative names for the same object
3. **Migrations**: Moving from old object IDs to new ones without breaking existing references

## Concepts

The aliasing system uses the following concepts:

- **Canonical Object**: The authoritative source of truth for an object
- **Alias Object**: A reference to a canonical object
- **Reference Labels**: Special labels that link aliases to their canonical objects

## How It Works

When an alias is created or a duplicate is reconciled:

1. One issue is designated as the canonical issue and receives the "canonical-object" label
2. Other issues are designated as aliases and receive the "alias-object" label
3. Aliases get a reference label "ALIAS-TO:{canonical_issue_number}" that links to the canonical issue
4. Updates to either the canonical or alias objects affect the same data

When you access an object:

1. The system checks if the requested object is an alias
2. If it is, it automatically retrieves the canonical object instead
3. This happens transparently - you don't need to know which is which

When you update an object:

1. You can update either the canonical object or any alias
2. The update is always applied to the canonical object
3. All aliases immediately reflect the changes

## Command Line Interface

### Deduplicating Objects

To find and resolve duplicate objects:

```bash
gh-store deduplicate --token <token> --repo <owner/repo>
```

This will:
1. Find all objects with multiple issues
2. Make the oldest issue the canonical issue
3. Make all other issues aliases
4. Process updates to ensure the canonical issue has the correct state

Options:
- `--object-id <id>`: Process only a specific object ID
- `--input <file>`: Read duplicates from a JSON file instead of finding them
- `--output <file>`: Write results to a JSON file
- `--dry-run`: Just report what would be done, don't make changes

### Creating Aliases Manually

To create a new alias to an existing object:

```bash
gh-store create-alias <canonical-id> <alias-id> --token <token> --repo <owner/repo>
```

This creates a new alias that references the canonical object.

### Listing Aliases

To list all aliases in the store:

```bash
gh-store list-aliases --token <token> --repo <owner/repo>
```

Options:
- `--canonical-id <id>`: List only aliases for a specific canonical object
- `--output <file>`: Write results to a JSON file

## API Usage

```python
from gh_store.core.store import GitHubStore

store = GitHubStore(token="github-token", repo="username/repository")

# Create alias
store.create_alias("metrics", "daily-metrics")

# Get data (both return the same data)
metrics1 = store.get("metrics")  # Gets canonical object
metrics2 = store.get("daily-metrics")  # Gets canonical object via alias

# Update (both update the same data)
store.update("metrics", {"value": 42})  # Updates canonical object
store.update("daily-metrics", {"value": 43})  # Updates canonical object via alias

# List aliases
aliases = store.list_aliases()
```

## Best Practices

1. **Use Meaningful Names**: Choose intuitive, descriptive names for aliases
2. **Limit Alias Depth**: Avoid creating aliases to aliases - keep a flat structure
3. **Document Relationships**: Document why an alias exists and what it refers to
4. **Avoid Circular References**: Don't create circular reference chains
5. **Process Canonical Objects**: After setting up aliases, process the canonical objects to ensure consistent state

## Implementation Details

The aliasing system uses GitHub labels to manage relationships:

- **Base Labels**:
  - `canonical-object`: Marks the source of truth
  - `alias-object`: Marks a reference to a canonical object
  - `deprecated-object`: Marks objects that should no longer be used

- **Reference Labels**:
  - `ALIAS-TO:{number}`: Points to a canonical issue number
  - `MERGED-INTO:{number}`: For objects that have been merged into another
  - `DUPLICATE-OF-#{number}`: For deprecated duplicates

Each alias object contains:
- The alias-to-canonical relationship in its body
- Special labels identifying it as an alias
- A system comment documenting when the alias was created

## Deduplication Process

The deduplication process follows these steps:

1. **Identification**: Find objects with multiple issues having the same UID label
2. **Canonicalization**: Choose one issue (default: oldest) as the canonical issue
3. **Aliasing**: Mark other issues as aliases to the canonical issue
4. **State Resolution**: Process canonical issue to ensure it has the correct state
5. **Documentation**: Add system comments documenting the relationship

## Note on Object History

When retrieving an object's history, the system will automatically:

1. Check if the object is an alias
2. If it is, retrieve the history from the canonical object instead

This ensures you always get the complete history regardless of which object ID you use.

## Snapshots

When creating snapshots, the system will:

1. Include all canonical objects
2. Include alias information in a separate section
3. Automatically resolve aliases to their canonical objects

This allows you to understand the relationships between objects while still having a complete view of all data.

## Troubleshooting

Common issues and solutions:

- **Can't Update Alias**: If you get an error about alias objects not being directly updatable, use the canonical object ID instead
- **Circular References**: If you see a circular reference error, review your alias structure and eliminate cycles
- **Missing Updates**: If updates appear to be missing, ensure you've processed the canonical object after setting up aliases

## Advanced Uses

### Complex Migrations

For complex migrations, you can:

1. Create a new canonical object with the desired structure
2. Create aliases from old object IDs to the new canonical object
3. Gradually transition to using the new canonical object ID

### Merging Different Objects

To merge two different objects:

1. Decide which object will be canonical
2. Make the other object an alias
3. Update the canonical object to include data from both objects

### Multiple Aliases

A single canonical object can have multiple aliases, creating a hub-and-spoke structure:

```
                 /--- alias-1
canonical-object ---- alias-2
                 \--- alias-3
```

This allows the same data to be accessed through multiple logical names.
