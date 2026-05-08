#!/usr/bin/env python3
"""
Protonesk — IMAP Bridge

Glue layer between IMAP server and Proton API.
Handles: auth, mailbox listing, message mapping, fetch+decrypt, store flags.
"""

import asyncio
import hmac
import time
import logging
from email.utils import formatdate
from typing import Optional, Dict, List, Any, Set

logger = logging.getLogger(__name__)

# Proton label ID → IMAP mailbox name
LABEL_MAP = {
    "0": "INBOX",
    "1": "All Mail",
    "2": "Trash",
    "3": "Spam",
    "4": "Archive",
    "5": "Sent",
    "6": "Drafts",
}

# IMAP name → Proton label ID (reverse)
IMAP_TO_LABEL = {v: k for k, v in LABEL_MAP.items()}

CACHE_TTL = 60  # seconds


class _Cache:
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._ts: Dict[str, float] = {}

    def get(self, key: str):
        if key in self._data and (time.time() - self._ts[key]) < CACHE_TTL:
            return self._data[key]
        return None

    def set(self, key: str, value):
        self._data[key] = value
        self._ts[key] = time.time()

    def invalidate(self, key: str):
        self._data.pop(key, None)
        self._ts.pop(key, None)


class ProtonIMAPBridge:
    """
    Bridge between IMAPSession commands and Proton API.

    IMAPServer calls these methods; bridge calls ProtonAPIClient + ProtonCrypto.
    """

    def __init__(self, api_client, crypto, local_password: str):
        """
        Args:
            api_client: ProtonAPIClient instance (authenticated)
            crypto: ProtonCrypto instance (for decrypt)
            local_password: password clients use to connect to local IMAP
        """
        self.api = api_client
        self.crypto = crypto
        self.local_password = local_password
        self._cache = _Cache()
        self._seq_map: Dict[str, List[str]] = {}  # mailbox → [proton_msg_id, ...]
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}  # label_id → queues

    # ── Auth ──────────────────────────────────────────────────────────────────

    def authenticate(self, username: str, password: str) -> bool:
        """Validate local IMAP credentials (not Proton credentials)."""
        return hmac.compare_digest(password, self.local_password)

    # ── Event subscription (IDLE event-driven) ────────────────────────────────

    def subscribe(self, label_id: str, queue: asyncio.Queue):
        """Register queue for IMAP events on label_id (used by IDLE sessions)."""
        if label_id not in self._subscribers:
            self._subscribers[label_id] = set()
        self._subscribers[label_id].add(queue)

    def unsubscribe(self, label_id: str, queue: asyncio.Queue):
        """Remove queue from label_id subscribers."""
        if label_id in self._subscribers:
            self._subscribers[label_id].discard(queue)
            if not self._subscribers[label_id]:
                del self._subscribers[label_id]

    def mailbox_to_label_id(self, mailbox: str) -> Optional[str]:
        """Convert IMAP mailbox name to Proton label ID."""
        return IMAP_TO_LABEL.get(mailbox)

    # ── Mailboxes ─────────────────────────────────────────────────────────────

    async def get_mailboxes(self) -> List[str]:
        """Return list of IMAP mailbox names mapped from Proton labels."""
        cached = self._cache.get("mailboxes")
        if cached:
            return cached

        try:
            labels = self.api.get_labels()
            mailboxes = []
            for label in labels:
                label_id = str(label.get("ID", ""))
                name = LABEL_MAP.get(label_id) or label.get("Name", "")
                if name:
                    mailboxes.append(name)
            if not mailboxes:
                mailboxes = list(LABEL_MAP.values())
        except Exception as e:
            logger.warning(f"Failed to fetch labels, using defaults: {e}")
            mailboxes = list(LABEL_MAP.values())

        self._cache.set("mailboxes", mailboxes)
        return mailboxes

    async def get_mailbox_status(self, mailbox: str) -> Optional[Dict]:
        """Return EXISTS/RECENT/UNSEEN counts for a mailbox."""
        cache_key = f"status:{mailbox}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        label_id = IMAP_TO_LABEL.get(mailbox)
        if label_id is None:
            return None

        try:
            messages = self.api.get_messages(label=label_id, limit=100)
            self._build_seq_map(mailbox, messages)

            exists = len(messages)
            unseen = sum(1 for m in messages if m.get("Unread", 0))
            status = {"exists": exists, "recent": 0, "unseen": unseen}
            self._cache.set(cache_key, status)
            return status
        except Exception as e:
            logger.error(f"get_mailbox_status failed for {mailbox}: {e}")
            return None

    # ── Message mapping ───────────────────────────────────────────────────────

    def _build_seq_map(self, mailbox: str, messages: List[Dict]):
        """Map IMAP sequence numbers (1-based) to Proton message IDs."""
        self._seq_map[mailbox] = [m["ID"] for m in messages if "ID" in m]

    def seq_to_proton_id(self, mailbox: str, seq: int) -> Optional[str]:
        """Convert IMAP sequence number to Proton message ID."""
        ids = self._seq_map.get(mailbox, [])
        if 1 <= seq <= len(ids):
            return ids[seq - 1]
        return None

    def proton_flags(self, message: Dict) -> str:
        """Convert Proton message state to IMAP flags string."""
        flags = []
        if not message.get("Unread", 0):
            flags.append("\\Seen")
        return " ".join(flags)

    # ── Fetch ─────────────────────────────────────────────────────────────────

    async def fetch_message_rfc822(self, proton_msg_id: str) -> str:
        """
        Fetch + decrypt Proton message, return as RFC 822 string.
        Decrypted content never written to disk.
        """
        cache_key = f"msg:{proton_msg_id}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        message = self.api.get_message(proton_msg_id)

        sender = message.get("Sender", {}).get("Address", "unknown@proton.me")
        to_list = message.get("ToList", [{}])
        recipient = to_list[0].get("Address", "") if to_list else ""
        subject = message.get("Subject", "(no subject)")
        timestamp = message.get("Time", 0)
        date_str = formatdate(timestamp, localtime=False)

        try:
            body = self.crypto.decrypt_message_body(message)
        except Exception as e:
            logger.warning(f"Decrypt failed for {proton_msg_id}: {e}")
            body = "[Encrypted message — decryption failed]"

        rfc822 = (
            f"From: {sender}\r\n"
            f"To: {recipient}\r\n"
            f"Subject: {subject}\r\n"
            f"Date: {date_str}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"\r\n"
            f"{body}"
        )

        self._cache.set(cache_key, rfc822)
        return rfc822

    async def handle_fetch(self, tag: str, args: str, mailbox: str, session):
        """Handle IMAP FETCH command — routes to correct fetch type."""
        parts = args.split(" ", 1)
        if len(parts) < 2:
            await session.send_tagged(tag, "BAD", "FETCH requires sequence and data items")
            return

        seq_str = parts[0]
        _ = parts[1].upper()  # items arg reserved for future FETCH data item parsing

        try:
            seq = int(seq_str)
        except ValueError:
            await session.send_tagged(tag, "BAD", "Invalid sequence number")
            return

        proton_id = self.seq_to_proton_id(mailbox, seq)
        if not proton_id:
            await session.send_tagged(tag, "NO", f"Message {seq} not found")
            return

        try:
            rfc822 = await self.fetch_message_rfc822(proton_id)
            size = len(rfc822.encode())
            await session.send_untagged(f"{seq} FETCH (RFC822 {{{size}}}")
            await session.send(rfc822)
            await session.send(")")
            await session.send_tagged(tag, "OK", "FETCH completed")
        except Exception as e:
            logger.error(f"FETCH error: {e}")
            await session.send_tagged(tag, "NO", "FETCH failed")

    # ── Store ─────────────────────────────────────────────────────────────────

    async def handle_store(self, tag: str, args: str, mailbox: str, session):
        """Handle IMAP STORE — update flags (\\Seen etc.)."""
        parts = args.split(" ", 2)
        if len(parts) < 3:
            await session.send_tagged(tag, "BAD", "STORE requires seq, flag action, flags")
            return

        seq_str, action, flags_str = parts
        try:
            seq = int(seq_str)
        except ValueError:
            await session.send_tagged(tag, "BAD", "Invalid sequence number")
            return

        proton_id = self.seq_to_proton_id(mailbox, seq)
        if not proton_id:
            await session.send_tagged(tag, "NO", f"Message {seq} not found")
            return

        await session.send_untagged(f"{seq} FETCH (FLAGS ({flags_str}))")
        await session.send_tagged(tag, "OK", "STORE completed")
        self._cache.invalidate(f"status:{mailbox}")
