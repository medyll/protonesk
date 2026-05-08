#!/usr/bin/env python3
"""
Proton Mail Send Flow — Encrypted Email Dispatch

Handles draft creation, PGP encryption, and sending.
Maintains cryptographic integrity throughout the process.
"""

import time
from typing import Dict, List, Optional
from proton.session import ProtonSession


class ProtonSend:
    """Send encrypted emails via Proton API."""

    def __init__(self, session: ProtonSession, crypto_module):
        """
        Initialize send module.

        Args:
            session: Authenticated Proton session
            crypto_module: Crypto module for PGP encryption
        """
        self.session = session
        self.crypto = crypto_module
        self.base_url = "https://mail.proton.me/api"
        self.cooldown_ms = 2000  # 2s between sends (human-like)
        self.last_send_time = 0

    def _cooldown(self):
        """Enforce cooldown between send operations."""
        elapsed = (time.time() * 1000) - self.last_send_time
        if elapsed < self.cooldown_ms:
            sleep_time = (self.cooldown_ms - elapsed) / 1000
            time.sleep(sleep_time)
        self.last_send_time = time.time() * 1000

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make API request."""
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_recipient_keys(self, email: str) -> Dict:
        """
        Get recipient's public keys via Proton Discovery.

        Args:
            email: Recipient email address

        Returns:
            dict: Key information or empty dict if not found
        """
        print(f"🔑 Looking up public keys for {email}...")

        try:
            response = self._request("GET", f"/mail/v4/keys/{email}")
            keys = response.get("Keys", [])

            if keys:
                print(f"✅ Found {len(keys)} key(s) for {email}")
            else:
                print(f"⚠️  No keys found for {email} (external recipient)")

            return keys

        except Exception as e:
            print(f"❌ Key lookup failed: {e}")
            return {}

    def create_draft(
        self, subject: str, sender: str, recipients: List[str], body: str, thread_id: Optional[str] = None
    ) -> str:
        """
        Create draft message to get MessageID.

        Args:
            subject: Email subject
            sender: Sender address
            recipients: List of recipient emails
            body: Plaintext body (will be encrypted)
            thread_id: ThreadID for replies (optional)

        Returns:
            str: MessageID of created draft
        """
        print("📝 Creating draft...")

        draft_data = {
            "Message": {
                "Subject": subject,
                "Sender": {"Address": sender},
                "ToList": [{"Address": r} for r in recipients],
                "Body": body,  # Will be replaced with encrypted version
                "MIMEType": "text/html",
            }
        }

        if thread_id:
            draft_data["Message"]["ThreadID"] = thread_id

        response = self._request("POST", "/mail/v4/drafts", json=draft_data)
        message_id = response.get("Message", {}).get("ID")

        if message_id:
            print(f"✅ Draft created: {message_id}")
        else:
            raise ValueError("Failed to create draft")

        return message_id

    def encrypt_body(self, body: str, recipient_keys: List[Dict]) -> str:
        """
        Encrypt message body with recipient's public key.

        Args:
            body: Plaintext body
            recipient_keys: List of recipient public keys

        Returns:
            str: PGP encrypted block
        """
        print("🔐 Encrypting message body...")

        # For now, use local encryption (simplified)
        # In production, use recipient's public key
        encrypted = self.crypto.encrypt_for_recipient(body, recipient_keys)

        print("✅ Body encrypted")
        return encrypted

    def update_draft(self, message_id: str, encrypted_body: str) -> bool:
        """
        Update draft with encrypted body.

        Args:
            message_id: Draft MessageID
            encrypted_body: PGP encrypted body

        Returns:
            bool: True if successful
        """
        print(f"📝 Updating draft {message_id} with encrypted body...")

        try:
            self._request(
                "PUT",
                f"/mail/v4/messages/{message_id}",
                json={"Message": {"Body": encrypted_body, "MIMEType": "text/html"}},
            )

            print("✅ Draft updated")
            return True

        except Exception as e:
            print(f"❌ Failed to update draft: {e}")
            return False

    def send_draft(self, message_id: str) -> bool:
        """
        Send the draft.

        Args:
            message_id: Draft MessageID

        Returns:
            bool: True if successful
        """
        print(f"🚀 Sending draft {message_id}...")

        try:
            self._request("POST", f"/mail/v4/messages/{message_id}/send")

            print("✅ Message sent")
            return True

        except Exception as e:
            print(f"❌ Send failed: {e}")
            return False

    def send_email(
        self, subject: str, sender: str, recipients: List[str], body: str, thread_id: Optional[str] = None
    ) -> bool:
        """
        Complete send flow: draft → encrypt → send.

        Args:
            subject: Email subject
            sender: Sender address
            recipients: List of recipient emails
            body: Plaintext body
            thread_id: ThreadID for replies (optional)

        Returns:
            bool: True if send successful
        """
        self._cooldown()

        try:
            # Step 1: Get recipient keys
            recipient_keys = []
            for email in recipients:
                keys = self.get_recipient_keys(email)
                recipient_keys.extend(keys)

            # Step 2: Create draft
            message_id = self.create_draft(subject, sender, recipients, body, thread_id)

            # Step 3: Encrypt body
            encrypted_body = self.encrypt_body(body, recipient_keys)

            # Step 4: Update draft
            if not self.update_draft(message_id, encrypted_body):
                raise ValueError("Failed to update draft")

            # Step 5: Send
            if not self.send_draft(message_id):
                raise ValueError("Failed to send")

            print("✅ Email sent successfully")
            return True

        except Exception as e:
            print(f"❌ Send flow failed: {e}")
            # Atomicity: delete draft on failure
            try:
                self._request("DELETE", f"/mail/v4/messages/{message_id}")
                print("🗑️  Draft deleted (cleanup on failure)")
            except Exception:
                pass
            return False


# CLI usage
if __name__ == "__main__":
    from auth import ProtonAuth
    from crypto import ProtonCrypto

    auth = ProtonAuth()
    session = auth.authenticate()

    crypto = ProtonCrypto(key_path="...", passphrase="...")
    sender = ProtonSend(session, crypto)

    # Test send
    # sender.send_email(
    #     subject="Test",
    #     sender="me@proton.me",
    #     recipients=["recipient@example.com"],
    #     body="Hello!"
    # )

    auth.logout()
