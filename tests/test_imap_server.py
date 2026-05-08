#!/usr/bin/env python3
"""Tests for IMAP server core — S2-02"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def mock_bridge():
    bridge = MagicMock()
    bridge.authenticate.return_value = True
    bridge.get_mailboxes = AsyncMock(return_value=["INBOX", "Sent", "Trash"])
    bridge.get_mailbox_status = AsyncMock(return_value={
        "exists": 10, "recent": 0, "unseen": 3
    })
    bridge.handle_fetch = AsyncMock()
    bridge.handle_store = AsyncMock()
    return bridge


def make_session(bridge, input_lines):
    """Helper: create IMAPSession with mocked reader/writer."""
    from src.imap_server import IMAPSession

    data = b"\r\n".join(line.encode() for line in input_lines) + b"\r\n"
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
    return session, written


@pytest.mark.asyncio
async def test_greeting_on_connect(mock_bridge):
    session, written = make_session(mock_bridge, ["A1 LOGOUT"])
    await session.run()
    assert any("OK" in line and "ready" in line for line in written)


@pytest.mark.asyncio
async def test_capability_command(mock_bridge):
    session, written = make_session(mock_bridge, ["A1 CAPABILITY", "A2 LOGOUT"])
    await session.run()
    assert any("IMAP4rev1" in line for line in written)
    assert any("A1 OK" in line for line in written)


@pytest.mark.asyncio
async def test_noop_command(mock_bridge):
    session, written = make_session(mock_bridge, ["A1 NOOP", "A2 LOGOUT"])
    await session.run()
    assert any("A1 OK" in line for line in written)


@pytest.mark.asyncio
async def test_logout_command(mock_bridge):
    session, written = make_session(mock_bridge, ["A1 LOGOUT"])
    await session.run()
    assert any("BYE" in line for line in written)
    assert any("A1 OK" in line for line in written)


@pytest.mark.asyncio
async def test_login_success(mock_bridge):
    mock_bridge.authenticate.return_value = True
    session, written = make_session(mock_bridge, [
        'A1 LOGIN user@proton.me password123',
        "A2 LOGOUT"
    ])
    await session.run()
    assert any("A1 OK" in line for line in written)


@pytest.mark.asyncio
async def test_login_failure(mock_bridge):
    mock_bridge.authenticate.return_value = False
    session, written = make_session(mock_bridge, [
        'A1 LOGIN user@proton.me wrongpass',
        "A2 LOGOUT"
    ])
    await session.run()
    assert any("A1 NO" in line for line in written)


@pytest.mark.asyncio
async def test_list_requires_auth(mock_bridge):
    session, written = make_session(mock_bridge, [
        'A1 LIST "" "*"',
        "A2 LOGOUT"
    ])
    await session.run()
    assert any("A1 NO" in line for line in written)


@pytest.mark.asyncio
async def test_list_after_login(mock_bridge):
    session, written = make_session(mock_bridge, [
        'A1 LOGIN user pass',
        'A2 LIST "" "*"',
        "A3 LOGOUT"
    ])
    await session.run()
    assert any("INBOX" in line for line in written)
    assert any("A2 OK" in line for line in written)


@pytest.mark.asyncio
async def test_select_inbox(mock_bridge):
    session, written = make_session(mock_bridge, [
        'A1 LOGIN user pass',
        'A2 SELECT INBOX',
        "A3 LOGOUT"
    ])
    await session.run()
    assert any("EXISTS" in line for line in written)
    assert any("UNSEEN" in line for line in written)
    assert any("A2 OK" in line for line in written)


@pytest.mark.asyncio
async def test_select_nonexistent_mailbox(mock_bridge):
    mock_bridge.get_mailbox_status = AsyncMock(return_value=None)
    session, written = make_session(mock_bridge, [
        'A1 LOGIN user pass',
        'A2 SELECT NONEXISTENT',
        "A3 LOGOUT"
    ])
    await session.run()
    assert any("A2 NO" in line for line in written)


@pytest.mark.asyncio
async def test_fetch_requires_select(mock_bridge):
    session, written = make_session(mock_bridge, [
        'A1 LOGIN user pass',
        'A2 FETCH 1 (RFC822)',
        "A3 LOGOUT"
    ])
    await session.run()
    assert any("A2 NO" in line for line in written)


@pytest.mark.asyncio
async def test_unknown_command_returns_bad(mock_bridge):
    session, written = make_session(mock_bridge, [
        'A1 UNKNOWNCMD',
        "A2 LOGOUT"
    ])
    await session.run()
    assert any("A1 BAD" in line for line in written)


class TestProtonIMAPServer:
    def test_server_init(self, mock_bridge):
        from src.imap_server import ProtonIMAPServer
        server = ProtonIMAPServer(mock_bridge, host="127.0.0.1", port=1143)
        assert server.host == "127.0.0.1"
        assert server.port == 1143
        assert server._server is None

    @pytest.mark.asyncio
    async def test_server_start_stop(self, mock_bridge):
        from src.imap_server import ProtonIMAPServer
        server = ProtonIMAPServer(mock_bridge, port=11430)
        await server.start()
        assert server._server is not None
        await server.stop()
