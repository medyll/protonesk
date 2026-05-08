#!/usr/bin/env python3
"""Tests for MultiAccountBridge — S4-03"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestMailboxParser:

    def test_parse_prefixed(self):
        from src.multi_account_bridge import MailboxParser
        label, mb = MailboxParser.parse("perso/INBOX")
        assert label == "perso"
        assert mb == "INBOX"

    def test_parse_nested(self):
        from src.multi_account_bridge import MailboxParser
        label, mb = MailboxParser.parse("pro/Sent/2024")
        assert label == "pro"
        assert mb == "Sent/2024"

    def test_parse_no_prefix(self):
        from src.multi_account_bridge import MailboxParser
        label, mb = MailboxParser.parse("INBOX")
        assert label == ""
        assert mb == "INBOX"

    def test_build_with_label(self):
        from src.multi_account_bridge import MailboxParser
        assert MailboxParser.build("perso", "INBOX") == "perso/INBOX"

    def test_build_without_label(self):
        from src.multi_account_bridge import MailboxParser
        assert MailboxParser.build("", "INBOX") == "INBOX"


class TestMultiAccountBridge:

    def _make_manager(self, labels=None):
        """Create a mock SessionManager with given labels."""
        if labels is None:
            labels = ["perso", "pro"]

        mock_manager = MagicMock()
        mock_manager.labels = labels

        def mock_get(label):
            return {
                "api_client": MagicMock(),
                "session": MagicMock(),
                "auth": MagicMock(),
                "username": f"{label}@proton.me",
            }
        mock_manager.get.side_effect = mock_get
        return mock_manager

    def test_get_mailboxes_returns_prefixed(self):
        from src.multi_account_bridge import MultiAccountBridge
        mock_manager = self._make_manager(["perso", "pro"])

        async def mock_get_mailboxes():
            return ["INBOX", "Sent"]

        with patch("src.multi_account_bridge.ProtonIMAPBridge") as mock_bridge_cls:
            mock_bridge = MagicMock()
            mock_bridge.get_mailboxes = mock_get_mailboxes
            mock_bridge_cls.return_value = mock_bridge

            bridge = MultiAccountBridge(mock_manager, local_password="test")
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(bridge.get_mailboxes())

        assert "perso/INBOX" in result
        assert "perso/Sent" in result
        assert "pro/INBOX" in result
        assert "pro/Sent" in result

    def test_get_mailbox_status_resolves_label(self):
        from src.multi_account_bridge import MultiAccountBridge
        mock_manager = self._make_manager(["solo"])

        async def mock_get_mailboxes():
            return ["INBOX"]

        async def mock_get_mailbox_status(mb):
            return {"exists": 5, "recent": 0, "unseen": 2}

        with patch("src.multi_account_bridge.ProtonIMAPBridge") as mock_bridge_cls:
            mock_bridge = MagicMock()
            mock_bridge.get_mailboxes = mock_get_mailboxes
            mock_bridge.get_mailbox_status = mock_get_mailbox_status
            mock_bridge_cls.return_value = mock_bridge

            bridge = MultiAccountBridge(mock_manager, local_password="test")
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                bridge.get_mailbox_status("solo/INBOX")
            )

        assert result["exists"] == 5

    def test_backward_compat_single_account_no_prefix(self):
        from src.multi_account_bridge import MultiAccountBridge
        mock_manager = self._make_manager(["only"])

        async def mock_get_mailboxes():
            return ["INBOX"]

        async def mock_get_mailbox_status(mb):
            return {"exists": 10, "recent": 1, "unseen": 3}

        with patch("src.multi_account_bridge.ProtonIMAPBridge") as mock_bridge_cls:
            mock_bridge = MagicMock()
            mock_bridge.get_mailboxes = mock_get_mailboxes
            mock_bridge.get_mailbox_status = mock_get_mailbox_status
            mock_bridge_cls.return_value = mock_bridge

            bridge = MultiAccountBridge(mock_manager, local_password="test")
            import asyncio
            # Should work without prefix when only one account
            result = asyncio.get_event_loop().run_until_complete(
                bridge.get_mailbox_status("INBOX")
            )

        assert result["exists"] == 10

    def test_resolve_bridge_raises_for_unknown_label(self):
        from src.multi_account_bridge import MultiAccountBridge
        mock_manager = self._make_manager(["alpha"])

        with patch("src.multi_account_bridge.ProtonIMAPBridge"):
            bridge = MultiAccountBridge(mock_manager, local_password="test")

        with pytest.raises(KeyError, match="Unknown account label"):
            bridge._resolve_bridge("beta/INBOX")

    def test_resolve_bridge_raises_for_no_prefix_multi_account(self):
        from src.multi_account_bridge import MultiAccountBridge
        mock_manager = self._make_manager(["a", "b"])

        with patch("src.multi_account_bridge.ProtonIMAPBridge"):
            bridge = MultiAccountBridge(mock_manager, local_password="test")

        with pytest.raises(KeyError, match="no label prefix"):
            bridge._resolve_bridge("INBOX")

    def test_authenticate(self):
        from src.multi_account_bridge import MultiAccountBridge
        mock_manager = self._make_manager(["x"])

        with patch("src.multi_account_bridge.ProtonIMAPBridge"):
            bridge = MultiAccountBridge(mock_manager, local_password="secret")

        assert bridge.authenticate("user", "secret") is True
        assert bridge.authenticate("user", "wrong") is False

    @pytest.mark.asyncio
    async def test_handle_fetch_routes_to_correct_bridge(self):
        from src.multi_account_bridge import MultiAccountBridge
        mock_manager = self._make_manager(["perso", "pro"])

        mock_session = AsyncMock()

        with patch("src.multi_account_bridge.ProtonIMAPBridge") as mock_bridge_cls:
            mock_bridge = MagicMock()
            mock_bridge.handle_fetch = AsyncMock()
            mock_bridge_cls.return_value = mock_bridge

            bridge = MultiAccountBridge(mock_manager, local_password="test")
            await bridge.handle_fetch("TAG1", "1 RFC822", "perso/INBOX", mock_session)

        mock_bridge.handle_fetch.assert_called_once_with(
            "TAG1", "1 RFC822", "INBOX", mock_session
        )

    @pytest.mark.asyncio
    async def test_handle_fetch_fails_for_unknown_label(self):
        from src.multi_account_bridge import MultiAccountBridge
        mock_manager = self._make_manager(["perso"])
        mock_session = AsyncMock()

        with patch("src.multi_account_bridge.ProtonIMAPBridge"):
            bridge = MultiAccountBridge(mock_manager, local_password="test")
            await bridge.handle_fetch("TAG1", "1 RFC822", "unknown/INBOX", mock_session)

        mock_session.send_tagged.assert_called_once()
        call_args = mock_session.send_tagged.call_args[0]
        assert call_args[1] == "NO"
