#!/usr/bin/env python3
"""Tests for event-driven IDLE — S5-02 + S5-03"""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock


# ── S5-02: subscribe/unsubscribe on bridges ───────────────────────────────────


class TestProtonIMAPBridgeSubscription:
    @pytest.fixture
    def bridge(self):
        from src.imap_bridge import ProtonIMAPBridge
        api = MagicMock()
        return ProtonIMAPBridge(api, None, local_password="test")

    def test_subscribe_stores_queue(self, bridge):
        q = asyncio.Queue()
        bridge.subscribe("0", q)
        assert "0" in bridge._subscribers
        assert q in bridge._subscribers["0"]

    def test_unsubscribe_removes_queue(self, bridge):
        q = asyncio.Queue()
        bridge.subscribe("0", q)
        bridge.unsubscribe("0", q)
        assert "0" not in bridge._subscribers

    def test_mailbox_to_label_id_known(self, bridge):
        assert bridge.mailbox_to_label_id("INBOX") == "0"
        assert bridge.mailbox_to_label_id("Sent") == "5"

    def test_mailbox_to_label_id_unknown(self, bridge):
        assert bridge.mailbox_to_label_id("NONEXISTENT") is None


class TestMultiAccountBridgeSubscription:
    @pytest.fixture
    def multi_bridge(self):
        from src.imap_bridge import ProtonIMAPBridge
        from src.multi_account_bridge import MultiAccountBridge

        mock_manager = MagicMock()
        mock_manager.labels = ["perso"]

        api = MagicMock()
        inner = ProtonIMAPBridge(api, None, local_password="test")
        mock_manager.get.return_value = {"api_client": api}

        bridge = MultiAccountBridge.__new__(MultiAccountBridge)
        bridge.session_manager = mock_manager
        bridge.crypto_map = {}
        bridge.local_password = "test"
        bridge._bridges = {"perso": inner}
        from src.multi_account_bridge import MailboxParser
        bridge._parser = MailboxParser()
        return bridge, inner

    def test_subscribe_routes_to_inner_bridge(self, multi_bridge):
        bridge, inner = multi_bridge
        q = asyncio.Queue()
        bridge.subscribe("perso/INBOX", q)
        assert q in inner._subscribers.get("0", set())

    def test_unsubscribe_routes_to_inner_bridge(self, multi_bridge):
        bridge, inner = multi_bridge
        q = asyncio.Queue()
        bridge.subscribe("perso/INBOX", q)
        bridge.unsubscribe("perso/INBOX", q)
        assert "0" not in inner._subscribers

    def test_subscribe_unknown_mailbox_no_error(self, multi_bridge):
        bridge, _ = multi_bridge
        q = asyncio.Queue()
        bridge.subscribe("unknown/INBOX", q)  # no exception


# ── S5-03: event-driven IDLE in IMAPSession ───────────────────────────────────


def make_idle_session(bridge, reader_data=b"DONE\r\n"):
    from src.imap_server import IMAPSession

    reader = asyncio.StreamReader()
    reader.feed_data(reader_data)
    reader.feed_eof()

    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 0)
    written = []
    writer.write = lambda d: written.append(d.decode())
    writer.drain = AsyncMock()
    writer.close = MagicMock()

    session = IMAPSession(reader, writer, bridge)
    session.state = session.STATE_SELECTED
    session.selected_mailbox = "INBOX"
    return session, written


class TestIdleEventDriven:
    @pytest.mark.asyncio
    async def test_idle_event_driven_terminates_on_done(self):
        """Event-driven IDLE exits cleanly on DONE."""
        from src.imap_bridge import ProtonIMAPBridge

        api = MagicMock()
        bridge = ProtonIMAPBridge(api, None, local_password="test")
        session, written = make_idle_session(bridge)

        await session._cmd_idle("A1", "")
        assert any("A1 OK" in line for line in written)

    @pytest.mark.asyncio
    async def test_idle_pushes_exists_on_event(self):
        """EXISTS pushed when create event arrives via queue."""
        from src.imap_bridge import ProtonIMAPBridge
        from src.event_loop import IMAPEvent

        api = MagicMock()
        bridge = ProtonIMAPBridge(api, None, local_password="test")
        bridge.get_mailbox_status = AsyncMock(return_value={"exists": 5, "recent": 0, "unseen": 0})

        # Capture the queue the session subscribes with, then inject event
        captured_queues = []
        original_subscribe = bridge.subscribe

        def capturing_subscribe(label_id, q):
            original_subscribe(label_id, q)
            captured_queues.append(q)

        bridge.subscribe = capturing_subscribe

        reader = asyncio.StreamReader()
        writer = MagicMock()
        writer.get_extra_info.return_value = ("127.0.0.1", 0)
        written = []
        writer.write = lambda d: written.append(d.decode())
        writer.drain = AsyncMock()
        writer.close = MagicMock()

        from src.imap_server import IMAPSession
        session = IMAPSession(reader, writer, bridge)
        session.state = session.STATE_SELECTED
        session.selected_mailbox = "INBOX"

        async def inject_event_then_done():
            # Wait for subscription to be registered
            for _ in range(20):
                if captured_queues:
                    break
                await asyncio.sleep(0.01)
            if captured_queues:
                event = IMAPEvent("exists", "0", count=1)
                captured_queues[0].put_nowait(event)
            await asyncio.sleep(0.05)
            reader.feed_data(b"DONE\r\n")
            reader.feed_eof()

        await asyncio.gather(session._cmd_idle("A1", ""), inject_event_then_done())
        assert any("EXISTS" in line for line in written)
        assert any("A1 OK" in line for line in written)

    @pytest.mark.asyncio
    async def test_idle_falls_back_to_polling_when_no_subscribe(self):
        """Falls back to polling if bridge has no subscribe method."""
        bridge = MagicMock()
        bridge.get_mailbox_status = AsyncMock(return_value={"exists": 3, "recent": 0, "unseen": 0})
        # Remove subscribe/unsubscribe to force polling path
        del bridge.subscribe
        del bridge.unsubscribe

        import src.imap_server as imap_mod
        orig_interval = imap_mod.IDLE_POLL_INTERVAL
        orig_max = imap_mod.IDLE_MAX_DURATION
        imap_mod.IDLE_POLL_INTERVAL = 0.05
        imap_mod.IDLE_MAX_DURATION = 0.12

        session, written = make_idle_session(bridge, reader_data=b"")

        try:
            await session._cmd_idle("A1", "")
        finally:
            imap_mod.IDLE_POLL_INTERVAL = orig_interval
            imap_mod.IDLE_MAX_DURATION = orig_max

        assert any("A1 OK" in line for line in written)

    @pytest.mark.asyncio
    async def test_idle_capability_still_advertised(self):
        """IDLE in CAPABILITIES after S5-03 changes."""
        from src.imap_server import CAPABILITIES
        assert "IDLE" in CAPABILITIES
