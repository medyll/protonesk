#!/usr/bin/env python3
"""
Proton Mail Bridge — Session Manager

Manages multiple active Proton sessions for multi-account support.
Each account is identified by its label from config.yaml.
"""

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SessionError(Exception):
    """Raised when session operations fail."""

    pass


class SessionManager:
    """Manages a pool of Proton sessions, one per account label."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def connect_all(self, accounts: list[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
        """Connect to all accounts and store their sessions.

        Args:
            accounts: List of account dicts with 'username' and 'label' keys.

        Returns:
            Dict mapping label → session info dict with keys:
            'auth', 'session', 'api_client', 'username'
        """
        from src.auth import ProtonAuth
        from src.api_client import ProtonAPIClient
        from src.secrets import SecretManager

        for account in accounts:
            label = account["label"]
            username = account["username"]
            logger.info(f"Connecting account '{label}' ({username})...")

            try:
                secret_mgr = SecretManager()
                password = secret_mgr.get_secret(f"proton_password_{label}")
                if not password:
                    password = secret_mgr.get_secret("proton_password")

                totp = secret_mgr.get_secret(f"proton_totp_{label}")
                if not totp:
                    totp = secret_mgr.get_secret("proton_totp")

                auth = ProtonAuth(username=username, password=password, totp=totp)
                session = auth.authenticate()
                api_client = ProtonAPIClient(session)

                self._sessions[label] = {
                    "auth": auth,
                    "session": session,
                    "api_client": api_client,
                    "username": username,
                }
                logger.info(f"✅ Account '{label}' connected")

            except Exception as e:
                logger.error(f"❌ Failed to connect account '{label}': {e}")
                raise SessionError(f"Account '{label}' connection failed: {e}")

        return self._sessions

    def get(self, label: str) -> Dict[str, Any]:
        """Get session info for a specific account label.

        Args:
            label: Account label from config.yaml

        Returns:
            Dict with 'auth', 'session', 'api_client', 'username'

        Raises:
            SessionError: If label is not found
        """
        if label not in self._sessions:
            raise SessionError(f"No session found for label '{label}'")
        return self._sessions[label]

    def reconnect(self, label: str, max_attempts: int = 3) -> Dict[str, Any]:
        """Reconnect a specific account without affecting others.

        Args:
            label: Account label to reconnect
            max_attempts: Maximum number of reconnection attempts

        Returns:
            Updated session info dict

        Raises:
            SessionError: If reconnection fails after all attempts
        """
        if label not in self._sessions:
            raise SessionError(f"No session found for label '{label}' to reconnect")

        old_session = self._sessions[label]
        username = old_session["username"]

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Reconnecting account '{label}' (attempt {attempt})...")

                from src.auth import ProtonAuth
                from src.api_client import ProtonAPIClient
                from src.secrets import SecretManager

                secret_mgr = SecretManager()
                password = secret_mgr.get_secret(f"proton_password_{label}")
                if not password:
                    password = secret_mgr.get_secret("proton_password")

                totp = secret_mgr.get_secret(f"proton_totp_{label}")
                if not totp:
                    totp = secret_mgr.get_secret("proton_totp")

                auth = ProtonAuth(username=username, password=password, totp=totp)
                session = auth.authenticate()
                api_client = ProtonAPIClient(session)

                self._sessions[label] = {
                    "auth": auth,
                    "session": session,
                    "api_client": api_client,
                    "username": username,
                }
                logger.info(f"✅ Account '{label}' reconnected")
                return self._sessions[label]

            except Exception as e:
                logger.warning(f"Reconnect attempt {attempt} failed for '{label}': {e}")
                if attempt < max_attempts:
                    delay = 5 * (2 ** (attempt - 1))
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)

        raise SessionError(f"Failed to reconnect account '{label}' after {max_attempts} attempts")

    def logout_all(self):
        """Logout all accounts and clear session pool."""
        for label, session_info in list(self._sessions.items()):
            try:
                session_info["auth"].logout()
                logger.info(f"Logged out account '{label}'")
            except Exception as e:
                logger.warning(f"Error logging out '{label}': {e}")
        self._sessions.clear()
        logger.info("All sessions cleared")

    @property
    def labels(self) -> list[str]:
        """Return list of connected account labels."""
        return list(self._sessions.keys())

    @property
    def is_multi_account(self) -> bool:
        """Return True if more than one account is connected."""
        return len(self._sessions) > 1
