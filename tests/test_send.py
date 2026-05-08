#!/usr/bin/env python3
"""
Tests unitaires — Encrypted Email Send Flow

Run: pytest tests/test_send.py -v
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock, call

# Import module à tester
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from send import ProtonSend


class TestProtonSend:
    """Tests pour ProtonSend."""
    
    @pytest.fixture
    def mock_session(self):
        """Fixture: Mock session."""
        session = MagicMock()
        return session
    
    @pytest.fixture
    def mock_crypto(self):
        """Fixture: Mock crypto module."""
        crypto = MagicMock()
        crypto.encrypt_for_recipient.return_value = "-----BEGIN PGP MESSAGE-----\nencrypted\n-----END PGP MESSAGE-----"
        return crypto
    
    @pytest.fixture
    def sender(self, mock_session, mock_crypto):
        """Fixture: ProtonSend instance."""
        sender = ProtonSend(mock_session, mock_crypto)
        sender.cooldown_ms = 0  # No cooldown for tests
        return sender
    
    def test_get_recipient_keys_found(self, sender, mock_session):
        """Test: Get recipient keys when found."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Keys": [
                {"PublicKey": "-----BEGIN PGP PUBLIC KEY BLOCK-----\nkey1\n-----END PGP PUBLIC KEY BLOCK-----"},
                {"PublicKey": "-----BEGIN PGP PUBLIC KEY BLOCK-----\nkey2\n-----END PGP PUBLIC KEY BLOCK-----"}
            ]
        }
        mock_session.request.return_value = mock_response
        
        result = sender.get_recipient_keys("recipient@proton.me")
        
        assert len(result) == 2
        mock_session.request.assert_called_once_with(
            "GET",
            "https://mail.proton.me/api/mail/v4/keys/recipient@proton.me"
        )
    
    def test_get_recipient_keys_not_found(self, sender, mock_session):
        """Test: Get recipient keys when not found (external)."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Keys": []}
        mock_session.request.return_value = mock_response
        
        result = sender.get_recipient_keys("external@gmail.com")
        
        assert result == []  # Returns empty list, not dict
    
    def test_create_draft_success(self, sender, mock_session):
        """Test: Create draft succeeds."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Message": {"ID": "draft123"}
        }
        mock_session.request.return_value = mock_response
        
        result = sender.create_draft(
            subject="Test Subject",
            sender="me@proton.me",
            recipients=["them@example.com"],
            body="Hello!"
        )
        
        assert result == "draft123"
        mock_session.request.assert_called_once()
    
    def test_create_draft_with_thread_id(self, sender, mock_session):
        """Test: Create draft with ThreadID for replies."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Message": {"ID": "draft123"}
        }
        mock_session.request.return_value = mock_response
        
        result = sender.create_draft(
            subject="Re: Original",
            sender="me@proton.me",
            recipients=["them@example.com"],
            body="Reply!",
            thread_id="thread456"
        )
        
        assert result == "draft123"
        
        # Verify ThreadID was included
        call_args = mock_session.request.call_args
        assert call_args[1]['json']['Message']['ThreadID'] == "thread456"
    
    def test_create_draft_failure(self, sender, mock_session):
        """Test: Create draft fails."""
        # Setup mock to return no ID
        mock_response = MagicMock()
        mock_response.json.return_value = {"Message": {}}
        mock_session.request.return_value = mock_response
        
        with pytest.raises(ValueError, match="Failed to create draft"):
            sender.create_draft("Subject", "me@proton.me", ["them@example.com"], "Body")
    
    def test_encrypt_body(self, sender, mock_crypto):
        """Test: Encrypt message body."""
        body = "Secret message"
        keys = [{"PublicKey": "key1"}]
        
        result = sender.encrypt_body(body, keys)
        
        assert result.startswith("-----BEGIN PGP MESSAGE-----")
        mock_crypto.encrypt_for_recipient.assert_called_once_with(body, keys)
    
    def test_update_draft_success(self, sender, mock_session):
        """Test: Update draft with encrypted body."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Code": 1000}
        mock_session.request.return_value = mock_response
        
        result = sender.update_draft("draft123", "encrypted body")
        
        assert result == True
        mock_session.request.assert_called_once_with(
            "PUT",
            "https://mail.proton.me/api/mail/v4/messages/draft123",
            json={"Message": {"Body": "encrypted body", "MIMEType": "text/html"}}
        )
    
    def test_update_draft_failure(self, sender, mock_session):
        """Test: Update draft fails."""
        # Setup mock to raise exception
        mock_session.request.side_effect = Exception("API error")
        
        result = sender.update_draft("draft123", "encrypted body")
        
        assert result == False
    
    def test_send_draft_success(self, sender, mock_session):
        """Test: Send draft succeeds."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"Code": 1000}
        mock_session.request.return_value = mock_response
        
        result = sender.send_draft("draft123")
        
        assert result == True
        mock_session.request.assert_called_once_with(
            "POST",
            "https://mail.proton.me/api/mail/v4/messages/draft123/send"
        )
    
    def test_send_draft_failure(self, sender, mock_session):
        """Test: Send draft fails."""
        # Setup mock to raise exception
        mock_session.request.side_effect = Exception("Send failed")
        
        result = sender.send_draft("draft123")
        
        assert result == False
    
    @patch('send.ProtonSend._cooldown')
    def test_send_email_full_flow_success(self, mock_cooldown, sender, mock_session, mock_crypto):
        """Test: Complete send flow succeeds."""
        # Setup mock responses
        mock_session.request.side_effect = [
            MagicMock(json=MagicMock(return_value={"Keys": []})),  # get_recipient_keys
            MagicMock(json=MagicMock(return_value={"Message": {"ID": "draft123"}})),  # create_draft
            MagicMock(json=MagicMock(return_value={"Code": 1000})),  # update_draft
            MagicMock(json=MagicMock(return_value={"Code": 1000}))  # send_draft
        ]
        
        result = sender.send_email(
            subject="Test",
            sender="me@proton.me",
            recipients=["them@example.com"],
            body="Hello!"
        )
        
        assert result == True
        assert mock_session.request.call_count == 4
    
    def test_send_email_cleanup_on_failure(self, sender, mock_session, mock_crypto):
        """Test: Draft deleted on send failure (atomicity)."""
        # Setup mock responses
        mock_session.request.side_effect = [
            MagicMock(json=MagicMock(return_value={"Keys": []})),  # get_recipient_keys
            MagicMock(json=MagicMock(return_value={"Message": {"ID": "draft123"}})),  # create_draft
            MagicMock(json=MagicMock(return_value={"Code": 1000})),  # update_draft
            Exception("Send failed"),  # send_draft fails
            MagicMock(json=MagicMock(return_value={"Code": 1000}))  # cleanup delete
        ]
        
        result = sender.send_email(
            subject="Test",
            sender="me@proton.me",
            recipients=["them@example.com"],
            body="Hello!"
        )
        
        assert result == False
        # Verify cleanup was attempted (5th call = DELETE)
        assert mock_session.request.call_count >= 5


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
