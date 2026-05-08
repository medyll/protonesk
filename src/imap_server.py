#!/usr/bin/env python3
"""
Proton Mail Bridge — IMAP Server

Local IMAP4 server on 127.0.0.1:1143.
Implements RFC 3501 subset: CAPABILITY, LOGIN, SELECT, LIST, FETCH, STORE, LOGOUT, NOOP.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

IMAP_OK = "OK"
IMAP_NO = "NO"
IMAP_BAD = "BAD"

CAPABILITIES = "IMAP4rev1 LITERAL+ SASL-IR AUTH=PLAIN IDLE"
IDLE_POLL_INTERVAL = 30  # seconds between Proton API polls
IDLE_MAX_DURATION = 1740  # 29 minutes (RFC recommends < 30 min)


class IMAPSession:
    """State machine for one IMAP client connection."""

    STATE_NOT_AUTH = "not_authenticated"
    STATE_AUTH = "authenticated"
    STATE_SELECTED = "selected"
    STATE_LOGOUT = "logout"

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, bridge):
        self.reader = reader
        self.writer = writer
        self.bridge = bridge
        self.state = self.STATE_NOT_AUTH
        self.selected_mailbox: Optional[str] = None
        self.peer = writer.get_extra_info("peername")

    async def send(self, line: str):
        self.writer.write((line + "\r\n").encode())
        await self.writer.drain()

    async def send_untagged(self, data: str):
        await self.send(f"* {data}")

    async def send_tagged(self, tag: str, status: str, msg: str):
        await self.send(f"{tag} {status} {msg}")

    async def run(self):
        await self.send(f"* OK [CAPABILITY {CAPABILITIES}] Proton Bridge IMAP ready")
        logger.info(f"Client connected: {self.peer}")

        try:
            while self.state != self.STATE_LOGOUT:
                line = await asyncio.wait_for(self.reader.readline(), timeout=1800)
                if not line:
                    break
                await self._dispatch(line.decode().rstrip("\r\n"))
        except asyncio.TimeoutError:
            logger.info(f"Client timeout: {self.peer}")
        except ConnectionResetError:
            pass
        finally:
            self.writer.close()
            logger.info(f"Client disconnected: {self.peer}")

    async def _dispatch(self, line: str):
        if not line.strip():
            return

        parts = line.split(" ", 2)
        if len(parts) < 2:
            await self.send("* BAD Invalid command")
            return

        tag = parts[0]
        cmd = parts[1].upper()
        args = parts[2] if len(parts) > 2 else ""

        handlers = {
            "CAPABILITY": self._cmd_capability,
            "NOOP": self._cmd_noop,
            "LOGOUT": self._cmd_logout,
            "LOGIN": self._cmd_login,
            "IDLE": self._cmd_idle,
            "LIST": self._cmd_list,
            "SELECT": self._cmd_select,
            "EXAMINE": self._cmd_examine,
            "FETCH": self._cmd_fetch,
            "STORE": self._cmd_store,
        }

        handler = handlers.get(cmd)
        if handler:
            await handler(tag, args)
        else:
            await self.send_tagged(tag, IMAP_BAD, f"Unknown command: {cmd}")

    async def _cmd_capability(self, tag: str, args: str):
        await self.send_untagged(f"CAPABILITY {CAPABILITIES}")
        await self.send_tagged(tag, IMAP_OK, "CAPABILITY completed")

    async def _cmd_noop(self, tag: str, args: str):
        await self.send_tagged(tag, IMAP_OK, "NOOP completed")

    async def _cmd_logout(self, tag: str, args: str):
        await self.send_untagged("BYE Proton Bridge logging out")
        await self.send_tagged(tag, IMAP_OK, "LOGOUT completed")
        self.state = self.STATE_LOGOUT

    async def _cmd_login(self, tag: str, args: str):
        if self.state != self.STATE_NOT_AUTH:
            await self.send_tagged(tag, IMAP_BAD, "Already authenticated")
            return

        parts = args.split(" ", 1)
        if len(parts) < 2:
            await self.send_tagged(tag, IMAP_BAD, "LOGIN requires username and password")
            return

        username = parts[0].strip('"')
        password = parts[1].strip('"')

        if self.bridge.authenticate(username, password):
            self.state = self.STATE_AUTH
            await self.send_tagged(tag, IMAP_OK, "LOGIN completed")
            logger.info(f"Authenticated: {username} from {self.peer}")
        else:
            await self.send_tagged(tag, IMAP_NO, "LOGIN failed")

    async def _cmd_list(self, tag: str, args: str):
        if self.state == self.STATE_NOT_AUTH:
            await self.send_tagged(tag, IMAP_NO, "Not authenticated")
            return

        mailboxes = await self.bridge.get_mailboxes()
        for mailbox in mailboxes:
            await self.send_untagged(f'LIST (\\HasNoChildren) "/" "{mailbox}"')
        await self.send_tagged(tag, IMAP_OK, "LIST completed")

    async def _cmd_select(self, tag: str, args: str, readonly: bool = False):
        if self.state == self.STATE_NOT_AUTH:
            await self.send_tagged(tag, IMAP_NO, "Not authenticated")
            return

        mailbox = args.strip().strip('"')
        status = await self.bridge.get_mailbox_status(mailbox)

        if status is None:
            await self.send_tagged(tag, IMAP_NO, f"Mailbox {mailbox} does not exist")
            return

        self.selected_mailbox = mailbox
        self.state = self.STATE_SELECTED

        await self.send_untagged(f"{status['exists']} EXISTS")
        await self.send_untagged(f"{status['recent']} RECENT")
        await self.send_untagged(f"OK [UNSEEN {status['unseen']}] Message {status['unseen']} is first unseen")
        await self.send_untagged("FLAGS (\\Answered \\Flagged \\Deleted \\Seen \\Draft)")
        await self.send_untagged("OK [PERMANENTFLAGS (\\Seen \\Deleted)] Limited")

        access = "[READ-ONLY]" if readonly else "[READ-WRITE]"
        await self.send_tagged(tag, IMAP_OK, f"{access} SELECT completed")

    async def _cmd_examine(self, tag: str, args: str):
        await self._cmd_select(tag, args, readonly=True)

    async def _cmd_fetch(self, tag: str, args: str):
        if self.state != self.STATE_SELECTED:
            await self.send_tagged(tag, IMAP_NO, "No mailbox selected")
            return
        await self.bridge.handle_fetch(tag, args, self.selected_mailbox, self)

    async def _cmd_store(self, tag: str, args: str):
        if self.state != self.STATE_SELECTED:
            await self.send_tagged(tag, IMAP_NO, "No mailbox selected")
            return
        await self.bridge.handle_store(tag, args, self.selected_mailbox, self)

    async def _cmd_idle(self, tag: str, args: str):
        """
        IMAP IDLE — RFC 2177.

        Event-driven mode (bridge has event_loop): subscribe to asyncio.Queue,
        push EXISTS/EXPUNGE as events arrive, no polling.

        Polling fallback (no event_loop): poll get_mailbox_status() every
        IDLE_POLL_INTERVAL seconds (legacy behaviour, kept for compatibility).

        Exits when client sends 'DONE' or after IDLE_MAX_DURATION (29 min).
        """
        if self.state != self.STATE_SELECTED:
            await self.send_tagged(tag, IMAP_NO, "No mailbox selected — SELECT first")
            return

        await self.send("+ idling")
        logger.debug(f"IDLE started on {self.selected_mailbox}")

        # Prefer event-driven if bridge exposes subscribe()
        has_event_driven = hasattr(self.bridge, "subscribe") and hasattr(self.bridge, "unsubscribe")

        if has_event_driven:
            await self._idle_event_driven(tag)
        else:
            await self._idle_polling(tag)

        await self.send_tagged(tag, IMAP_OK, "IDLE terminated")

    async def _idle_event_driven(self, tag: str):
        """Event-driven IDLE — waits on asyncio.Queue fed by ProtonEventLoop."""
        queue: asyncio.Queue = asyncio.Queue()
        mailbox = self.selected_mailbox

        # Subscribe to events for this mailbox
        label_id = None
        if hasattr(self.bridge, "mailbox_to_label_id"):
            label_id = self.bridge.mailbox_to_label_id(mailbox)

        if label_id:
            self.bridge.subscribe(label_id, queue)
        else:
            # Unknown label — fall back to polling
            await self._idle_polling(tag)
            return

        logger.debug(f"IDLE event-driven on {mailbox} (label={label_id})")
        exists_count = None

        try:
            deadline = asyncio.get_event_loop().time() + IDLE_MAX_DURATION

            while asyncio.get_event_loop().time() < deadline:
                remaining = deadline - asyncio.get_event_loop().time()

                # Race: client DONE vs. next event vs. timeout
                done_task = asyncio.create_task(self.reader.readline())
                event_task = asyncio.create_task(queue.get())

                done, pending = await asyncio.wait(
                    [done_task, event_task],
                    timeout=min(remaining, 60),
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Cancel pending tasks
                for t in pending:
                    t.cancel()
                    try:
                        await t
                    except (asyncio.CancelledError, Exception):
                        pass

                if not done:
                    continue  # timeout — loop back

                # Check if client sent DONE
                if done_task in done:
                    try:
                        line = done_task.result()
                        if line.decode().strip().upper() == "DONE":
                            break
                    except Exception:
                        break

                # Process event from queue
                if event_task in done:
                    try:
                        event = event_task.result()
                        from src.event_loop import IMAPEvent

                        if event.event_type == "exists":
                            if exists_count is None:
                                status = await self.bridge.get_mailbox_status(mailbox)
                                exists_count = status["exists"] if status else 0
                            exists_count += event.count or 1
                            await self.send_untagged(f"{exists_count} EXISTS")

                        elif event.event_type == "expunge":
                            if exists_count and exists_count > 0:
                                await self.send_untagged(f"{exists_count} EXPUNGE")
                                exists_count -= 1

                        elif event.event_type == "cache_invalid":
                            self.bridge._cache.invalidate(f"status:{mailbox}")

                    except Exception as e:
                        logger.warning(f"IDLE event processing error: {e}")

        except Exception as e:
            logger.error(f"IDLE event-driven error: {e}")
        finally:
            if label_id:
                self.bridge.unsubscribe(label_id, queue)

    async def _idle_polling(self, tag: str):
        """Legacy polling IDLE — fallback when no event_loop available."""
        last_exists = None
        elapsed = 0

        try:
            while elapsed < IDLE_MAX_DURATION:
                try:
                    done_line = await asyncio.wait_for(
                        self.reader.readline(), timeout=IDLE_POLL_INTERVAL
                    )
                    if done_line.decode().strip().upper() == "DONE":
                        break
                except asyncio.TimeoutError:
                    pass

                elapsed += IDLE_POLL_INTERVAL

                try:
                    status = await self.bridge.get_mailbox_status(self.selected_mailbox)
                    if status:
                        current_exists = status["exists"]
                        if last_exists is not None and current_exists != last_exists:
                            await self.send_untagged(f"{current_exists} EXISTS")
                        last_exists = current_exists
                except Exception as e:
                    logger.warning(f"IDLE poll failed: {e}")

        except Exception as e:
            logger.error(f"IDLE polling error: {e}")


class ProtonIMAPServer:
    """Asyncio IMAP server — spawns IMAPSession per connection."""

    def __init__(self, bridge, host: str = "127.0.0.1", port: int = 1143, ssl_context=None):
        self.bridge = bridge
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self):
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port, ssl=self.ssl_context)
        tls_tag = " (TLS)" if self.ssl_context else ""
        logger.info(f"📬 IMAP server started on {self.host}:{self.port}{tls_tag}")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        session = IMAPSession(reader, writer, self.bridge)
        await session.run()

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("📬 IMAP server stopped")
