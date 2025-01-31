# gh_store/core/version.py
import importlib.metadata

try:
    __version__ = importlib.metadata.version("gh-store")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.5.1"  # fallback version

CLIENT_VERSION = __version__
