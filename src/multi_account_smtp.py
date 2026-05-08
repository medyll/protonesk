#!/usr/bin/env python3
"""
Protonesk — Multi-Account SMTP Handler

Routes outgoing mail to the correct Proton account based on the From: header.
"""

import logging
from email import message_from_bytes
from email.policy import default as email_default_policy
from typing import Optional, Dict, Any

from aiosmtpd.smtp import Envelope

logger = logging.getLogger(__name__)


class MultiAccountSMTPHandler:
    """aiosmtpd handler that routes outgoing mail by From: address to the correct account.

    Routing logic:
    - Extract From: header from the message
    - Map the From: address to an account label via SessionManager
    - Use that account's ProtonSend to deliver
    - If address unknown → use default account (first) + warning log
    - If account found but session invalid → 550 error
    """

    def __init__(self, session_manager, send_map: Dict[str, Any]):
        """
        Args:
            session_manager: SessionManager with connected accounts
            send_map: Dict mapping label → ProtonSend instance
        """
        self.session_manager = session_manager
        self.send_map = send_map
        self._default_label: Optional[str] = None
        if session_manager.labels:
            self._default_label = session_manager.labels[0]

    def _resolve_label_from_address(self, from_address: str) -> Optional[str]:
        """Map a From: email address to an account label.

        Matches against the username of each connected account.
        Returns None if no match found.
        """
        if not from_address:
            return None

        # Normalize: strip angle brackets if present
        clean = from_address.strip("<>").strip()

        for label in self.session_manager.labels:
            session_info = self.session_manager.get(label)
            username = session_info.get("username", "")
            if username.lower() == clean.lower():
                return label

        return None

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope: Envelope):
        try:
            msg = message_from_bytes(envelope.content, policy=email_default_policy)

            sender = envelope.mail_from
            recipients = envelope.rcpt_tos
            subject = str(msg.get("Subject", "(no subject)"))

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_content()
                        break
                if not body:
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            body = part.get_content()
                            break
            else:
                body = msg.get_content()

            # Route by From: address
            label = self._resolve_label_from_address(sender)

            if label is None:
                label = self._default_label
                if label:
                    logger.warning(
                        f"From address '{sender}' not mapped to any account — " f"using default account '{label}'"
                    )
                else:
                    logger.error("No accounts available to send mail")
                    return "550 No accounts configured"

            if label not in self.send_map:
                logger.error(f"No ProtonSend instance for label '{label}'")
                return "550 Internal routing error"

            proton_send = self.send_map[label]

            # Check session validity
            try:
                session_info = self.session_manager.get(label)
                if not session_info.get("session"):
                    logger.error(f"Session invalid for account '{label}'")
                    return f"550 Account '{label}' session invalid"
            except Exception:
                logger.error(f"Could not verify session for account '{label}'")
                return f"550 Account '{label}' unavailable"

            logger.info(f"SMTP routing '{subject}' from {sender} via account '{label}' " f"to {recipients}")

            success = proton_send.send_email(
                subject=subject,
                sender=sender,
                recipients=recipients,
                body=body,
            )

            if success:
                logger.info(f"✅ Sent via '{label}': '{subject}'")
                return "250 Message accepted for delivery"
            else:
                logger.error(f"❌ Send failed via '{label}': '{subject}'")
                return "550 Message delivery failed"

        except Exception as e:
            logger.error(f"SMTP handler error: {e}")
            return "550 Internal server error"
