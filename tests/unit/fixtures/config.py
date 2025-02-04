# tests/unit/fixtures/config.py
"""Configuration fixtures for gh-store unit tests."""

from datetime import datetime, timezone
from pathlib import Path
import pytest
from unittest.mock import patch, mock_open
from omegaconf import OmegaConf

@pytest.fixture
def default_config():
    """Create a consistent default config for testing."""
    return OmegaConf.create({
        "store": {
            "base_label": "stored-object",
            "uid_prefix": "UID:",
            "reactions": {
                "processed": "+1",
                "initial_state": "rocket"
            },
            "retries": {
                "max_attempts": 3,
                "backoff_factor": 2
            },
            "rate_limit": {
                "max_requests_per_hour": 1000
            },
            "log": {
                "level": "INFO",
                "format": "{time} | {level} | {message}"
            }
        }
    })

@pytest.fixture(autouse=True)
def mock_config_file(default_config):
    """Mock OmegaConf config loading."""
    with patch('omegaconf.OmegaConf.load', return_value=default_config) as mock_load:
        yield mock_load

@pytest.fixture
def test_config_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for config files during testing."""
    config_dir = tmp_path / ".config" / "gh-store"
    config_dir.mkdir(parents=True)
    return config_dir

@pytest.fixture
def test_config_file(test_config_dir: Path, default_config: OmegaConf) -> Path:
    """Create a test config file with minimal valid content."""
    config_path = test_config_dir / "config.yml"
    config_path.write_text(OmegaConf.to_yaml(default_config))
    return config_path
