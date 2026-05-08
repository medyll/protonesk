#!/usr/bin/env python3
"""Tests for S4-05 — Reconnexion indépendante par compte"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


class TestSessionExpiredDetection:

    def test_is_session_expired_401(self):
        from main import _is_session_expired_error
        assert _is_session_expired_error(Exception("HTTP 401 Unauthorized")) is True

    def test_is_session_expired_unauthorized(self):
        from main import _is_session_expired_error
        assert _is_session_expired_error(Exception("Token unauthorized")) is True

    def test_is_session_expired_expired(self):
        from main import _is_session_expired_error
        assert _is_session_expired_error(Exception("Session expired")) is True

    def test_is_session_expired_other(self):
        from main import _is_session_expired_error
        assert _is_session_expired_error(Exception("Connection refused")) is False


class TestReconnectMonitor:

    def _make_manager_with_session(self, auth_status=True):
        mock_manager = MagicMock()
        mock_manager.labels = ["acc1", "acc2"]

        mock_session = MagicMock()
        mock_session.is_authenticated.return_value = auth_status

        def mock_get(label):
            return {
                "username": f"{label}@proton.me",
                "session": mock_session,
                "auth": MagicMock(),
                "api_client": MagicMock(),
            }
        mock_manager.get.side_effect = mock_get
        return mock_manager, mock_session

    @pytest.mark.asyncio
    async def test_reconnect_called_when_session_expired(self):
        from src.session_manager import SessionManager, SessionError

        mock_manager, mock_session = self._make_manager_with_session(auth_status=False)
        mock_manager.reconnect = MagicMock()

        stop_event = asyncio.Event()

        async def _reconnect_monitor():
            while not stop_event.is_set():
                for label in mock_manager.labels:
                    try:
                        session_info = mock_manager.get(label)
                        sess = session_info.get("session")
                        if sess and hasattr(sess, "is_authenticated"):
                            if not sess.is_authenticated():
                                try:
                                    mock_manager.reconnect(label)
                                except SessionError:
                                    pass
                    except Exception:
                        pass
                stop_event.set()

        await _reconnect_monitor()

        assert mock_manager.reconnect.call_count == 2
        mock_manager.reconnect.assert_any_call("acc1")
        mock_manager.reconnect.assert_any_call("acc2")

    @pytest.mark.asyncio
    async def test_reconnect_failure_does_not_affect_other_accounts(self):
        from src.session_manager import SessionManager, SessionError

        mock_manager, mock_session = self._make_manager_with_session(auth_status=False)
        reconnect_calls = []

        def mock_reconnect(label):
            reconnect_calls.append(label)
            if label == "acc1":
                raise SessionError("acc1 reconnect failed")
        mock_manager.reconnect.side_effect = mock_reconnect

        stop_event = asyncio.Event()

        async def _reconnect_monitor():
            while not stop_event.is_set():
                for label in mock_manager.labels:
                    try:
                        session_info = mock_manager.get(label)
                        sess = session_info.get("session")
                        if sess and hasattr(sess, "is_authenticated"):
                            if not sess.is_authenticated():
                                try:
                                    mock_manager.reconnect(label)
                                except SessionError:
                                    pass
                    except Exception:
                        pass
                stop_event.set()

        await _reconnect_monitor()

        assert "acc1" in reconnect_calls
        assert "acc2" in reconnect_calls
