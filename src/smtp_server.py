#!/usr/bin/env python3
"""
Proton Mail Bridge — SMTP Server

Local SMTP server on 127.0.0.1:1025.
Receives outgoing mail from any client, encrypts, sends via Proton API.
"""

import logging
from email import message_from_bytes
from email.policy import default as email_default_policy
from typing import Optional

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope

logger = logging.getLogger(__name__)


class ProtonSMTPHandler:
    """
    aiosmtpd handler — intercepts outgoing messages and routes to ProtonSend.

    Each received message goes through:
    1. Parse RFC 822 → extract From/To/Subject/Body
    2. ProtonSend.send_email() with PGP encryption
    3. Return 250 OK or 550 on failure
    """

    def __init__(self, proton_send):
        self.proton_send = proton_send

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope: Envelope):
        try:
            msg = message_from_bytes(envelope.content, policy=email_default_policy)

            sender = envelope.mail_from
            recipients = envelope.rcpt_tos
            subject = str(msg.get("Subject", "(no subject)"))

            # Extract body (prefer plain text)
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

            logger.info(f"SMTP received: '{subject}' from {sender} to {recipients}")

            success = self.proton_send.send_email(
                subject=subject,
                sender=sender,
                recipients=recipients,
                body=body,
            )

            if success:
                logger.info(f"SMTP relayed via Proton: '{subject}'")
                return "250 Message accepted for delivery"
            else:
                logger.error(f"SMTP relay failed: '{subject}'")
                return "550 Message delivery failed"

        except Exception as e:
            logger.error(f"SMTP handler error: {e}")
            return "550 Internal server error"


class ProtonSMTPServer:
    """Local SMTP server bridging any client to Proton Mail."""

    def __init__(self, proton_send, host: str = "127.0.0.1", port: int = 1025, ssl_context=None):
        self.proton_send = proton_send
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self._controller: Optional[Controller] = None

    def start(self):
        handler = ProtonSMTPHandler(self.proton_send)
        kwargs = {"hostname": self.host, "port": self.port}
        if self.ssl_context:
            kwargs["ssl_context"] = self.ssl_context
        self._controller = Controller(handler, **kwargs)
        self._controller.start()
        tls_tag = " (TLS)" if self.ssl_context else ""
        logger.info(f"📤 SMTP server started on {self.host}:{self.port}{tls_tag}")

    def stop(self):
        if self._controller:
            self._controller.stop()
            logger.info("📤 SMTP server stopped")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from src.auth import ProtonAuth
    from src.crypto import ProtonCrypto  # noqa: F401
    from src.send import ProtonSend  # noqa: F401

    logging.basicConfig(level=logging.INFO)

    auth = ProtonAuth()
    session = auth.authenticate()

    # ProtonCrypto requires key path — set via secrets
    # crypto = ProtonCrypto(key_path, passphrase)
    # proton_send = ProtonSend(session, crypto)
    # server = ProtonSMTPServer(proton_send)
    # server.start()
    # print("SMTP bridge running on 127.0.0.1:1025 — Ctrl+C to stop")
    # try:
    #     asyncio.get_event_loop().run_forever()
    # except KeyboardInterrupt:
    #     server.stop()
    #     auth.logout()
