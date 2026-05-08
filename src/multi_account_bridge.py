#!/usr/bin/env python3
"""
Protonesk — Multi-Account IMAP Bridge

Wraps per-account ProtonIMAPBridge instances with label-based namespace routing.
Mailbox names are prefixed: "perso/INBOX", "pro/Sent", etc.
"""

import hmac
import logging
from typing import Optional, Dict, List, Any

from src.imap_bridge import ProtonIMAPBridge

logger = logging.getLogger(__name__)


class MailboxParser:
    """Parse prefixed IMAP mailbox names into label + mailbox components."""

    @staticmethod
    def parse(mailbox: str) -> tuple[str, str]:
        """Parse 'label/mailbox' or return ('', mailbox) for backward compat.

        Returns:
            (label, mailbox_name) tuple.
            If no prefix found, label is empty string (single-account mode).
        """
        if "/" in mailbox:
            parts = mailbox.split("/", 1)
            return parts[0], parts[1]
        return "", mailbox

    @staticmethod
    def build(label: str, mailbox: str) -> str:
        """Build prefixed mailbox name. If label is empty, returns mailbox as-is."""
        if label:
            return f"{label}/{mailbox}"
        return mailbox


class MultiAccountBridge:
    """IMAP bridge supporting multiple Proton accounts via label-prefixed namespaces.

    Each account gets its own ProtonIMAPBridge instance.
    Mailbox names are prefixed with the account label.
    """

    def __init__(self, session_manager, crypto_map: Optional[Dict[str, Any]] = None, local_password: str = "bridge"):
        """
        Args:
            session_manager: SessionManager instance with connected accounts
            crypto_map: Optional dict mapping label → ProtonCrypto instance
            local_password: password IMAP clients use to connect
        """
        self.session_manager = session_manager
        self.crypto_map = crypto_map or {}
        self.local_password = local_password
        self._bridges: Dict[str, ProtonIMAPBridge] = {}
        self._parser = MailboxParser()

        # Build per-account bridges
        for label in session_manager.labels:
            session_info = session_manager.get(label)
            api_client = session_info["api_client"]
            crypto = self.crypto_map.get(label)
            self._bridges[label] = ProtonIMAPBridge(api_client, crypto, local_password=local_password)

    def _resolve_bridge(self, mailbox: str) -> tuple[ProtonIMAPBridge, str, str]:
        """Resolve mailbox to (bridge, label, unprefixed_mailbox).

        For backward compat: if single account and no prefix, uses that account.
        """
        label, unprefixed = self._parser.parse(mailbox)

        if label:
            if label not in self._bridges:
                raise KeyError(f"Unknown account label: '{label}'")
            return self._bridges[label], label, unprefixed

        # No label prefix — backward compat mode
        if len(self._bridges) == 1:
            label = list(self._bridges.keys())[0]
            return self._bridges[label], label, unprefixed

        raise KeyError(f"Mailbox '{mailbox}' has no label prefix. " f"Available: {', '.join(self._bridges.keys())}")

    # ── Auth ──────────────────────────────────────────────────────────────────

    def authenticate(self, username: str, password: str) -> bool:
        """Validate local IMAP credentials."""
        return hmac.compare_digest(password, self.local_password)

    # ── Event subscription (IDLE event-driven) ────────────────────────────────

    def subscribe(self, mailbox: str, queue):
        """Subscribe queue to events for prefixed mailbox (e.g. 'perso/INBOX')."""
        try:
            bridge, account_label, unprefixed = self._resolve_bridge(mailbox)
            label_id = bridge.mailbox_to_label_id(unprefixed)
            if label_id:
                bridge.subscribe(label_id, queue)
        except KeyError:
            pass

    def unsubscribe(self, mailbox: str, queue):
        """Unsubscribe queue from prefixed mailbox events."""
        try:
            bridge, account_label, unprefixed = self._resolve_bridge(mailbox)
            label_id = bridge.mailbox_to_label_id(unprefixed)
            if label_id:
                bridge.unsubscribe(label_id, queue)
        except KeyError:
            pass

    def mailbox_to_label_id(self, mailbox: str):
        """Resolve prefixed mailbox to label_id (for single-account compat)."""
        try:
            bridge, _, unprefixed = self._resolve_bridge(mailbox)
            return bridge.mailbox_to_label_id(unprefixed)
        except KeyError:
            return None

    # ── Mailboxes ─────────────────────────────────────────────────────────────

    async def get_mailboxes(self) -> List[str]:
        """Return all mailboxes from all accounts, prefixed with labels."""
        all_mailboxes = []
        for label, bridge in self._bridges.items():
            mailboxes = await bridge.get_mailboxes()
            for mb in mailboxes:
                all_mailboxes.append(self._parser.build(label, mb))
        return all_mailboxes

    async def get_mailbox_status(self, mailbox: str) -> Optional[Dict]:
        """Return status for a specific prefixed mailbox."""
        bridge, label, unprefixed = self._resolve_bridge(mailbox)
        return await bridge.get_mailbox_status(unprefixed)

    # ── Fetch ─────────────────────────────────────────────────────────────────

    async def fetch_message_rfc822(self, proton_msg_id: str, label: str) -> str:
        """Fetch + decrypt message from specific account."""
        if label not in self._bridges:
            raise KeyError(f"Unknown account label: '{label}'")
        return await self._bridges[label].fetch_message_rfc822(proton_msg_id)

    async def handle_fetch(self, tag: str, args: str, mailbox: str, session):
        """Handle IMAP FETCH with label-aware routing."""
        try:
            bridge, label, unprefixed = self._resolve_bridge(mailbox)
        except KeyError as e:
            await session.send_tagged(tag, "NO", str(e))
            return
        await bridge.handle_fetch(tag, args, unprefixed, session)

    # ── Store ─────────────────────────────────────────────────────────────────

    async def handle_store(self, tag: str, args: str, mailbox: str, session):
        """Handle IMAP STORE with label-aware routing."""
        try:
            bridge, label, unprefixed = self._resolve_bridge(mailbox)
        except KeyError as e:
            await session.send_tagged(tag, "NO", str(e))
            return
        await bridge.handle_store(tag, args, unprefixed, session)
