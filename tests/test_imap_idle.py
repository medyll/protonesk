#!/usr/bin/env python3
"""Tests for IMAP IDLE — S3-03"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock


def make_session_idle(bridge, idle_input_lines, mailbox="INBOX"):
    """Helper: session pre-authenticated and mailbox selected, then IDLE input."""
    from src.imap_server import IMAPSession

    data = b"\r\n".join(line.encode() for line in idle_input_lines) + b"\r\n"
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()

    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 9999)
    written = []
    writer.write = lambda d: written.append(d.decode())
    writer.drain = AsyncMock()
    writer.close = MagicMock()

    session = IMAPSession(reader, writer, bridge)
    session.state = session.STATE_SELECTED
    session.selected_mailbox = mailbox
    return session, written


@pytest.fixture
def mock_bridge_idle():
    bridge = MagicMock()
    bridge.authenticate.return_value = True
    bridge.get_mailbox_status = AsyncMock(return_value={
        "exists": 5, "recent": 0, "unseen": 2
    })
    bridge.handle_fetch = AsyncMock()
    bridge.handle_store = AsyncMock()
    bridge.get_mailboxes = AsyncMock(return_value=["INBOX"])
    # Force polling path — no event loop attached
    del bridge.subscribe
    del bridge.unsubscribe
    return bridge


class TestIMAPIdle:

    @pytest.mark.asyncio
    async def test_idle_requires_selected_state(self, mock_bridge_idle):
        """IDLE rejected if no mailbox selected."""
        from src.imap_server import IMAPSession

        reader = asyncio.StreamReader()
        reader.feed_data(b"A1 LOGOUT\r\n")
        reader.feed_eof()
        writer = MagicMock()
        writer.get_extra_info.return_value = ("127.0.0.1", 0)
        written = []
        writer.write = lambda d: written.append(d.decode())
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        session = IMAPSession(reader, writer, mock_bridge_idle)
        session.state = session.STATE_AUTH  # not selected
        session.selected_mailbox = None

        await session._cmd_idle("A1", "")
        assert any("NO" in line for line in written)

    @pytest.mark.asyncio
    async def test_idle_sends_idling_continuation(self, mock_bridge_idle):
        """IDLE starts with '+ idling' response."""
        session, written = make_session_idle(mock_bridge_idle, ["DONE"])
        await session._cmd_idle("A1", "")
        assert any("+ idling" in line for line in written)

    @pytest.mark.asyncio
    async def test_idle_terminates_on_done(self, mock_bridge_idle):
        """IDLE exits when client sends DONE."""
        session, written = make_session_idle(mock_bridge_idle, ["DONE"])
        await session._cmd_idle("A1", "")
        assert any("A1 OK" in line for line in written)

    @pytest.mark.asyncio
    async def test_idle_pushes_exists_on_new_message(self, mock_bridge_idle):
        """IDLE pushes '* N EXISTS' when message count changes between polls."""
        call_count = [0]

        async def dynamic_status(mailbox):
            call_count[0] += 1
            return {"exists": 5 + call_count[0], "recent": 0, "unseen": 0}

        mock_bridge_idle.get_mailbox_status = dynamic_status

        # Two polls then DONE: first sets baseline, second triggers EXISTS push
        # Use very short interval so test is fast
        import src.imap_server as imap_mod
        original_interval = imap_mod.IDLE_POLL_INTERVAL
        original_max = imap_mod.IDLE_MAX_DURATION

        # reader feeds "DONE" after a tiny delay simulation — put it after timeout
        reader = asyncio.StreamReader()
        writer = MagicMock()
        writer.get_extra_info.return_value = ("127.0.0.1", 0)
        written = []
        writer.write = lambda d: written.append(d.decode())
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        from src.imap_server import IMAPSession
        session = IMAPSession(reader, writer, mock_bridge_idle)
        session.state = session.STATE_SELECTED
        session.selected_mailbox = "INBOX"

        imap_mod.IDLE_POLL_INTERVAL = 0.05  # 50ms
        imap_mod.IDLE_MAX_DURATION = 0.12   # 120ms → 2 poll cycles then exit

        try:
            await session._cmd_idle("A1", "")
        finally:
            imap_mod.IDLE_POLL_INTERVAL = original_interval
            imap_mod.IDLE_MAX_DURATION = original_max

        # After 2 polls: second poll sees count change → EXISTS pushed
        assert any("EXISTS" in line for line in written)
        assert any("A1 OK" in line for line in written)

    @pytest.mark.asyncio
    async def test_idle_capability_advertised(self, mock_bridge_idle):
        """IDLE capability included in CAPABILITY response."""
        from src.imap_server import IMAPSession

        reader = asyncio.StreamReader()
        reader.feed_data(b"A1 CAPABILITY\r\nA2 LOGOUT\r\n")
        reader.feed_eof()
        writer = MagicMock()
        writer.get_extra_info.return_value = ("127.0.0.1", 0)
        written = []
        writer.write = lambda d: written.append(d.decode())
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        session = IMAPSession(reader, writer, mock_bridge_idle)
        await session.run()
        assert any("IDLE" in line for line in written)
