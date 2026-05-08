#!/usr/bin/env python3
"""Tests for IMAP bridge — S2-03 + S2-04"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def mock_api():
    api = MagicMock()
    api.get_labels.return_value = [
        {"ID": "0", "Name": "Inbox"},
        {"ID": "5", "Name": "Sent"},
        {"ID": "2", "Name": "Trash"},
    ]
    api.get_messages.return_value = [
        {"ID": "msg1", "Unread": 1, "Subject": "Test 1"},
        {"ID": "msg2", "Unread": 0, "Subject": "Test 2"},
        {"ID": "msg3", "Unread": 1, "Subject": "Test 3"},
    ]
    api.get_message.return_value = {
        "ID": "msg1",
        "Subject": "Test 1",
        "Sender": {"Address": "sender@proton.me"},
        "ToList": [{"Address": "me@proton.me"}],
        "Time": 1746612000,
        "Body": "-----BEGIN PGP MESSAGE-----\ntest\n-----END PGP MESSAGE-----",
        "Unread": 1,
    }
    return api


@pytest.fixture
def mock_crypto():
    crypto = MagicMock()
    crypto.decrypt_message_body.return_value = "Hello, this is the decrypted body."
    return crypto


@pytest.fixture
def bridge(mock_api, mock_crypto):
    from src.imap_bridge import ProtonIMAPBridge
    return ProtonIMAPBridge(mock_api, mock_crypto, local_password="testpass")


class TestAuth:
    def test_correct_password(self, bridge):
        assert bridge.authenticate("user", "testpass") is True

    def test_wrong_password(self, bridge):
        assert bridge.authenticate("user", "wrong") is False


class TestMailboxes:
    @pytest.mark.asyncio
    async def test_get_mailboxes_from_labels(self, bridge, mock_api):
        mailboxes = await bridge.get_mailboxes()
        assert "INBOX" in mailboxes
        assert "Sent" in mailboxes
        assert "Trash" in mailboxes

    @pytest.mark.asyncio
    async def test_get_mailboxes_cached(self, bridge, mock_api):
        await bridge.get_mailboxes()
        await bridge.get_mailboxes()
        mock_api.get_labels.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_mailboxes_fallback_on_error(self, bridge, mock_api):
        mock_api.get_labels.side_effect = Exception("API error")
        bridge._cache.invalidate("mailboxes")
        mailboxes = await bridge.get_mailboxes()
        assert len(mailboxes) > 0

    @pytest.mark.asyncio
    async def test_get_mailbox_status_inbox(self, bridge):
        status = await bridge.get_mailbox_status("INBOX")
        assert status is not None
        assert status["exists"] == 3
        assert status["unseen"] == 2

    @pytest.mark.asyncio
    async def test_get_mailbox_status_unknown(self, bridge):
        status = await bridge.get_mailbox_status("NONEXISTENT")
        assert status is None

    @pytest.mark.asyncio
    async def test_get_mailbox_status_cached(self, bridge, mock_api):
        await bridge.get_mailbox_status("INBOX")
        await bridge.get_mailbox_status("INBOX")
        mock_api.get_messages.assert_called_once()


class TestSeqMapping:
    @pytest.mark.asyncio
    async def test_seq_to_proton_id(self, bridge):
        await bridge.get_mailbox_status("INBOX")
        assert bridge.seq_to_proton_id("INBOX", 1) == "msg1"
        assert bridge.seq_to_proton_id("INBOX", 2) == "msg2"
        assert bridge.seq_to_proton_id("INBOX", 3) == "msg3"

    @pytest.mark.asyncio
    async def test_seq_out_of_range(self, bridge):
        await bridge.get_mailbox_status("INBOX")
        assert bridge.seq_to_proton_id("INBOX", 99) is None
        assert bridge.seq_to_proton_id("INBOX", 0) is None

    def test_proton_flags_unread(self, bridge, mock_api):
        msg = {"Unread": 1}
        assert "\\Seen" not in bridge.proton_flags(msg)

    def test_proton_flags_read(self, bridge, mock_api):
        msg = {"Unread": 0}
        assert "\\Seen" in bridge.proton_flags(msg)


class TestFetch:
    @pytest.mark.asyncio
    async def test_fetch_rfc822_format(self, bridge):
        await bridge.get_mailbox_status("INBOX")
        rfc822 = await bridge.fetch_message_rfc822("msg1")
        assert "From: sender@proton.me" in rfc822
        assert "Subject: Test 1" in rfc822
        assert "Hello, this is the decrypted body." in rfc822

    @pytest.mark.asyncio
    async def test_fetch_decrypt_failure_placeholder(self, bridge, mock_crypto):
        mock_crypto.decrypt_message_body.side_effect = Exception("bad key")
        bridge._cache.invalidate("msg:msg1")
        rfc822 = await bridge.fetch_message_rfc822("msg1")
        assert "decryption failed" in rfc822.lower()

    @pytest.mark.asyncio
    async def test_fetch_cached(self, bridge, mock_api):
        await bridge.fetch_message_rfc822("msg1")
        await bridge.fetch_message_rfc822("msg1")
        mock_api.get_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_fetch_message_not_found(self, bridge):
        session = MagicMock()
        session.send_tagged = AsyncMock()
        session.send_untagged = AsyncMock()
        session.send = AsyncMock()
        await bridge.handle_fetch("A1", "99 (RFC822)", "INBOX", session)
        session.send_tagged.assert_called_once()
        args = session.send_tagged.call_args[0]
        assert args[1] == "NO"

    @pytest.mark.asyncio
    async def test_handle_fetch_bad_seq(self, bridge):
        session = MagicMock()
        session.send_tagged = AsyncMock()
        await bridge.handle_fetch("A1", "abc (RFC822)", "INBOX", session)
        args = session.send_tagged.call_args[0]
        assert args[1] == "BAD"


class TestStore:
    @pytest.mark.asyncio
    async def test_handle_store_ok(self, bridge):
        await bridge.get_mailbox_status("INBOX")
        session = MagicMock()
        session.send_tagged = AsyncMock()
        session.send_untagged = AsyncMock()
        await bridge.handle_store("A1", "1 +FLAGS (\\Seen)", "INBOX", session)
        args = session.send_tagged.call_args[0]
        assert args[1] == "OK"

    @pytest.mark.asyncio
    async def test_handle_store_invalidates_cache(self, bridge):
        await bridge.get_mailbox_status("INBOX")
        session = MagicMock()
        session.send_tagged = AsyncMock()
        session.send_untagged = AsyncMock()
        assert bridge._cache.get("status:INBOX") is not None
        await bridge.handle_store("A1", "1 +FLAGS (\\Seen)", "INBOX", session)
        assert bridge._cache.get("status:INBOX") is None
