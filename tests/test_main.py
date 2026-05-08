#!/usr/bin/env python3
"""Tests for daemon entry point — S2-05"""

import asyncio
import pytest
import argparse
from unittest.mock import MagicMock, AsyncMock, patch


def make_args(**kwargs):
    defaults = {
        "imap_port": 1143,
        "smtp_port": 1025,
        "imap_host": "127.0.0.1",
        "smtp_host": "127.0.0.1",
        "imap_only": False,
        "smtp_only": False,
        "local_password": "bridge",
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestParseArgs:
    def test_defaults(self):
        from main import parse_args
        with patch("sys.argv", ["main.py"]):
            args = parse_args()
        assert args.imap_port == 1143
        assert args.smtp_port == 1025
        assert args.imap_host == "127.0.0.1"
        assert args.imap_only is False
        assert args.smtp_only is False

    def test_custom_ports(self):
        from main import parse_args
        with patch("sys.argv", ["main.py", "--imap-port", "2143", "--smtp-port", "2025"]):
            args = parse_args()
        assert args.imap_port == 2143
        assert args.smtp_port == 2025

    def test_imap_only_flag(self):
        from main import parse_args
        with patch("sys.argv", ["main.py", "--imap-only"]):
            args = parse_args()
        assert args.imap_only is True
        assert args.smtp_only is False

    def test_smtp_only_flag(self):
        from main import parse_args
        with patch("sys.argv", ["main.py", "--smtp-only"]):
            args = parse_args()
        assert args.smtp_only is True
        assert args.imap_only is False


class TestConnectProton:
    def test_success_on_first_attempt(self):
        from main import connect_proton
        mock_auth_instance = MagicMock()
        mock_session = MagicMock()
        mock_client_instance = MagicMock()
        mock_auth_instance.authenticate.return_value = mock_session

        with patch("main.ProtonAuth", return_value=mock_auth_instance), \
             patch("main.ProtonAPIClient", return_value=mock_client_instance):
            auth, session, client = connect_proton()

        assert auth is mock_auth_instance
        assert session is mock_session
        assert client is mock_client_instance

    def test_retry_on_failure_then_success(self):
        from main import connect_proton
        mock_session = MagicMock()

        call_count = [0]

        def make_auth():
            inst = MagicMock()
            call_count[0] += 1
            if call_count[0] < 2:
                inst.authenticate.side_effect = Exception("Auth failed")
            else:
                inst.authenticate.return_value = mock_session
            return inst

        with patch("main.ProtonAuth", side_effect=make_auth), \
             patch("main.ProtonAPIClient"), \
             patch("main.time.sleep"):
            connect_proton()

        assert call_count[0] == 2

    def test_exits_after_max_retries(self):
        from main import connect_proton

        def make_failing_auth():
            inst = MagicMock()
            inst.authenticate.side_effect = Exception("Auth always fails")
            return inst

        with patch("main.ProtonAuth", side_effect=make_failing_auth), \
             patch("main.time.sleep"), \
             pytest.raises(SystemExit):
            connect_proton()


class TestRunImap:
    @pytest.mark.asyncio
    async def test_imap_only_skips_smtp(self):
        """imap_only=True: IMAP server starts, SMTP server never instantiated."""
        args = make_args(imap_only=True)

        mock_auth = MagicMock()
        mock_imap_server = MagicMock()
        mock_imap_server.start = AsyncMock()
        mock_imap_server.stop = AsyncMock()
        mock_smtp_cls = MagicMock()

        stop_event = asyncio.Event()
        stop_event.set()  # return immediately

        with patch("main.connect_proton", return_value=(mock_auth, MagicMock(), MagicMock())), \
             patch("main.ProtonIMAPBridge"), \
             patch("main.ProtonIMAPServer", return_value=mock_imap_server), \
             patch("main.ProtonSMTPServer", mock_smtp_cls), \
             patch("main.get_credentials", return_value={}), \
             patch("asyncio.Event", return_value=stop_event), \
             patch("signal.signal"):
            from main import run
            await run(args)

        mock_imap_server.start.assert_called_once()
        mock_smtp_cls.assert_not_called()
