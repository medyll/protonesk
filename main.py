#!/usr/bin/env python3
"""
Proton Mail Bridge — Daemon Entry Point

Starts local IMAP (port 1143) and SMTP (port 1025) servers.
Any email client or AI agent can connect as if to a standard mail server.

Supports single-account (legacy) and multi-account mode via config.yaml.

Usage:
    python main.py
    python main.py --imap-port 1143 --smtp-port 1025
    python main.py --imap-only
    python main.py --smtp-only
"""

import asyncio
import argparse
import logging
import signal
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Top-level imports for testability (patch targets must exist at module scope)
from src.auth import ProtonAuth  # noqa: E402
from src.config import load_config  # noqa: E402
from src.api_client import ProtonAPIClient  # noqa: E402
from src.imap_bridge import ProtonIMAPBridge  # noqa: E402
from src.imap_server import ProtonIMAPServer  # noqa: E402
from src.smtp_server import ProtonSMTPServer  # noqa: E402
from src.send import ProtonSend  # noqa: E402
from src.secrets import get_credentials  # noqa: E402

MAX_RECONNECT_ATTEMPTS = 3
RECONNECT_DELAY = 5  # seconds


def parse_args():
    parser = argparse.ArgumentParser(description="Proton Mail Bridge")
    parser.add_argument("--imap-port", type=int, default=1143)
    parser.add_argument("--smtp-port", type=int, default=1025)
    parser.add_argument("--imap-host", default="127.0.0.1")
    parser.add_argument("--smtp-host", default="127.0.0.1")
    parser.add_argument("--imap-only", action="store_true")
    parser.add_argument("--smtp-only", action="store_true")
    parser.add_argument("--local-password", default=None)
    parser.add_argument("--tls", action="store_true", default=None, help="Enable TLS (auto-generates self-signed cert)")
    parser.add_argument("--log-level", default=None, choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--tray", action="store_true", help="Show system tray icon (requires pystray)")
    return parser.parse_args()


def connect_proton(attempt: int = 0):
    """Authenticate with Proton, retry on failure."""
    for i in range(MAX_RECONNECT_ATTEMPTS):
        try:
            logger.info(f"🔐 Authenticating with Proton... (attempt {i + 1})")
            auth = ProtonAuth()
            session = auth.authenticate()
            client = ProtonAPIClient(session)
            logger.info("✅ Connected to Proton")
            return auth, session, client
        except Exception as e:
            logger.error(f"❌ Auth failed: {e}")
            if i < MAX_RECONNECT_ATTEMPTS - 1:
                logger.info(f"Retrying in {RECONNECT_DELAY * (2 ** i)}s...")
                time.sleep(RECONNECT_DELAY * (2**i))

    logger.critical("Could not authenticate with Proton after retries. Exiting.")
    sys.exit(1)


def _is_session_expired_error(e: Exception) -> bool:
    """Detect if an exception indicates an expired/invalid session (HTTP 401)."""
    msg = str(e).lower()
    return "401" in msg or "unauthorized" in msg or "expired" in msg


async def run(args):
    cfg = load_config(args)
    accounts = cfg.get("accounts")

    ssl_context = None
    if cfg.get("tls"):
        from src.tls import get_ssl_context

        ssl_context = get_ssl_context()

    local_password = cfg.get("local_password", "bridge")

    # Crypto is optional — bridge works without PGP key
    crypto = None
    try:
        creds = get_credentials()
        key_path = creds.get("key_path")
        key_passphrase = creds.get("key_passphrase")
        if key_path and key_passphrase:
            from src.crypto import ProtonCrypto

            crypto = ProtonCrypto(key_path, key_passphrase)
            logger.info("🔑 PGP decryption enabled")
        else:
            logger.warning("⚠️  No PGP key configured — messages will show as encrypted")
    except Exception:
        logger.warning("⚠️  Could not load PGP key — messages will show as encrypted")

    # Multi-account mode
    if accounts:
        from src.session_manager import SessionManager, SessionError
        from src.multi_account_bridge import MultiAccountBridge
        from src.multi_account_smtp import MultiAccountSMTPHandler

        logger.info(f"Multi-account mode: {len(accounts)} account(s)")
        manager = SessionManager()
        manager.connect_all(accounts)

        crypto_map = {}
        if crypto:
            for label in manager.labels:
                crypto_map[label] = crypto

        bridge = MultiAccountBridge(manager, crypto_map, local_password=local_password)

        imap_port = cfg.get("imap_port", 1143)
        smtp_port = cfg.get("smtp_port", 1025)
        imap_host = cfg.get("imap_host", "127.0.0.1")
        smtp_host = cfg.get("smtp_host", "127.0.0.1")

        if not args.smtp_only:
            imap_server = ProtonIMAPServer(bridge, host=imap_host, port=imap_port, ssl_context=ssl_context)
            await imap_server.start()
            logger.info(f"📬 IMAP server ready on {imap_host}:{imap_port}")

        if not args.imap_only:
            send_map = {}
            for label in manager.labels:
                session_info = manager.get(label)
                if crypto:
                    send_map[label] = ProtonSend(session_info["session"], crypto)

            if send_map:
                handler = MultiAccountSMTPHandler(manager, send_map)
                kwargs = {"hostname": smtp_host, "port": smtp_port}
                if ssl_context:
                    kwargs["ssl_context"] = ssl_context
                from aiosmtpd.controller import Controller

                smtp_controller = Controller(handler, **kwargs)
                smtp_controller.start()
                logger.info(f"📤 SMTP server ready on {smtp_host}:{smtp_port}")

        print()
        print(f"🚀 Proton Bridge ready ({len(accounts)} accounts). Press Ctrl+C to stop.")
        print(f"   IMAP: {imap_host}:{imap_port}  (password: {local_password})")
        print(f"   SMTP: {smtp_host}:{smtp_port}")
        print(f"   Accounts: {', '.join(manager.labels)}")
        print()

        stop_event = asyncio.Event()

        def _shutdown(sig, frame):
            logger.info("Shutting down...")
            stop_event.set()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        # Background reconnection monitor
        async def _reconnect_monitor():
            """Watch for session expiration and reconnect affected accounts."""
            while not stop_event.is_set():
                for label in manager.labels:
                    try:
                        session_info = manager.get(label)
                        sess = session_info.get("session")
                        if sess and hasattr(sess, "is_authenticated"):
                            if not sess.is_authenticated():
                                logger.warning(f"Session expired for '{label}', reconnecting...")
                                try:
                                    manager.reconnect(label)
                                    logger.info(f"✅ Reconnected '{label}'")
                                except SessionError as e:
                                    logger.error(f"❌ Reconnect failed for '{label}': {e}")
                    except Exception as e:
                        if _is_session_expired_error(e):
                            logger.warning(f"Session error for '{label}', reconnecting...")
                            try:
                                manager.reconnect(label)
                            except SessionError as re:
                                logger.error(f"❌ Reconnect failed for '{label}': {re}")
                await asyncio.sleep(30)

        reconnect_task = asyncio.create_task(_reconnect_monitor())

        await stop_event.wait()
        reconnect_task.cancel()

        if not args.smtp_only and "imap_server" in dir():
            await imap_server.stop()
        if not args.imap_only and "smtp_controller" in dir():
            smtp_controller.stop()

        manager.logout_all()
        logger.info("Bridge stopped.")

    else:
        # Single-account mode (legacy)
        auth, session, api_client = connect_proton()

        imap_port = cfg.get("imap_port", 1143)
        smtp_port = cfg.get("smtp_port", 1025)
        imap_host = cfg.get("imap_host", "127.0.0.1")
        smtp_host = cfg.get("smtp_host", "127.0.0.1")

        bridge = ProtonIMAPBridge(api_client, crypto, local_password=local_password)

        if not args.smtp_only:
            imap_server = ProtonIMAPServer(bridge, host=imap_host, port=imap_port, ssl_context=ssl_context)
            await imap_server.start()
            logger.info(f"📬 IMAP server ready on {imap_host}:{imap_port}")

        if not args.imap_only:
            if crypto:
                proton_send = ProtonSend(session, crypto)
            else:
                logger.warning("⚠️  SMTP send requires PGP key — outgoing mail disabled")
                proton_send = None

            if proton_send:
                smtp_server = ProtonSMTPServer(proton_send, host=smtp_host, port=smtp_port, ssl_context=ssl_context)
                smtp_server.start()
                logger.info(f"📤 SMTP server ready on {smtp_host}:{smtp_port}")

        print()
        print("🚀 Proton Bridge ready. Press Ctrl+C to stop.")
        print(f"   IMAP: {args.imap_host}:{args.imap_port}  (password: {args.local_password})")
        print(f"   SMTP: {args.smtp_host}:{args.smtp_port}")
        print()

        stop_event = asyncio.Event()

        def _shutdown(sig, frame):
            logger.info("Shutting down...")
            stop_event.set()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        await stop_event.wait()

        if not args.smtp_only and "imap_server" in dir():
            await imap_server.stop()
        if not args.imap_only and proton_send and "smtp_server" in dir():
            smtp_server.stop()

        auth.logout()
        logger.info("Bridge stopped.")


def main():
    args = parse_args()
    cfg = load_config(args)
    # Apply log level from config
    logging.getLogger().setLevel(cfg.get("log_level", "INFO"))

    if args.tray:
        try:
            from src.tray import TrayIcon, HAS_PYSTRAY

            if not HAS_PYSTRAY:
                logger.warning("pystray not installed — starting headless. Install: pip install pystray pillow")
                asyncio.run(run(args))
                return

            def _bridge_runner():
                asyncio.run(run(args))

            tray = TrayIcon(bridge_runner=_bridge_runner)
            # Auto-start bridge when tray launches
            tray._start_bridge()
            tray.run()
        except ImportError:
            logger.warning("Tray dependencies missing — starting headless")
            asyncio.run(run(args))
    else:
        asyncio.run(run(args))


if __name__ == "__main__":
    main()
