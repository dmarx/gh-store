# tests/unit/test_cli_crud.py

from unittest.mock import Mock, patch, mock_open
import json
from datetime import datetime, timezone

class TestCLIBasicOperations:
    def test_create(self, cli, mock_github):
        """Test create command"""
        mock_gh, mock_repo = mock_github
        mock_data = {"test": "data"}
        
        # Mock issue creation
        mock_issue = Mock(
            number=123,
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            body=json.dumps(mock_data)
        )
        mock_repo.create_issue.return_value = mock_issue
        
        # Mock comment creation and reactions
        mock_comment = Mock(id=456)
        mock_issue.create_comment.return_value = mock_comment
        
        # Mock labels
        mock_repo.get_labels.return_value = [Mock(name="stored-object")]

        with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
            cli.create("test-123", "data.json")

        # Verify issue creation
        mock_repo.create_issue.assert_called_once()
        call_kwargs = mock_repo.create_issue.call_args[1]
        assert "test-123" in call_kwargs["title"]
        assert mock_data == json.loads(call_kwargs["body"])
        
        # Verify comment and reactions
        mock_issue.create_comment.assert_called_once()
        comment_data = json.loads(mock_issue.create_comment.call_args[0][0])
        assert comment_data["type"] == "initial_state"
        assert comment_data["_data"] == mock_data

    def test_get(self, cli, mock_github):
        """Test get command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issue response
        mock_issue = Mock(
            body=json.dumps({"test": "data"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issues.return_value = [mock_issue]
        
        # Mock comments for version
        mock_issue.get_comments.return_value = []

        with patch('builtins.print') as mock_print:
            cli.get("test-123")

        # Verify issue fetch
        mock_repo.get_issues.assert_called_once()
        mock_print.assert_called_once()
    
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
        
        # Mock issue response
        mock_issue = Mock(
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-123")
            ]
        )
        mock_repo.get_issues.return_value = [mock_issue]

        cli.delete("test-123")

        # Verify issue edited
        mock_issue.edit.assert_called_once_with(
            state="closed",
            labels=["archived", "stored-object", "UID:test-123"]
        )
