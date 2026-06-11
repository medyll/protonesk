#!/usr/bin/env python3
"""
Proton Mail Auth Engine — SRP Authentication

Handles Secure Remote Password (SRP) handshake with Proton API via
proton.api.Session (proton-python-client). Never transmits cleartext passwords.

SECURITY: Uses src/secrets.py OS keyring (AI cannot access)
"""

import json
import os
from pathlib import Path

import pyotp
from proton.api import Session as ProtonSession
from proton.exceptions import ProtonAPIError
from src.secrets import get_credentials

API_URL = "https://mail.proton.me/api"

# Session.__init__ requires writable log/cache dirs.
_STATE_DIR = Path(os.environ.get("PROTONESK_STATE_DIR", Path.home() / ".protonesk"))
LOG_DIR = _STATE_DIR / "logs"
CACHE_DIR = _STATE_DIR / "cache"
SESSION_FILE = _STATE_DIR / "session.json"


def build_session():
    """Construct a fresh, unauthenticated ProtonSession."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    session = ProtonSession(
        api_url=API_URL,
        log_dir_path=str(LOG_DIR),
        cache_dir_path=str(CACHE_DIR),
        # Proton's API rejects unrecognized appversion strings ("Invalid app version").
        # "Other" is the proton-client default and is accepted by the API.
        appversion="Other",
        user_agent="Protonesk",
        # proton-client 0.7.1's TLS-pinning pool is incompatible with urllib3 2.x
        # (positional arg shift makes `strict=False` land in `timeout`, raising
        # "Timeout cannot be a boolean value"). Standard cert validation still applies.
        tls_pinning=False,
    )
    session.enable_alternative_routing = False
    return session


def save_session(session):
    """Persist session tokens so subsequent runs can resume without SRP/CAPTCHA."""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(session.dump()))


def load_session():
    """Load a previously saved session, or None if unavailable/invalid."""
    if not SESSION_FILE.exists():
        return None
    try:
        dump = json.loads(SESSION_FILE.read_text())
        return ProtonSession.load(
            dump,
            log_dir_path=str(LOG_DIR),
            cache_dir_path=str(CACHE_DIR),
            tls_pinning=False,
        )
    except Exception:
        return None


def clear_session():
    """Remove any saved session (e.g. on logout)."""
    try:
        SESSION_FILE.unlink()
    except FileNotFoundError:
        pass


class ProtonAuth:
    """SRP Authentication with Proton Mail."""

    def __init__(self, username=None, password=None, totp=None):
        """
        Initialize ProtonAuth.

        Args:
            username: Proton username (if None, fetch from secrets manager)
            password: Proton password (if None, fetch from secrets manager)
            totp: TOTP 2FA secret (optional)

        Security:
        - If username/password not provided, fetches from workspace/secrets/manager.py
        - AI/OpenClaw CANNOT access these values
        """
        if not username or not password:
            try:
                creds = get_credentials()
                self.username = creds["username"]
                self.password = creds["password"]
                self.totp_secret = creds.get("totp")
            except SystemExit:
                self.username = username
                self.password = password
                self.totp_secret = totp
        else:
            self.username = username
            self.password = password
            self.totp_secret = totp

        self.session = None

        if not self.username or not self.password:
            raise ValueError(
                "Credentials not found. Run setup first:\n"
                "   python src/secrets.py setup\n\n"
                "This stores credentials in OS keyring (AI cannot access)"
            )

    def authenticate(self):
        """
        Perform SRP handshake and return authenticated session.

        Resumes a previously saved session when possible, avoiding repeated
        SRP/CAPTCHA challenges on every restart.

        Returns:
            ProtonSession: Authenticated session

        Raises:
            ValueError: If authentication fails
        """
        # Try to resume a saved session first.
        session = load_session()
        if session is not None and session.UID is not None:
            try:
                session.api_request("/users")
                self.session = session
                print("✅ Resumed existing session")
                return self.session
            except Exception:
                try:
                    session.refresh()
                    session.api_request("/users")
                    self.session = session
                    save_session(session)
                    print("✅ Session refreshed")
                    return self.session
                except Exception:
                    pass  # Fall through to a full SRP login.

        print(f"🔐 Authenticating as {self.username}...")

        try:
            session = build_session()

            session.authenticate(self.username, self.password)

            if self.totp_secret:
                code = pyotp.TOTP(self.totp_secret).now()
                session.provide_2fa(code)

            self.session = session
            save_session(session)

            print("✅ Authentication successful")
            return self.session

        except ProtonAPIError as e:
            if e.code == 9001:
                msg = (
                    "Human verification (CAPTCHA) required by Proton. Run:\n"
                    "   python scripts/solve_captcha.py\n"
                    "then retry."
                )
                print(f"❌ Authentication failed: {msg}")
                raise ValueError(f"SRP authentication failed: {msg}")
            print(f"❌ Authentication failed: {e}")
            raise ValueError(f"SRP authentication failed: {e}")

        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            raise ValueError(f"SRP authentication failed: {e}")

    def is_authenticated(self):
        """Check if session is valid."""
        return self.session is not None and self.session.UID is not None

    def logout(self):
        """Clear session."""
        if self.session:
            try:
                self.session.logout()
            except ProtonAPIError:
                pass
            except Exception:
                pass
            self.session = None
            clear_session()
            print("🚪 Logged out")


# CLI usage
if __name__ == "__main__":
    auth = ProtonAuth()
    session = auth.authenticate()
    print(f"Session: {session}")
    auth.logout()
