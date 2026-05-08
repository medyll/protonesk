#!/usr/bin/env python3
"""
Proton Mail Auth Engine — SRP Authentication

Handles Secure Remote Password (SRP) handshake with Proton API.
Never transmits cleartext passwords.

SECURITY: Uses src/secrets.py OS keyring (AI cannot access)
"""

from proton.session import ProtonSession
from src.secrets import get_credentials


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

        Returns:
            ProtonSession: Authenticated session

        Raises:
            ValueError: If authentication fails
        """
        print(f"🔐 Authenticating as {self.username}...")

        try:
            self.session = ProtonSession()
            self.session.login(self.username, self.password, self.totp_secret)

            print("✅ Authentication successful")
            return self.session

        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            raise ValueError(f"SRP authentication failed: {e}")

    def is_authenticated(self):
        """Check if session is valid."""
        return (
            self.session is not None and hasattr(self.session, "is_authenticated") and self.session.is_authenticated()
        )

    def logout(self):
        """Clear session."""
        if self.session:
            try:
                self.session.logout()
            except Exception:
                pass
            self.session = None
            print("🚪 Logged out")


# CLI usage
if __name__ == "__main__":
    auth = ProtonAuth()
    session = auth.authenticate()
    print(f"Session: {session}")
    auth.logout()
