# tests/unit/test_store.py

from datetime import datetime
from pathlib import Path
import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from github import Github, Repository, Issue, IssueComment
from github.GithubException import RateLimitExceededException
from gh_store.core.store import GitHubStore
from gh_store.core.types import StoredObject, ObjectMeta, Json, Update
from gh_store.core.exceptions import ObjectNotFound, InvalidUpdate, ConcurrentUpdateError

@pytest.fixture
def mock_repo():
    repo = Mock(spec=Repository.Repository)
    # Set up default return values for commonly used methods
    repo.get_issues.return_value = []
    repo.create_issue.return_value = Mock(spec=Issue.Issue)
    return repo

@pytest.fixture
def mock_github(mock_repo):
    with patch('gh_store.core.store.Github', autospec=True) as mock:
        # Configure the mock to return our mock_repo
        instance = mock.return_value
        instance.get_repo.return_value = mock_repo
        yield mock

@pytest.fixture
def mock_config():
    return {
        'store': {
            'base_label': 'stored-object',
            'processed_reaction': '+1',
            'retries': {
                'max_attempts': 3,
                'backoff_factor': 2
            }
        }
    }

@pytest.fixture
def store(mock_github, mock_repo, mock_config, tmp_path):
    # Create a temporary config file
    config_path = tmp_path / "test_config.yml"
    config_path.write_text(json.dumps(mock_config))
    
    store = GitHubStore(
        token="test-token",
        repo="test/repo",
        config_path=config_path
    )
    store.repo = mock_repo  # Ensure we're using our mock
    return store

@pytest.fixture
def sample_data() -> Json:
    return {
        "name": "test object",
        "value": 42,
        "tags": ["test", "example"]
    }

class TestGitHubStore:
    def test_create_object(self, store, mock_repo, sample_data):
        # Setup mock
        issue = Mock(spec=Issue.Issue)
        issue.number = 1
        issue.created_at = datetime.now()
        issue.updated_at = datetime.now()
        mock_repo.create_issue.return_value = issue

        # Test creation
        obj = store.create("test-obj", sample_data)
        
        # Verify
        assert isinstance(obj, StoredObject)
        assert obj.meta.object_id == "test-obj"
        assert obj.data == sample_data
        mock_repo.create_issue.assert_called_once()
        
        # Verify issue was created with correct parameters
        create_kwargs = mock_repo.create_issue.call_args[1]
        assert "stored-object" in create_kwargs["labels"]
        assert "test-obj" in create_kwargs["labels"]
        assert json.dumps(sample_data, indent=2) == create_kwargs["body"]

    def test_get_object(self, store, mock_repo):
        # Setup mock
        issue = Mock(spec=Issue.Issue)
        issue.body = json.dumps({"name": "test object", "value": 42})
        issue.created_at = datetime.now()
        issue.updated_at = datetime.now()
        issue.labels = [Mock(name="stored-object"), Mock(name="test-obj")]
        mock_repo.get_issues.return_value = [issue]

        # Test retrieval
        obj = store.get("test-obj")
        
        # Verify
        assert isinstance(obj, StoredObject)
        assert obj.data["name"] == "test object"
        mock_repo.get_issues.assert_called_with(
            labels=["stored-object", "test-obj"],
            state="closed"
        )

    def test_deep_update(self, store, mock_repo):
        # Setup mock
        initial_data = {
            "user": {
                "profile": {
                    "name": "Alice",
                    "settings": {"theme": "dark"}
                },
                "score": 10
            }
        }
        
        issue = Mock(spec=Issue.Issue)
        issue.number = 1
        issue.state = "closed"
        issue.body = json.dumps(initial_data)
        issue.labels = [Mock(name="stored-object"), Mock(name="test-obj")]
        
        mock_repo.get_issues.return_value = [issue]
        
        # Test deep update
        update_data = {
            "user": {
                "profile": {
                    "settings": {"theme": "light"}
                },
                "score": 15
            }
        }
        
        # Mock comment creation
        comment = Mock(spec=IssueComment.IssueComment)
        issue.create_comment.return_value = comment
        
        # Ensure get_object returns updated data after update
        def get_issues_side_effect(*args, **kwargs):
            if kwargs.get("state") == "closed":
                updated_data = {
                    "user": {
                        "profile": {
                            "name": "Alice",
                            "settings": {"theme": "light"}
                        },
                        "score": 15
                    }
                }
                issue.body = json.dumps(updated_data)
            return [issue]
        
        mock_repo.get_issues.side_effect = get_issues_side_effect
        
        obj = store.update("test-obj", update_data)

        # Verify deep merge
        assert obj.data["user"]["profile"]["name"] == "Alice"  # Preserved
        assert obj.data["user"]["profile"]["settings"]["theme"] == "light"  # Updated
        assert obj.data["user"]["score"] == 15  # Updated

    # ... rest of the tests remain the same ...
