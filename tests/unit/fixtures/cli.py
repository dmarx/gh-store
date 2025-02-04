# tests/unit/fixtures/cli.py
"""CLI-specific fixtures for gh-store unit tests."""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone
import json
import pytest
from unittest.mock import Mock, patch
from loguru import logger

from gh_store.__main__ import CLI

@pytest.fixture(autouse=True)
def cli_env_vars(monkeypatch):
    """Setup environment variables for CLI testing."""
    monkeypatch.setenv('GITHUB_TOKEN', 'test-token')
    monkeypatch.setenv('GITHUB_REPOSITORY', 'owner/repo')
    yield

@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config file for testing."""
    config_dir = tmp_path / ".config" / "gh-store"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.yml"
    
    # Create default config
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
    config_path.write_text(default_config)
    return config_path

@pytest.fixture
def mock_gh_repo():
    """Create a mocked GitHub repo for testing."""
    mock_repo = Mock()
    with patch('gh_store.core.store.Github') as MockGithub:
        # Setup mock repo
        mock_repo = Mock()
        mock_repo.get_issue.return_value = Mock(state="closed")
        mock_repo.get_issues.return_value = []
        mock_repo.owner = Mock(login="owner", type="User")
        
        # Set up mock Github client
        MockGithub.return_value.get_repo.return_value = mock_repo
        yield mock_repo

@pytest.fixture(autouse=True)
def setup_loguru():
    """Configure loguru for testing."""
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level="INFO")  # Add test handler
    yield
    logger.remove()  # Clean up

@pytest.fixture
def mock_cli(mock_config, mock_gh_repo):
    """Create a CLI instance with mocked dependencies."""
    with patch('gh_store.__main__.ensure_config_exists') as mock_ensure:
        cli = CLI()
        # Mock HOME to point to our test config
        with patch.dict(os.environ, {'HOME': str(mock_config.parent.parent.parent)}):
            yield cli

@pytest.fixture
def mock_store_response():
    """Mock common GitHubStore responses."""
    mock_obj = Mock()
    mock_obj.meta = Mock(
        object_id="test-123",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
        version=1
    )
    mock_obj.data = {"name": "test", "value": 42}
    return mock_obj

@pytest.fixture
def mock_stored_objects():
    """Create mock stored objects for testing."""
    objects = {}
    for i in range(1, 3):
        mock_obj = Mock()
        mock_obj.meta = Mock(
            object_id=f"test-obj-{i}",
            created_at=datetime(2025, 1, i, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, i+1, tzinfo=timezone.utc),
            version=1
        )
        mock_obj.data = {
            "name": f"test{i}",
            "value": i * 42
        }
        objects[f"test-obj-{i}"] = mock_obj
    return objects

@pytest.fixture
def mock_snapshot_file(tmp_path, mock_stored_objects):
    """Create a mock snapshot file for testing."""
    snapshot_path = tmp_path / "test_snapshot.json"
    
    # Convert objects to serializable format
    snapshot_data = {
        "snapshot_time": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
        "repository": "owner/repo",
        "objects": {
            obj_id: {
                "data": obj.data,
                "meta": {
                    "created_at": obj.meta.created_at.isoformat(),
                    "updated_at": obj.meta.updated_at.isoformat(),
                    "version": obj.meta.version
                }
            }
            for obj_id, obj in mock_stored_objects.items()
        }
    }
    
    snapshot_path.write_text(json.dumps(snapshot_data, indent=2))
    return snapshot_path
