#!/usr/bin/env python3
"""Tests for SMTP server — S2-01"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def mock_proton_send():
    send = MagicMock()
    send.send_email.return_value = True
    return send


@pytest.fixture
def smtp_handler(mock_proton_send):
    from src.smtp_server import ProtonSMTPHandler
    return ProtonSMTPHandler(mock_proton_send)


class TestProtonSMTPHandler:

    @pytest.mark.asyncio
    async def test_handle_rcpt_accepts_address(self, smtp_handler):
        envelope = MagicMock()
        envelope.rcpt_tos = []
        result = await smtp_handler.handle_RCPT(None, None, envelope, "to@example.com", [])
        assert result == "250 OK"
        assert "to@example.com" in envelope.rcpt_tos

    @pytest.mark.asyncio
    async def test_handle_data_plain_text_success(self, smtp_handler, mock_proton_send):
        envelope = MagicMock()
        envelope.mail_from = "from@proton.me"
        envelope.rcpt_tos = ["to@example.com"]
        envelope.content = (
            b"From: from@proton.me\r\n"
            b"To: to@example.com\r\n"
            b"Subject: Test\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"Hello world"
        )
        result = await smtp_handler.handle_DATA(None, None, envelope)
        assert "250" in result
        mock_proton_send.send_email.assert_called_once()
        call_kwargs = mock_proton_send.send_email.call_args[1]
        assert call_kwargs["subject"] == "Test"
        assert call_kwargs["sender"] == "from@proton.me"
        assert call_kwargs["recipients"] == ["to@example.com"]
        assert "Hello world" in call_kwargs["body"]

    @pytest.mark.asyncio
    async def test_handle_data_send_failure_returns_550(self, smtp_handler, mock_proton_send):
        mock_proton_send.send_email.return_value = False
        envelope = MagicMock()
        envelope.mail_from = "from@proton.me"
        envelope.rcpt_tos = ["to@example.com"]
        envelope.content = (
            b"From: from@proton.me\r\n"
            b"Subject: Fail\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"body"
        )
        result = await smtp_handler.handle_DATA(None, None, envelope)
        assert "550" in result

    @pytest.mark.asyncio
    async def test_handle_data_exception_returns_550(self, smtp_handler, mock_proton_send):
        mock_proton_send.send_email.side_effect = Exception("Unexpected error")
        envelope = MagicMock()
        envelope.mail_from = "from@proton.me"
        envelope.rcpt_tos = ["to@example.com"]
        envelope.content = (
            b"From: from@proton.me\r\n"
            b"Subject: Crash\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"body"
        )
        result = await smtp_handler.handle_DATA(None, None, envelope)
        assert "550" in result

    @pytest.mark.asyncio
    async def test_handle_data_no_subject_uses_default(self, smtp_handler, mock_proton_send):
        envelope = MagicMock()
        envelope.mail_from = "from@proton.me"
        envelope.rcpt_tos = ["to@example.com"]
        envelope.content = (
            b"From: from@proton.me\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"body"
        )
        await smtp_handler.handle_DATA(None, None, envelope)
        call_kwargs = mock_proton_send.send_email.call_args[1]
        assert "(no subject)" in call_kwargs["subject"]


class TestProtonSMTPServer:

    def test_server_init(self, mock_proton_send):
        from src.smtp_server import ProtonSMTPServer
        server = ProtonSMTPServer(mock_proton_send, host="127.0.0.1", port=1025)
        assert server.host == "127.0.0.1"
        assert server.port == 1025
        assert server._controller is None

    def test_server_start_stop(self, mock_proton_send):
        from src.smtp_server import ProtonSMTPServer
        server = ProtonSMTPServer(mock_proton_send)
        with patch("src.smtp_server.Controller") as MockController:
            mock_ctrl = MagicMock()
            MockController.return_value = mock_ctrl
            server.start()
            mock_ctrl.start.assert_called_once()
            server.stop()
            mock_ctrl.stop.assert_called_once()
