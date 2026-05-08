#!/usr/bin/env python3
"""Tests for SessionManager — S4-02"""

import pytest
from unittest.mock import patch, MagicMock


class TestSessionManager:

    def test_connect_all_returns_dict_of_sessions(self):
        from src.session_manager import SessionManager
        accounts = [
            {"username": "a@proton.me", "label": "perso"},
            {"username": "b@proton.me", "label": "pro"},
        ]

        mock_auth = MagicMock()
        mock_session = MagicMock()
        mock_api = MagicMock()
        mock_auth.authenticate.return_value = mock_session

        with patch("src.auth.ProtonAuth", return_value=mock_auth), \
             patch("src.api_client.ProtonAPIClient", return_value=mock_api), \
             patch("src.secrets.SecretManager") as mock_secrets:
            mock_secrets.return_value.get_secret.return_value = "fakepass"
            manager = SessionManager()
            result = manager.connect_all(accounts)

        assert "perso" in result
        assert "pro" in result
        assert result["perso"]["auth"] == mock_auth
        assert result["perso"]["session"] == mock_session
        assert result["perso"]["api_client"] == mock_api
        assert result["perso"]["username"] == "a@proton.me"

    def test_get_returns_session_for_label(self):
        from src.session_manager import SessionManager, SessionError
        accounts = [{"username": "x@proton.me", "label": "solo"}]

        mock_auth = MagicMock()
        mock_session = MagicMock()
        mock_api = MagicMock()
        mock_auth.authenticate.return_value = mock_session

        with patch("src.auth.ProtonAuth", return_value=mock_auth), \
             patch("src.api_client.ProtonAPIClient", return_value=mock_api), \
             patch("src.secrets.SecretManager") as mock_secrets:
            mock_secrets.return_value.get_secret.return_value = "pass"
            manager = SessionManager()
            manager.connect_all(accounts)

        info = manager.get("solo")
        assert info["username"] == "x@proton.me"

    def test_get_raises_error_for_unknown_label(self):
        from src.session_manager import SessionManager, SessionError
        manager = SessionManager()
        with pytest.raises(SessionError, match="No session found"):
            manager.get("nonexistent")

    def test_reconnect_replaces_session(self):
        from src.session_manager import SessionManager
        accounts = [{"username": "r@proton.me", "label": "reconnect_test"}]

        mock_auth1 = MagicMock()
        mock_session1 = MagicMock()
        mock_api1 = MagicMock()
        mock_auth1.authenticate.return_value = mock_session1

        mock_auth2 = MagicMock()
        mock_session2 = MagicMock()
        mock_api2 = MagicMock()
        mock_auth2.authenticate.return_value = mock_session2

        with patch("src.auth.ProtonAuth", side_effect=[mock_auth1, mock_auth2]), \
             patch("src.api_client.ProtonAPIClient", side_effect=[mock_api1, mock_api2]), \
             patch("src.secrets.SecretManager") as mock_secrets:
            mock_secrets.return_value.get_secret.return_value = "pass"
            manager = SessionManager()
            manager.connect_all(accounts)
            original_session = manager.get("reconnect_test")["session"]

            result = manager.reconnect("reconnect_test")

        assert result["session"] == mock_session2
        assert original_session != mock_session2

    def test_reconnect_raises_error_for_unknown_label(self):
        from src.session_manager import SessionManager, SessionError
        manager = SessionManager()
        with pytest.raises(SessionError, match="No session found"):
            manager.reconnect("nonexistent")

    def test_logout_all_clears_sessions(self):
        from src.session_manager import SessionManager
        accounts = [
            {"username": "a@proton.me", "label": "one"},
            {"username": "b@proton.me", "label": "two"},
        ]

        mock_auth = MagicMock()
        mock_session = MagicMock()
        mock_api = MagicMock()
        mock_auth.authenticate.return_value = mock_session

        with patch("src.auth.ProtonAuth", return_value=mock_auth), \
             patch("src.api_client.ProtonAPIClient", return_value=mock_api), \
             patch("src.secrets.SecretManager") as mock_secrets:
            mock_secrets.return_value.get_secret.return_value = "pass"
            manager = SessionManager()
            manager.connect_all(accounts)
            manager.logout_all()

        assert len(manager.labels) == 0

    def test_labels_property(self):
        from src.session_manager import SessionManager
        accounts = [
            {"username": "a@proton.me", "label": "alpha"},
            {"username": "b@proton.me", "label": "beta"},
        ]

        mock_auth = MagicMock()
        mock_session = MagicMock()
        mock_api = MagicMock()
        mock_auth.authenticate.return_value = mock_session

        with patch("src.auth.ProtonAuth", return_value=mock_auth), \
             patch("src.api_client.ProtonAPIClient", return_value=mock_api), \
             patch("src.secrets.SecretManager") as mock_secrets:
            mock_secrets.return_value.get_secret.return_value = "pass"
            manager = SessionManager()
            manager.connect_all(accounts)

        assert set(manager.labels) == {"alpha", "beta"}

    def test_is_multi_account(self):
        from src.session_manager import SessionManager
        accounts = [
            {"username": "a@proton.me", "label": "a"},
            {"username": "b@proton.me", "label": "b"},
        ]

        mock_auth = MagicMock()
        mock_session = MagicMock()
        mock_api = MagicMock()
        mock_auth.authenticate.return_value = mock_session

        with patch("src.auth.ProtonAuth", return_value=mock_auth), \
             patch("src.api_client.ProtonAPIClient", return_value=mock_api), \
             patch("src.secrets.SecretManager") as mock_secrets:
            mock_secrets.return_value.get_secret.return_value = "pass"
            manager = SessionManager()
            assert not manager.is_multi_account
            manager.connect_all(accounts)
            assert manager.is_multi_account

    def test_connect_all_fails_raises_session_error(self):
        from src.session_manager import SessionManager, SessionError
        accounts = [{"username": "fail@proton.me", "label": "bad"}]

        with patch("src.auth.ProtonAuth") as mock_auth_cls:
            mock_auth_cls.side_effect = Exception("auth failed")
            manager = SessionManager()
            with pytest.raises(SessionError, match="connection failed"):
                manager.connect_all(accounts)

    def test_reconnect_uses_label_specific_credentials(self):
        from src.session_manager import SessionManager
        accounts = [{"username": "labelled@proton.me", "label": "mylabel"}]

        mock_auth = MagicMock()
        mock_session = MagicMock()
        mock_api = MagicMock()
        mock_auth.authenticate.return_value = mock_session

        call_args = []

        def track_get_secret(key):
            call_args.append(key)
            return "tracked_pass"

        with patch("src.auth.ProtonAuth", return_value=mock_auth), \
             patch("src.api_client.ProtonAPIClient", return_value=mock_api), \
             patch("src.secrets.SecretManager") as mock_secrets:
            mock_secrets.return_value.get_secret.side_effect = track_get_secret
            manager = SessionManager()
            manager.connect_all(accounts)
            manager.reconnect("mylabel")

        assert "proton_password_mylabel" in call_args
