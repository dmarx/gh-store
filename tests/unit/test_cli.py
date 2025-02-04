# tests/unit/test_cli.py
"""Test suite for CLI functionality."""

import json
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

from gh_store.__main__ import CLI
from gh_store.core.exceptions import GitHubStoreError

def test_init_creates_default_config(mock_env_setup, test_config_dir: Path):
    """Test that init creates default config in expected location."""
    cli = CLI()
    
    # Config shouldn't exist yet
    config_path = test_config_dir / "config.yml"
    assert not config_path.exists()
