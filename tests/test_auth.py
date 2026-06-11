#!/usr/bin/env python3
"""
Tests unitaires — Auth Engine (SRP Authentication)

Run: pytest tests/test_auth.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# Import module à tester
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from auth import ProtonAuth


class TestProtonAuth:
    """Tests pour ProtonAuth."""

    @pytest.fixture(autouse=True)
    def isolate_session_file(self, tmp_path, monkeypatch):
        """Keep session persistence out of the user's real ~/.protonesk."""
        import auth
        monkeypatch.setattr(auth, "SESSION_FILE", tmp_path / "session.json")

    @patch('auth.get_credentials', side_effect=SystemExit)
    def test_init_missing_credentials(self, mock_get_credentials):
        """Test: Init fails without credentials — raises ValueError with setup instructions."""
        with pytest.raises((ValueError, SystemExit)):
            ProtonAuth()  # No credentials provided
    
    def test_init_with_credentials(self):
        """Test: Init succeeds with credentials."""
        auth = ProtonAuth(username='test@proton.me', password='testpassword')
        assert auth.username == 'test@proton.me'
        assert auth.password == 'testpassword'
    
    def test_init_with_totp(self):
        """Test: Init with TOTP secret."""
        auth = ProtonAuth(
            username='test@proton.me',
            password='testpassword',
            totp='JBSWY3DPEHPK3PXP'
        )
        assert auth.totp_secret == 'JBSWY3DPEHPK3PXP'
    
    @patch('auth.ProtonSession')
    def test_authenticate_success(self, mock_session_class):
        """Test: Authentication succeeds."""
        # Setup mock
        mock_session = MagicMock()
        mock_session.UID = "test-uid"
        mock_session.dump.return_value = {
            "api_url": "https://mail.proton.me/api",
            "appversion": "Other",
            "User-Agent": "Protonesk",
            "cookies": {},
            "session_data": {"UID": "test-uid"},
        }
        mock_session_class.return_value = mock_session

        auth = ProtonAuth(username='test@proton.me', password='testpassword')
        session = auth.authenticate()

        assert auth.session is not None
        assert auth.is_authenticated() == True
        mock_session.authenticate.assert_called_once_with('test@proton.me', 'testpassword')

    @patch('auth.ProtonSession')
    def test_authenticate_failure(self, mock_session_class):
        """Test: Authentication fails."""
        # Setup mock to raise exception
        mock_session_class.return_value.authenticate.side_effect = Exception("Invalid credentials")

        auth = ProtonAuth(username='test@proton.me', password='wrongpassword')

        with pytest.raises(ValueError, match="SRP authentication failed"):
            auth.authenticate()
    
    def test_logout(self):
        """Test: Logout clears session."""
        auth = ProtonAuth(username='test', password='test')
        mock_session = MagicMock()
        auth.session = mock_session
        
        auth.logout()
        
        assert auth.session is None
        mock_session.logout.assert_called_once()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
