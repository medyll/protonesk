#!/usr/bin/env python3
"""
Proton Mail Bridge — Event Loop

Polls Proton's event API and distributes events to IMAP IDLE subscribers.

Proton event API: GET /core/v4/events/{EventID}
- Long-poll: server holds connection ~25s if no events, returns immediately on new event
- EventID: opaque cursor — use returned EventID for next poll
- Messages[].Action: 0=delete, 1=create, 2=update
- Labels[].Action: same
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

EVENT_POLL_TIMEOUT = 25  # seconds — Proton long-poll window
EVENT_RETRY_DELAY = 5  # seconds — delay after failed poll


class IMAPEvent:
    """Parsed IMAP-relevant event from Proton event stream."""

    ACTION_DELETE = 0
    ACTION_CREATE = 1
    ACTION_UPDATE = 2

    def __init__(self, event_type: str, label_id: str, count: Optional[int] = None,
                 seq: Optional[int] = None):
        self.event_type = event_type   # "exists", "expunge", "cache_invalid"
        self.label_id = label_id       # Proton label ID
        self.count = count             # new EXISTS count (for "exists")
        self.seq = seq                 # sequence number (for "expunge")


class ProtonEventLoop:
    """
    Asyncio task that polls Proton's event stream and fans out to subscribers.

    Subscribers register an asyncio.Queue per (label_id).
    On event: put IMAPEvent into all matching queues.

    Usage:
        loop = ProtonEventLoop(api_client)
        await loop.start()
        q = asyncio.Queue()
        loop.subscribe("0", q)   # label "0" = INBOX
        # ... IDLE session waits on q.get()
        loop.unsubscribe("0", q)
        await loop.stop()
    """

    def __init__(self, api_client, poll_timeout: int = EVENT_POLL_TIMEOUT):
        self.api = api_client
        self.poll_timeout = poll_timeout
        self._last_event_id: Optional[str] = None
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}  # label_id → queues
        self._task: Optional[asyncio.Task] = None
        self._running = False

    # ── Subscription API ──────────────────────────────────────────────────────

    def subscribe(self, label_id: str, queue: asyncio.Queue):
        """Register queue to receive events for label_id."""
        if label_id not in self._subscribers:
            self._subscribers[label_id] = set()
        self._subscribers[label_id].add(queue)
        logger.debug(f"EventLoop: subscribed queue to label '{label_id}'")

    def unsubscribe(self, label_id: str, queue: asyncio.Queue):
        """Remove queue from label_id subscribers."""
        if label_id in self._subscribers:
            self._subscribers[label_id].discard(queue)
            if not self._subscribers[label_id]:
                del self._subscribers[label_id]
        logger.debug(f"EventLoop: unsubscribed queue from label '{label_id}'")

    def subscriber_count(self) -> int:
        return sum(len(qs) for qs in self._subscribers.values())

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        """Fetch initial EventID and start polling task."""
        self._last_event_id = await self._fetch_latest_event_id()
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(), name="proton-event-loop")
        logger.info(f"EventLoop started (last_event_id={self._last_event_id})")

    async def stop(self):
        """Stop polling task."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("EventLoop stopped")

    # ── Polling ───────────────────────────────────────────────────────────────

    async def _fetch_latest_event_id(self) -> str:
        """Fetch the current latest EventID to use as starting cursor."""
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.api._request("GET", "/core/v4/events/latest")
            )
            event_id = response.get("EventID", "")
            logger.debug(f"EventLoop: initial EventID = {event_id}")
            return event_id
        except Exception as e:
            logger.warning(f"EventLoop: could not fetch initial EventID: {e}")
            return ""

    async def _poll_once(self) -> Optional[Dict[str, Any]]:
        """Poll for next event batch. Returns response dict or None on error."""
        if not self._last_event_id:
            return None
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.api._request("GET", f"/core/v4/events/{self._last_event_id}")
            )
            return response
        except Exception as e:
            logger.warning(f"EventLoop: poll error: {e}")
            return None

    async def _poll_loop(self):
        """Main polling loop — runs until stop() called."""
        while self._running:
            try:
                response = await asyncio.wait_for(
                    self._poll_once(), timeout=self.poll_timeout + 5
                )

                if response is None:
                    await asyncio.sleep(EVENT_RETRY_DELAY)
                    continue

                new_event_id = response.get("EventID")
                if new_event_id and new_event_id != self._last_event_id:
                    self._last_event_id = new_event_id
                    await self._dispatch(response)

                # No events → immediate retry (server already held for poll_timeout)

            except asyncio.TimeoutError:
                logger.debug("EventLoop: poll timeout, retrying")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EventLoop: unexpected error: {e}")
                await asyncio.sleep(EVENT_RETRY_DELAY)

    # ── Event dispatch ────────────────────────────────────────────────────────

    async def _dispatch(self, response: Dict[str, Any]):
        """Parse event response and fan out to subscribers."""
        messages = response.get("Messages", [])
        labels_changed = response.get("Labels", [])

        # Group message events by label
        exists_by_label: Dict[str, int] = {}
        expunge_by_label: Dict[str, List[str]] = {}

        for msg_event in messages:
            action = msg_event.get("Action")
            message = msg_event.get("Message", {})
            label_ids = message.get("LabelIDs", [])

            for label_id in label_ids:
                if action == IMAPEvent.ACTION_CREATE:
                    exists_by_label[label_id] = exists_by_label.get(label_id, 0) + 1
                elif action == IMAPEvent.ACTION_DELETE:
                    if label_id not in expunge_by_label:
                        expunge_by_label[label_id] = []
                    expunge_by_label[label_id].append(msg_event.get("ID", ""))

        # Publish EXISTS events
        for label_id, delta in exists_by_label.items():
            event = IMAPEvent("exists", label_id, count=delta)
            await self._publish(label_id, event)

        # Publish EXPUNGE events
        for label_id, msg_ids in expunge_by_label.items():
            for _ in msg_ids:
                event = IMAPEvent("expunge", label_id)
                await self._publish(label_id, event)

        # Label changes → cache invalid
        for label_event in labels_changed:
            label_id = label_event.get("ID", "")
            event = IMAPEvent("cache_invalid", label_id)
            await self._publish(label_id, event)

        if messages or labels_changed:
            logger.debug(
                f"EventLoop: dispatched {len(messages)} message events, "
                f"{len(labels_changed)} label events"
            )

    async def _publish(self, label_id: str, event: IMAPEvent):
        """Put event into all queues subscribed to label_id."""
        queues = self._subscribers.get(label_id, set()).copy()
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"EventLoop: subscriber queue full for label '{label_id}', dropping event")
