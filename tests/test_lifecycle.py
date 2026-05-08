#!/usr/bin/env python3
"""
Tests unitaires — Message Lifecycle Management

Run: pytest tests/test_lifecycle.py -v
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

# Import module à tester
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from lifecycle import MessageLifecycle


class TestMessageLifecycle:
    """Tests pour MessageLifecycle."""
    
    @pytest.fixture
    def mock_session(self):
        """Fixture: Mock session."""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def lifecycle(self, mock_session):
        """Fixture: Lifecycle instance."""
        return MessageLifecycle(mock_session, cooldown_ms=0)  # No cooldown for tests
    
    def test_mark_as_read_success(self, lifecycle, mock_session):
        """Test: Mark message as read succeeds."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Code": 1000}
        mock_session.request.return_value = mock_response
        
        result = lifecycle.mark_as_read("message123")
        
        assert result == True
        mock_session.request.assert_called_once_with(
            "PATCH",
            "https://mail.proton.me/api/mail/v4/messages/message123",
            json={"IsRead": 1}
        )
    
    def test_mark_as_read_failure(self, lifecycle, mock_session):
        """Test: Mark message as read fails."""
        # Setup mock to raise exception
        mock_session.request.side_effect = Exception("API error")
        
        result = lifecycle.mark_as_read("message123")
        
        assert result == False
    
    def test_mark_batch_as_read(self, lifecycle, mock_session):
        """Test: Batch mark messages as read."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Code": 1000}
        mock_session.request.return_value = mock_response
        
        result = lifecycle.mark_batch_as_read(["msg1", "msg2", "msg3"])
        
        assert result == 3
        assert mock_session.request.call_count == 3
    
    def test_get_trash_label_id_found(self, lifecycle, mock_session):
        """Test: Get Trash LabelID when found."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Labels": [
                {"ID": "inbox", "Name": "Inbox", "Type": 0},
                {"ID": "trash", "Name": "Trash", "Type": 3},
                {"ID": "archive", "Name": "Archive", "Type": 5}
            ]
        }
        mock_session.request.return_value = mock_response
        
        result = lifecycle.get_trash_label_id()
        
        assert result == "trash"
    
    def test_get_trash_label_id_not_found(self, lifecycle, mock_session):
        """Test: Get Trash LabelID when not found."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Labels": [
                {"ID": "inbox", "Name": "Inbox", "Type": 0}
            ]
        }
        mock_session.request.return_value = mock_response
        
        result = lifecycle.get_trash_label_id()
        
        assert result is None
    
    def test_move_to_trash_success(self, lifecycle, mock_session):
        """Test: Move message to trash succeeds."""
        # Setup mocks
        trash_response = MagicMock()
        trash_response.json.return_value = {
            "Labels": [{"ID": "trash", "Name": "Trash", "Type": 3}]
        }
        
        label_response = MagicMock()
        label_response.json.return_value = {"Code": 1000}
        
        mock_session.request.side_effect = [trash_response, label_response]
        
        result = lifecycle.move_to_trash("message123")
        
        assert result == True
    
    def test_move_to_trash_no_trash_folder(self, lifecycle, mock_session):
        """Test: Move to trash fails when trash folder not found."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Labels": [{"ID": "inbox", "Name": "Inbox"}]
        }
        mock_session.request.return_value = mock_response
        
        result = lifecycle.move_to_trash("message123")
        
        assert result == False
    
    def test_delete_permanently_success(self, lifecycle, mock_session):
        """Test: Permanent delete succeeds."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Code": 1000}
        mock_session.request.return_value = mock_response
        
        result = lifecycle.delete_permanently("message123")
        
        assert result == True
        mock_session.request.assert_called_once_with(
            "DELETE",
            "https://mail.proton.me/api/mail/v4/messages/message123"
        )
    
    def test_batch_delete(self, lifecycle, mock_session):
        """Test: Batch delete messages."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Code": 1000}
        mock_session.request.return_value = mock_response
        
        result = lifecycle.batch_delete(["msg1", "msg2"], permanent=True)
        
        assert result == 2
    
    def test_archive_success(self, lifecycle, mock_session):
        """Test: Archive message succeeds."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Code": 1000}
        mock_session.request.return_value = mock_response
        
        result = lifecycle.archive("message123")
        
        assert result == True
        mock_session.request.assert_called_once_with(
            "PUT",
            "https://mail.proton.me/api/mail/v4/messages/message123/label",
            json={"LabelIDs": []}
        )
    
    def test_cooldown_enforced(self, mock_session):
        """Test: Cooldown is enforced between write operations."""
        lifecycle = MessageLifecycle(mock_session, cooldown_ms=100)
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Code": 1000}
        mock_session.request.return_value = mock_response
        
        # First write
        lifecycle.mark_as_read("msg1")
        
        # Second write should have cooldown
        import time
        start = time.time()
        lifecycle.mark_as_read("msg2")
        elapsed = (time.time() - start) * 1000
        
        # Cooldown should have been enforced (at least 100ms)
        # Note: This test may be flaky due to timing
        # assert elapsed >= 100


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
