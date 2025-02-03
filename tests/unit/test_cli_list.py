# tests/unit/test_cli_list.py

from unittest.mock import Mock, patch
import json
from datetime import datetime, timezone

class TestCLIListOperations:
    def test_list_all(self, cli, mock_github):
        """Test list_all command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issues response
        mock_issues = [
            Mock(
                body=json.dumps({"test": 1}),
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                labels=[
                    Mock(name="stored-object"),
                    Mock(name="UID:test-1")
                ],
                get_comments=Mock(return_value=[])
            ),
            Mock(
                body=json.dumps({"test": 2}),
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                labels=[
                    Mock(name="stored-object"),
                    Mock(name="UID:test-2")
                ],
                get_comments=Mock(return_value=[])
            )
        ]
        mock_repo.get_issues.return_value = mock_issues

        with patch('builtins.print') as mock_print:
            cli.list_all()

        # Verify issue listing
        mock_repo.get_issues.assert_called_once_with(
            state="closed",
            labels=["stored-object"]
        )
        mock_print.assert_called_once()

    def test_list_updated(self, cli, mock_github):
        """Test list_updated command"""
        mock_gh, mock_repo = mock_github
        timestamp = "2025-01-01T00:00:00Z"
        
        # Mock issues response
        mock_issue = Mock(
            body=json.dumps({"test": "updated"}),
            created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
            labels=[
                Mock(name="stored-object"),
                Mock(name="UID:test-1")
            ],
            get_comments=Mock(return_value=[])
        )
        mock_repo.get_issues.return_value = [mock_issue]

        with patch('builtins.print') as mock_print:
            cli.list_updated(timestamp)

        # Verify issue listing with since parameter
        call_kwargs = mock_repo.get_issues.call_args[1]
        assert call_kwargs["since"] == datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        mock_print.assert_called_once()

    def test_get_history(self, cli, mock_github):
        """Test get_history command"""
        mock_gh, mock_repo = mock_github
        
        # Mock issues response
        mock_issue = Mock(number=123)
        mock_repo.get_issues.return_value = [mock_issue]
        
        # Mock comments
        mock_comments = [
            Mock(
                id=1,
                created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                body=json.dumps({
                    "type": "initial_state",
                    "_data": {"status": "new"},
                    "_meta": {
                        "client_version": "0.1.0",
                        "timestamp": "2025-01-01T00:00:00Z",
                        "update_mode": "append"
                    }
                })
            ),
            Mock(
                id=2,
                created_at=datetime(2025, 1, 2, tzinfo=timezone.utc),
                body=json.dumps({
                    "_data": {"status": "updated"},
                    "_meta": {
                        "client_version": "0.1.0",
                        "timestamp": "2025-01-02T00:00:00Z",
                        "update_mode": "append"
                    }
                })
            )
        ]
        mock_issue.get_comments.return_value = mock_comments

        with patch('builtins.print') as mock_print:
            cli.get_history("test-123")

        # Verify comment retrieval
        mock_issue.get_comments.assert_called_once()
        mock_print.assert_called_once()
        
    def test_list_all_empty(self, cli, mock_github):
        """Test list_all when no objects exist"""
        mock_gh, mock_repo = mock_github
        mock_repo.get_issues.return_value = []

        with patch('builtins.print') as mock_print:
            cli.list_all()

        mock_repo.get_issues.assert_called_once_with(
            state="closed",
            labels=["stored-object"]
        )
        mock_print.assert_called_once()
