# github_store/tests/test_store.py

from datetime import datetime
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

from github import Github, Repository, Issue, IssueComment
from gh_store.core.store import GitHubStore
from gh_store.core.types import StoredObject, ObjectMeta, Json, Update
from gh_store.core.exceptions import ObjectNotFound, InvalidUpdate

@pytest.fixture
def mock_repo():
    repo = Mock(spec=Repository.Repository)
    return repo

@pytest.fixture
def mock_github():
    with patch('github.Github') as mock:
        mock.return_value.get_repo.return_value = mock_repo()
        yield mock

@pytest.fixture
def store(mock_github):
    return GitHubStore(
        token="test-token",
        repo="test/repo",
        config_path=Path("tests/test_config.yml")
    )

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
        assert sample_data in create_kwargs["body"]

    def test_get_object(self, store, mock_repo):
        # Setup mock
        issue = Mock(spec=Issue.Issue)
        issue.body = '{"name": "test object", "value": 42}'
        issue.created_at = datetime.now()
        issue.updated_at = datetime.now()
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

    def test_get_nonexistent_object(self, store, mock_repo):
        # Setup mock to return no issues
        mock_repo.get_issues.return_value = []

        # Test
        with pytest.raises(ObjectNotFound):
            store.get("nonexistent")

    def test_update_object(self, store, mock_repo):
        # Setup mock
        issue = Mock(spec=Issue.Issue)
        issue.number = 1
        issue.body = '{"name": "test object", "value": 42}'
        comment = Mock(spec=IssueComment.IssueComment)
        mock_repo.get_issues.return_value = [issue]
        issue.create_comment.return_value = comment

        # Test update
        update_data = {"value": 43}
        obj = store.update("test-obj", update_data)
        
        # Verify
        assert obj.data["value"] == 43
        issue.create_comment.assert_called_once()
        issue.edit.assert_called_with(state="open")

    def test_process_updates(self, store, mock_repo):
        # Setup mocks
        issue = Mock(spec=Issue.Issue)
        issue.number = 1
        issue.body = '{"name": "test object", "value": 42}'
        
        comments = [
            Mock(spec=IssueComment.IssueComment, id=1, body='{"value": 43}'),
            Mock(spec=IssueComment.IssueComment, id=2, body='{"tags": ["updated"]}')
        ]
        
        mock_repo.get_issue.return_value = issue
        issue.get_comments.return_value = comments
        
        # Test processing
        obj = store.process_updates(1)
        
        # Verify final state
        assert obj.data["value"] == 43
        assert obj.data["tags"] == ["updated"]
        
        # Verify comments were marked as processed
        for comment in comments:
            comment.create_reaction.assert_called_with("+1")
        
        # Verify issue was closed
        issue.edit.assert_called_with(state="closed")

    def test_invalid_update_json(self, store, mock_repo):
        # Setup mock
        issue = Mock(spec=Issue.Issue)
        issue.body = '{"name": "test object"}'
        comment = Mock(spec=IssueComment.IssueComment)
        comment.body = 'invalid json'
        
        mock_repo.get_issue.return_value = issue
        issue.get_comments.return_value = [comment]

        # Test
        with pytest.raises(InvalidUpdate):
            store.process_updates(1)
