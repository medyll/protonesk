#!/usr/bin/env python3
"""
Proton Mail Crypto Module — PGP Decryption

Handles local decryption of Proton Mail PGP messages.
Decrypted content NEVER written to disk.
"""

import re
import gnupg
from typing import Optional


class ProtonCrypto:
    """Local PGP decryption for Proton Mail."""

    def __init__(self, private_key_path: str, passphrase: str):
        """
        Initialize crypto module.

        Args:
            private_key_path: Path to private PGP key (GPG keyring)
            passphrase: Passphrase for private key
        """
        self.gpg = gnupg.GPG()
        self.passphrase = passphrase
        self.private_key_path = private_key_path

        # Import private key if provided
        if private_key_path:
            self._import_private_key(private_key_path)

    def _import_private_key(self, key_path: str):
        """Import private key into GPG keyring."""
        print(f"🔑 Importing private key from {key_path}...")

        with open(key_path, "r") as f:
            key_data = f.read()

        import_result = self.gpg.import_keys(key_data, passphrase=self.passphrase)

        if import_result.count == 0:
            raise ValueError("Failed to import private key")

        print(f"✅ Private key imported: {import_result.fingerprints}")

    def _extract_pgp_block(self, content: str) -> Optional[str]:
        """
        Extract PGP encrypted block from message.

        Args:
            content: Raw message content

        Returns:
            str: PGP block or None if not found
        """
        pgp_pattern = r"(-----BEGIN PGP MESSAGE-----.*?-----END PGP MESSAGE-----)"
        match = re.search(pgp_pattern, content, re.DOTALL)

        return match.group(1) if match else None

    def decrypt(self, encrypted_content: str) -> str:
        """
        Decrypt PGP message in-memory.

        ⚠️  SECURITY: Decrypted content is NEVER written to disk.

        Args:
            encrypted_content: PGP encrypted message

        Returns:
            str: Decrypted plaintext

        Raises:
            ValueError: If decryption fails
        """
        # Extract PGP block if wrapped in HTML/text
        pgp_block = self._extract_pgp_block(encrypted_content)
        if not pgp_block:
            pgp_block = encrypted_content  # Assume raw PGP

        # Decrypt in-memory (no file I/O)
        decrypted = self.gpg.decrypt(pgp_block, passphrase=self.passphrase)

        if not decrypted.ok:
            raise ValueError(f"Decryption failed: {decrypted.status}")

        plaintext = decrypted.data.decode("utf-8")
        print("✅ Message decrypted (in-memory)")

        return plaintext

    def decrypt_message_body(self, message: dict) -> str:
        """
        Decrypt Proton message body.

        Args:
            message: Message dict from API (with 'Body' field)

        Returns:
            str: Decrypted body
        """
        body = message.get("Body", "")

        if not body:
            return ""

        return self.decrypt(body)


# CLI usage
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    key_path = os.getenv("PROTON_PRIVATE_KEY_PATH")
    passphrase = os.getenv("PROTON_KEY_PASSPHRASE")

    if not key_path or not passphrase:
        print("❌ PROTON_PRIVATE_KEY_PATH and PROTON_KEY_PASSPHRASE required")
        exit(1)

    crypto = ProtonCrypto(key_path, passphrase)

    # Test with sample encrypted message
    sample = """-----BEGIN PGP MESSAGE-----
Version: ProtonMail
Comment: https://proton.me
Comment: Charset: UTF-8

[encrypted content here]
-----END PGP MESSAGE-----"""

    print("Testing decryption...")
    # Note: This will fail without real encrypted content
    # crypto.decrypt(sample)
