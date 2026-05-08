#!/usr/bin/env python3
"""Tests for MultiAccountSMTPHandler — S4-04"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from email.mime.text import MIMEText
from aiosmtpd.smtp import Envelope


def make_envelope(from_addr, to_addrs, subject, body):
    """Create a mock Envelope with message content."""
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    envelope = MagicMock(spec=Envelope)
    envelope.mail_from = from_addr
    envelope.rcpt_tos = to_addrs
    envelope.content = msg.as_bytes()
    return envelope


class TestMultiAccountSMTPHandler:

    def _make_manager(self, labels=None):
        if labels is None:
            labels = ["perso", "pro"]
        mock_manager = MagicMock()
        mock_manager.labels = labels

        def mock_get(label):
            return {
                "username": f"{label}@proton.me",
                "session": MagicMock(),
                "auth": MagicMock(),
                "api_client": MagicMock(),
            }
        mock_manager.get.side_effect = mock_get
        return mock_manager

    def test_resolve_label_from_address(self):
        from src.multi_account_smtp import MultiAccountSMTPHandler
        mock_manager = self._make_manager(["perso", "pro"])
        mock_send = MagicMock()

        handler = MultiAccountSMTPHandler(mock_manager, {"perso": mock_send, "pro": mock_send})
        label = handler._resolve_label_from_address("perso@proton.me")
        assert label == "perso"

        label = handler._resolve_label_from_address("pro@proton.me")
        assert label == "pro"

    def test_resolve_label_unknown_returns_none(self):
        from src.multi_account_smtp import MultiAccountSMTPHandler
        mock_manager = self._make_manager(["solo"])
        mock_send = MagicMock()

        handler = MultiAccountSMTPHandler(mock_manager, {"solo": mock_send})
        label = handler._resolve_label_from_address("unknown@example.com")
        assert label is None

    def test_resolve_label_strips_angle_brackets(self):
        from src.multi_account_smtp import MultiAccountSMTPHandler
        mock_manager = self._make_manager(["alpha"])
        mock_send = MagicMock()

        handler = MultiAccountSMTPHandler(mock_manager, {"alpha": mock_send})
        label = handler._resolve_label_from_address("<alpha@proton.me>")
        assert label == "alpha"

    @pytest.mark.asyncio
    async def test_routes_to_correct_account(self):
        from src.multi_account_smtp import MultiAccountSMTPHandler
        mock_manager = self._make_manager(["sender", "other"])
        mock_send = MagicMock()
        mock_send.send_email.return_value = True

        handler = MultiAccountSMTPHandler(
            mock_manager, {"sender": mock_send, "other": MagicMock()}
        )
        envelope = make_envelope(
            "sender@proton.me", ["recipient@example.com"], "Test", "Hello"
        )
        mock_server = MagicMock()
        mock_session = MagicMock()

        result = await handler.handle_DATA(mock_server, mock_session, envelope)

        assert "250" in result
        mock_send.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_uses_default_when_from_unknown(self):
        from src.multi_account_smtp import MultiAccountSMTPHandler
        mock_manager = self._make_manager(["default_acc", "other"])
        mock_send = MagicMock()
        mock_send.send_email.return_value = True

        handler = MultiAccountSMTPHandler(
            mock_manager, {"default_acc": mock_send, "other": MagicMock()}
        )
        envelope = make_envelope(
            "unknown@example.com", ["recipient@example.com"], "Test", "Hello"
        )
        mock_server = MagicMock()
        mock_session = MagicMock()

        result = await handler.handle_DATA(mock_server, mock_session, envelope)

        assert "250" in result
        mock_send.send_email.assert_called_once()

    @pytest.mark.asyncio
    async def test_550_when_session_invalid(self):
        from src.multi_account_smtp import MultiAccountSMTPHandler
        mock_manager = self._make_manager(["broken"])

        def mock_get(label):
            return {
                "username": "broken@proton.me",
                "session": None,
                "auth": MagicMock(),
                "api_client": MagicMock(),
            }
        mock_manager.get.side_effect = mock_get

        mock_send = MagicMock()
        handler = MultiAccountSMTPHandler(mock_manager, {"broken": mock_send})
        envelope = make_envelope(
            "broken@proton.me", ["recipient@example.com"], "Test", "Hello"
        )
        mock_server = MagicMock()
        mock_session = MagicMock()

        result = await handler.handle_DATA(mock_server, mock_session, envelope)

        assert "550" in result
        mock_send.send_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_550_when_no_accounts(self):
        from src.multi_account_smtp import MultiAccountSMTPHandler
        mock_manager = MagicMock()
        mock_manager.labels = []

        handler = MultiAccountSMTPHandler(mock_manager, {})
        envelope = make_envelope(
            "any@example.com", ["recipient@example.com"], "Test", "Hello"
        )
        mock_server = MagicMock()
        mock_session = MagicMock()

        result = await handler.handle_DATA(mock_server, mock_session, envelope)

        assert "550" in result
        assert "No accounts" in result
