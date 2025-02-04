# tests/unit/fixtures/cli.py
"""CLI-specific fixtures for gh-store unit tests."""

from pathlib import Path
from datetime import datetime, timezone
import json
import pytest
from unittest.mock import patch, mock_open, Mock
from gh_store.__main__ import CLI

@pytest.fixture
def cli_env_vars():
    """Setup environment variables for CLI testing."""
    with patch.dict('os.environ', {
        'GITHUB_TOKEN': 'test-token',
        'GITHUB_REPOSITORY': 'owner/repo'
    }):
        yield

@pytest.fixture
def mock_env_setup(monkeypatch, test_config_dir: Path):
    """Mock environment setup for CLI testing."""
    # Mock HOME directory to control config location
    monkeypatch.setenv("HOME", str(test_config_dir.parent.parent))
    
    # Mock default config access
    default_config = """
store:
  base_label: "stored-object"
  uid_prefix: "UID:"
  reactions:
    processed: "+1"
    initial_state: "rocket"
  retries:
    max_attempts: 3
    backoff_factor: 2
  rate_limit:
    max_requests_per_hour: 1000
  log:
    level: "INFO"
    format: "{time} | {level} | {message}"
"""
    with patch('importlib.resources.files') as mock_files:
        mock_files.return_value.joinpath.return_value.read_bytes = \
            lambda: default_config.encode('utf-8')
        yield mock_files

@pytest.fixture
def cli(cli_env_vars, mock_github, mock_env_setup):
    """Create CLI instance with mocked dependencies."""
    return CLI()

@pytest.fixture
def mock_snapshot_data():
    """Create consistent mock data for snapshot testing."""
    return {
        "test-obj-1": {
            "data": {"name": "test1", "value": 42},
            "meta": {
                "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2025, 1, 2, tzinfo=timezone.utc),
                "version": 1
            }
        },
        "test-obj-2": {
            "data": {"name": "test2", "value": 84},
            "meta": {
                "created_at": datetime(2025, 1, 3, tzinfo=timezone.utc),
                "updated_at": datetime(2025, 1, 4, tzinfo=timezone.utc),
                "version": 1
            }
        }
    }

@pytest.fixture
def mock_stored_objects(mock_snapshot_data):
    """Create mock StoredObject instances from snapshot data."""
    objects = {}
    for obj_id, data in mock_snapshot_data.items():
        mock_obj = Mock()
        mock_obj.data = data["data"]
        mock_obj.meta.created_at = data["meta"]["created_at"]
        mock_obj.meta.updated_at = data["meta"]["updated_at"]
        mock_obj.meta.version = data["meta"]["version"]
        mock_obj.meta.object_id = obj_id
        objects[obj_id] = mock_obj
    return objects

@pytest.fixture
def mock_snapshot_file(tmp_path, mock_snapshot_data):
    """Create a mock snapshot file for testing."""
    snapshot_path = tmp_path / "test_snapshot.json"
    
    # Convert datetime objects to ISO format strings for JSON serialization
    serializable_data = {
        obj_id: {
            "data": data["data"],
            "meta": {
                "created_at": data["meta"]["created_at"].isoformat(),
                "updated_at": data["meta"]["updated_at"].isoformat(),
                "version": data["meta"]["version"]
            }
        }
        for obj_id, data in mock_snapshot_data.items()
    }
    
    snapshot_content = {
        "snapshot_time": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "repository": "owner/repo",
        "objects": serializable_data
    }
    
    snapshot_path.write_text(json.dumps(snapshot_content, indent=2))
    return snapshot_path

@pytest.fixture
def mock_config_file_creation():
    """Mock the creation of config files."""
    mock_file = mock_open(read_data="")
    with patch('builtins.open', mock_file):
        with patch('pathlib.Path.exists') as mock_exists:
            mock_exists.return_value = False
            with patch('pathlib.Path.mkdir') as mock_mkdir:
                yield mock_file

@pytest.fixture
def mock_github_auth():
    """Mock GitHub authentication and API initialization."""
    with patch('gh_store.core.store.Github') as mock_gh:
        # Mock the repo setup
        mock_repo = Mock()
        mock_repo.get_issue.return_value = Mock(state="closed")
        mock_repo.get_issues.return_value = []
        mock_repo.owner = Mock(login="owner", type="User")
        
        # Setup the mock Github instance
        mock_gh.return_value.get_repo.return_value = mock_repo
        yield mock_gh, mock_repo
