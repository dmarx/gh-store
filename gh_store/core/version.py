# gh_store/core/version.py
import importlib.metadata
import os
from pathlib import Path

def get_version() -> str:
    """Get version from pyproject.toml metadata or fallback to manual version"""
    try:
        return importlib.metadata.version("gh-store")
    except importlib.metadata.PackageNotFoundError:
        # During development, read directly from pyproject.toml
        root_dir = Path(__file__).parent.parent.parent
        pyproject_path = root_dir / "pyproject.toml"
        
        if pyproject_path.exists():
            import tomli
            with open(pyproject_path, "rb") as f:
                pyproject = tomli.load(f)
                return pyproject["project"]["version"]
        
        return "0.5.1"  # Fallback version

__version__ = get_version()
CLIENT_VERSION = __version__
