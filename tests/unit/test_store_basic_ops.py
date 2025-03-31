# tests/unit/test_store_basic_ops.py

import json
from datetime import datetime, timezone
import pytest
from unittest.mock import Mock

from gh_store.core.constants import LabelNames
from gh_store.core.exceptions import ObjectNotFound


def test_create_object_with_initial_state(store, mock_label_factory, mock_comment_factory, mock_issue_factory):
    """Test that creating an object stores the initial state in a comment"""
    object_id = "test-123"
    test_data = {"name": "test", "value": 42}
    issue_number = 456  # Define issue number
    
    # Mock existing labels
    store.repo.get_labels.return_value = [
        mock_label_factory(name=LabelNames.GH_STORE),
        mock_label_factory(name=LabelNames.STORED_OBJECT),
    ]
    
    mock_issue = mock_issue_factory(number=issue_number)
    
    # Create object
    obj = store.create(object_id, test_data)
    
    # Verify initial state comment
    mock_issue.create_comment.assert_called_once()
    comment_data = json.loads(mock_issue.comments[0].body)
    assert comment_data["type"] == "initial_state"
    assert comment_data["_data"] == test_data
    assert "_meta" in comment_data
    assert "issue_number" in comment_data["_meta"]  # Verify issue_number in metadata
    assert comment_data["_meta"]["issue_number"] == issue_number  # Verify issue_number value
    
    # Verify object metadata
    assert obj.meta.issue_number == issue_number  # Verify issue_number in object metadata


# =================================== FAILURES ===================================
# ____________________ test_create_object_with_initial_state _____________________
#
# store = <gh_store.core.store.GitHubStore object at 0x7fdb15163250>
# mock_label_factory = <function mock_label_factory.<locals>.create_label at 0x7fdb1533f1a0>
# mock_comment_factory = <function mock_comment_factory.<locals>.create_comment at 0x7fdb1533f560>
# mock_issue_factory = <function mock_issue_factory.<locals>.create_issue at 0x7fdb1533f240>
#
#     def test_create_object_with_initial_state(store, mock_label_factory, mock_comment_factory, mock_issue_factory):
#         """Test that creating an object stores the initial state in a comment"""
#         object_id = "test-123"
#         test_data = {"name": "test", "value": 42}
#         issue_number = 456  # Define issue number
#         # Mock existing labels
#         store.repo.get_labels.return_value = [
#             mock_label_factory(name=LabelNames.GH_STORE),
#             mock_label_factory(name=LabelNames.STORED_OBJECT),
#         ]
#         mock_issue = mock_issue_factory(number=issue_number)
#         # Create object
# >       obj = store.create(object_id, test_data)
#
# tests/unit/test_store_basic_ops.py:38: 
# _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
# gh_store/core/store.py:49: in create
#     return self.issue_handler.create_object(object_id, data)
# gh_store/handlers/issue.py:56: in create_object
#     comment = issue.create_comment(json.dumps(initial_state_comment.to_dict(), indent=2))
# /opt/hostedtoolcache/Python/3.11.11/x64/lib/python3.11/json/__init__.py:238: in dumps
#     **kw).encode(obj)
# /opt/hostedtoolcache/Python/3.11.11/x64/lib/python3.11/json/encoder.py:202: in encode
#     chunks = list(chunks)
# /opt/hostedtoolcache/Python/3.11.11/x64/lib/python3.11/json/encoder.py:432: in _iterencode
#     yield from _iterencode_dict(o, _current_indent_level)
# /opt/hostedtoolcache/Python/3.11.11/x64/lib/python3.11/json/encoder.py:406: in _iterencode_dict
#     yield from chunks
# /opt/hostedtoolcache/Python/3.11.11/x64/lib/python3.11/json/encoder.py:406: in _iterencode_dict
#     yield from chunks
# /opt/hostedtoolcache/Python/3.11.11/x64/lib/python3.11/json/encoder.py:439: in _iterencode
#     o = _default(o)
# _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ 
#
# self = <json.encoder.JSONEncoder object at 0x7fdb15157490>
# o = <Mock name='Github().get_repo().create_issue().number' id='140578928360080'>
#
#     def default(self, o):
#         """Implement this method in a subclass such that it returns
#         a serializable object for ``o``, or calls the base implementation
#         (to raise a ``TypeError``).
#    
#         For example, to support arbitrary iterators, you could
#         implement default like this::
#
#             def default(self, o):
#                 try:
#                     iterable = iter(o)
#                 except TypeError:
#                     pass
#                 else:
#                     return list(iterable)
#                 # Let the base class default method raise the TypeError
#                 return super().default(o)
#
#         """
# >       raise TypeError(f'Object of type {o.__class__.__name__} '
#                         f'is not JSON serializable')
# E       TypeError: Object of type Mock is not JSON serializable
#
# /opt/hostedtoolcache/Python/3.11.11/x64/lib/python3.11/json/encoder.py:180: TypeError










def test_get_object(store):
    """Test retrieving an object"""
    test_data = {"name": "test", "value": 42}
    issue_number = 42  # Define issue number
    
    # Mock labels - should include both stored-object and gh-store
    stored_label = Mock()
    stored_label.name = "stored-object"
    gh_store_label = Mock()
    gh_store_label.name = LabelNames.GH_STORE
    uid_label = Mock()
    uid_label.name = "UID:test-obj"
    
    store.repo.get_labels.return_value = [stored_label, gh_store_label, uid_label]
    
    mock_issue = Mock()
    mock_issue.number = issue_number  # Set issue number
    mock_issue.body = json.dumps(test_data)
    mock_issue.get_comments = Mock(return_value=[])
    mock_issue.created_at = datetime.now(timezone.utc)
    mock_issue.updated_at = datetime.now(timezone.utc)
    mock_issue.labels = [stored_label, gh_store_label, uid_label]
    store.repo.get_issues.return_value = [mock_issue]
    
    obj = store.get("test-obj")
    assert obj.data == test_data
    assert obj.meta.issue_number == issue_number  # Verify issue_number in metadata
    
    # Verify correct query was made (now checking for all three labels)
    store.repo.get_issues.assert_called_with(
        labels=[LabelNames.GH_STORE, "stored-object", "UID:test-obj"],
        state="closed"
    )

def test_get_nonexistent_object(store):
    """Test getting an object that doesn't exist"""
    store.repo.get_issues.return_value = []
    
    with pytest.raises(ObjectNotFound):
        store.get("nonexistent")

def test_create_object_ensures_labels_exist(store, mock_issue_factory, mock_label_factory):
    pass
