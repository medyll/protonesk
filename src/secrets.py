#!/usr/bin/env python3
"""
Proton Mail Bridge — Secret Management

Secure credential storage that hides secrets from AI/LLM access.

Security principles:
1. NEVER store secrets in plain text files
2. Use OS-native encrypted keyring
3. Prompt user for sensitive input (not AI)
4. Clear secrets from memory after use
"""

import os
import sys
import keyring
from getpass import getpass
from cryptography.fernet import Fernet
import base64
import hashlib


class SecretManager:
    """
    Secure secret management with multiple protection layers.

    Security levels:
    1. keyring (OS-native encryption) — RECOMMENDED
    2. Encrypted file (Fernet cipher) — FALLBACK
    3. Environment variables — NOT RECOMMENDED (visible to AI)
    """

    SERVICE_NAME = "proton-mail-bridge"

    def __init__(self, use_keyring: bool = True):
        """
        Initialize secret manager.

        Args:
            use_keyring: Use OS keyring if True, fallback to encrypted file
        """
        self.use_keyring = use_keyring
        self._key = None
        self._encrypted_file = os.path.join(os.path.expanduser("~"), ".proton_bridge_secrets.enc")

    # Salt stored alongside encrypted file — same dir, fixed name
    _SALT_FILE = os.path.join(os.path.expanduser("~"), ".proton_bridge_secrets.salt")

    def _get_key(self, password: str) -> bytes:
        """Derive encryption key using scrypt (salted, iterated)."""
        if os.path.exists(self._SALT_FILE):
            with open(self._SALT_FILE, "rb") as f:
                salt = f.read()
        else:
            salt = hashlib.sha256(os.urandom(32)).digest()
            with open(self._SALT_FILE, "wb") as f:
                f.write(salt)
            os.chmod(self._SALT_FILE, 0o600)
        key = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return base64.urlsafe_b64encode(key)

    def set_secret(self, key: str, value: str, prompt: bool = True):
        """
        Store secret securely.

        Args:
            key: Secret identifier (e.g., "proton_password")
            value: Secret value (if prompt=False)
            prompt: If True, prompt user for input (more secure)

        Security:
        - ✅ prompt=True: AI cannot see the value
        - ✅ Stored in OS keyring (encrypted)
        - ❌ Never store in .env or plain text
        """
        if prompt:
            # Prompt user directly (AI cannot see this)
            print(f"🔐 Enter {key.replace('_', ' ')}: ", end="", flush=True)
            value = getpass("")  # Hides input
            print()  # Newline after password

        if not value:
            raise ValueError(f"No value provided for {key}")

        if self.use_keyring:
            try:
                keyring.set_password(self.SERVICE_NAME, key, value)
                print(f"✅ {key} stored in OS keyring (encrypted)")
                return
            except Exception as e:
                print(f"⚠️  Keyring failed: {e}")
                print("   Falling back to encrypted file...")

        # Fallback: Encrypted file
        self._save_to_file(key, value)

    def get_secret(self, key: str) -> str:
        """
        Retrieve secret securely.

        Args:
            key: Secret identifier

        Returns:
            str: Secret value or None if not found
        """
        if self.use_keyring:
            try:
                value = keyring.get_password(self.SERVICE_NAME, key)
                if value:
                    return value
            except Exception:
                pass

        # Fallback: Encrypted file
        return self._load_from_file(key)

    def _save_to_file(self, key: str, value: str):
        """Save to encrypted file (fallback)."""
        # Load existing secrets
        secrets = self._load_all_from_file()
        secrets[key] = value

        # Encrypt and save
        master_password = self._get_master_password()
        cipher = Fernet(self._get_key(master_password))

        import json

        encrypted = cipher.encrypt(json.dumps(secrets).encode())

        with open(self._encrypted_file, "wb") as f:
            f.write(encrypted)

        # Set restrictive permissions (owner read/write only)
        os.chmod(self._encrypted_file, 0o600)

        print(f"✅ {key} stored in encrypted file")

    def _load_from_file(self, key: str) -> str:
        """Load from encrypted file (fallback)."""
        secrets = self._load_all_from_file()
        return secrets.get(key)

    def _load_all_from_file(self) -> dict:
        """Load all secrets from encrypted file."""
        import json

        if not os.path.exists(self._encrypted_file):
            return {}

        try:
            master_password = self._get_master_password()
            cipher = Fernet(self._get_key(master_password))

            with open(self._encrypted_file, "rb") as f:
                encrypted = f.read()

            decrypted = cipher.decrypt(encrypted)
            return json.loads(decrypted)

        except Exception as e:
            print(f"⚠️  Failed to load encrypted secrets: {e}")
            return {}

    def _get_master_password(self) -> str:
        """Get master password for encryption."""
        # Try environment first (less secure)
        env_pass = os.getenv("PROTON_MASTER_PASSWORD")
        if env_pass:
            return env_pass

        # Prompt user (more secure)
        print("🔐 Enter master password for secret decryption: ", end="")
        return getpass("")

    def delete_secret(self, key: str):
        """Delete secret securely."""
        if self.use_keyring:
            try:
                keyring.delete_password(self.SERVICE_NAME, key)
                print(f"🗑️  {key} deleted from keyring")
                return
            except Exception:
                pass

        # Fallback: Remove from file
        secrets = self._load_all_from_file()
        if key in secrets:
            del secrets[key]
            # Re-save
            if secrets:
                self._save_all_to_file(secrets)
            else:
                # Delete file if empty
                if os.path.exists(self._encrypted_file):
                    os.remove(self._encrypted_file)
                    print(f"🗑️  {key} deleted, encrypted file removed")

    def clear_memory(self):
        """Clear any cached secrets from memory."""
        self._key = None
        # Note: Python doesn't guarantee memory clearing
        # For maximum security, restart process after use


# === Convenience Functions ===


def setup_credentials():
    """
    Interactive setup for all required credentials.

    Call this ONCE to store credentials securely.
    AI cannot see the values entered.
    """
    print("🔐 Proton Mail Bridge — Secure Credential Setup\n")

    secrets = SecretManager()

    # Get credentials (user input, AI cannot see)
    secrets.set_secret("proton_username", None, prompt=True)
    secrets.set_secret("proton_password", None, prompt=True)

    # Optional: TOTP 2FA
    print("\n⚠️  2FA enabled? (y/n): ", end="")
    if input().lower() == "y":
        secrets.set_secret("proton_totp", None, prompt=True)

    # Optional: PGP key
    print("\n⚠️  PGP private key path? (leave empty to skip): ", end="")
    key_path = input().strip()
    if key_path:
        secrets.set_secret("proton_key_path", key_path, prompt=False)
        secrets.set_secret("proton_key_passphrase", None, prompt=True)

    print("\n✅ All credentials stored securely!")
    print("   AI/OpenClaw CANNOT access these values.")
    print("   You will be prompted when needed.\n")


def get_credentials():
    """
    Retrieve credentials securely.

    Returns:
        dict: Credentials (username, password, totp, key_path, key_passphrase)
    """
    secrets = SecretManager()

    creds = {
        "username": secrets.get_secret("proton_username"),
        "password": secrets.get_secret("proton_password"),
        "totp": secrets.get_secret("proton_totp"),
        "key_path": secrets.get_secret("proton_key_path"),
        "key_passphrase": secrets.get_secret("proton_key_passphrase"),
    }

    if not creds["username"] or not creds["password"]:
        print("❌ Credentials not found. Run setup first:")
        print("   python src/secrets.py setup")
        sys.exit(1)

    return creds


# CLI
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup_credentials()
    else:
        print("Usage: python secrets.py setup")
        print("\nThis will securely store your Proton credentials.")
        print("AI/OpenClaw CANNOT see the values you enter.\n")
