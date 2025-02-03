# tests/unit/test_cli_crud.py

from datetime import datetime, timezone
import json
from unittest.mock import Mock, patch, mock_open

class TestCLIBasicOperations:
    def test_create(self, cli, mock_github, mock_issue):
        """Test create command"""
        mock_gh, mock_repo = mock_github
        mock_data = {"test": "data"}
        
        # Create mock issue with correct label format
        test_issue = mock_issue(
            number=123,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            body=json.dumps(mock_data),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")  # Include prefix in mock GitHub response
            ]
        )
        mock_repo.create_issue.return_value = test_issue
        
        # Create with client-facing ID (no prefix)
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            cli.create("test-123", "data.json")

        # Verify issue creation used prefixed label
        mock_repo.create_issue.assert_called_once()
        call_kwargs = mock_repo.create_issue.call_args[1]
        assert "UID:test-123" in call_kwargs["labels"]
        assert "test-123" not in call_kwargs["labels"]

        # Verify comment and reactions
        mock_issue.create_comment.assert_called_once()
        comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
        assert comment_data["type"] == "initial_state"
        assert comment_data["_data"] == mock_data

    def test_get(self, cli, mock_github):
        """Test get command"""
        mock_gh, mock_repo = mock_github
        
        # Mock GitHub response with prefixed label
        mock_issue = Mock(
            body=json.dumps({"test": "data"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")  # Include prefix in mock response
            ]
        )
        mock_repo.get_issues.return_value = [mock_issue]
        
        # Get with client-facing ID (no prefix)
        with patch('builtins.print') as mock_print:
            cli.get("test-123")
            
        # Verify correct label was queried
        mock_repo.get_issues.assert_called_once()
        call_kwargs = mock_repo.get_issues.call_args[1]
        assert "UID:test-123" in call_kwargs["params"]["labels"]
    
    def test_update(self, cli, mock_github):
        """Test update command"""
        mock_gh, mock_repo = mock_github
        mock_data = {"update": "data"}
        
        # Mock issue response with proper get_comments
        mock_issue = Mock(
            number=123,
            body=json.dumps({"test": "data"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ],
            get_comments=Mock(return_value=[])  # Add proper mock for get_comments
        )
        
        # Mock issue listing
        def get_issues_side_effect(**kwargs):
            if kwargs.get("state") == "open":
                return []  # No open issues
            return [mock_issue]
        mock_repo.get_issues.side_effect = get_issues_side_effect
        
        # Mock comment creation
        mock_comment = Mock(id=456)
        mock_issue.create_comment.return_value = mock_comment
        
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            cli.update("test-123", "update.json")
            
        mock_issue.create_comment.assert_called_once()

    def test_delete(self, cli, mock_github):
        """Test delete command"""
        mock_gh, mock_repo = mock_github
        
        # Mock GitHub response with prefixed label
        mock_issue = Mock(
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")  # Include prefix in mock response
            ]
        )
        mock_repo.get_issues.return_value = [mock_issue]
        
        # Delete with client-facing ID (no prefix)
        cli.delete("test-123")
        
        # Verify labels were preserved with prefix
        mock_issue.edit.assert_called_once()
        call_kwargs = mock_issue.edit.call_args[1]
        assert "archived" in call_kwargs["labels"]
        assert "stored-object" in call_kwargs["labels"]
        assert "UID:test-123" in call_kwargs["labels"]
