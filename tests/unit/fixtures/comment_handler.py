# tests/unit/fixtures/comment_handler.py
"""Fixtures for mocking CommentHandler functionality across tests."""

import pytest
from unittest.mock import Mock, patch
from typing import List, Callable

from gh_store.handlers.comment import CommentHandler
from gh_store.core.types import Update


@pytest.fixture
def mock_comment_handler():
    """
    Create a mock CommentHandler with configurable get_unprocessed_updates behavior.
    
    This fixture centralizes the mocking of CommentHandler methods to ensure
    consistent behavior across test suites.
    """
    def _configure_handler(comment_handler: CommentHandler, 
                         unprocessed_updates_factory: Callable[[int], List[Update]] = None):
        """
        Configure a CommentHandler instance with mock behaviors.
        
        Args:
            comment_handler: The CommentHandler instance to configure
            unprocessed_updates_factory: Optional factory function that takes an issue number
                                        and returns a list of unprocessed updates
        
        Returns:
            The configured CommentHandler instance
        """
        # Store original method for restoration
        original_get_unprocessed = comment_handler.get_unprocessed_updates
        
        # Mock get_unprocessed_updates if factory provided
        if unprocessed_updates_factory:
            comment_handler.get_unprocessed_updates = unprocessed_updates_factory
        
        # Add restoration method
        comment_handler.restore_original_get_unprocessed = lambda: setattr(
            comment_handler, 'get_unprocessed_updates', original_get_unprocessed
        )
        
        return comment_handler
    
    return _configure_handler


@pytest.fixture
def setup_unprocessed_updates_count():
    """
    Create a factory function that returns a configured number of unprocessed updates.
    
    Usage:
        count_factory = setup_unprocessed_updates_count()
        mock_comment_handler(store.comment_handler, count_factory(3))  # Returns 3 updates
    """
    def _create_factory(count: int):
        """Create a factory that returns the specified number of updates."""
        def _get_unprocessed_updates(issue_number: int):
            """Mock implementation of get_unprocessed_updates."""
            return [
                Update(
                    comment_id=i,
                    timestamp=Mock(),
                    changes={"value": f"update-{i}"}
                ) for i in range(count)
            ]
        return _get_unprocessed_updates
    
    return _create_factory
