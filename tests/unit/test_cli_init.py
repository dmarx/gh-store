# tests/unit/test_cli_init.py

from pathlib import Path
import pytest

from gh_store.__main__ import CLI

class TestCLIInitialization:
    def test_init_with_env_vars(self, cli_env_vars, mock_github, mock_config_exists):
        """Test CLI initialization using environment variables"""
        mock_gh, _ = mock_github
        cli = CLI()
        assert cli.token == "test-token"
        assert cli.repo == "owner/repo"
        
        # Verify Github was initialized with correct token
        mock_gh.assert_called_once_with("test-token")
        # Verify correct repo was requested
        mock_gh.return_value.get_repo.assert_called_once_with("owner/repo")

    def test_init_with_args(self, mock_github, mock_config_exists):
        """Test CLI initialization using explicit arguments"""
        mock_gh, _ = mock_github
        cli = CLI(token="arg-token", repo="arg/repo", config="custom_config.yml")
        assert cli.token == "arg-token"
        assert cli.repo == "arg/repo"
        assert cli.config_path == Path("custom_config.yml")

    def test_init_no_credentials(self, mock_github, mock_config_exists):
        """Test CLI initialization with no credentials fails"""
        with pytest.raises(ValueError, match="No GitHub token found"):
            CLI(repo="owner/repo")

        with pytest.raises(ValueError, match="No repository specified"):
            CLI(token="test-token")

    def test_invalid_config_path(self, mock_github):
        """Test initialization with invalid config path"""
        with pytest.raises(FileNotFoundError):
            CLI(
                token="test-token",
                repo="owner/repo",
                config="/nonexistent/path/config.yml"
            )
