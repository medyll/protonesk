#!/usr/bin/env python3
"""
Proton Mail Message Lifecycle Management

Handles message state transitions: read, archive, delete.
Uses label management rather than destructive operations where possible.
"""

import time
from typing import List, Optional
from proton.session import ProtonSession


class MessageLifecycle:
    """Manage Proton message lifecycle (read, archive, delete)."""

    def __init__(self, session: ProtonSession, cooldown_ms: int = 1000):
        """
        Initialize lifecycle manager.

        Args:
            session: Authenticated Proton session
            cooldown_ms: Cooldown between write operations (default: 1s)
        """
        self.session = session
        self.base_url = "https://mail.proton.me/api"
        self.cooldown_ms = cooldown_ms
        self.last_write_time = 0

    def _cooldown(self):
        """Enforce cooldown between write operations."""
        elapsed = (time.time() * 1000) - self.last_write_time
        if elapsed < self.cooldown_ms:
            sleep_time = (self.cooldown_ms - elapsed) / 1000
            time.sleep(sleep_time)
        self.last_write_time = time.time() * 1000

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make API request with cooldown for write operations."""
        if method in ["PUT", "POST", "PATCH", "DELETE"]:
            self._cooldown()

        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def mark_as_read(self, message_id: str) -> bool:
        """
        Mark message as read.

        Args:
            message_id: Proton message ID

        Returns:
            bool: True if successful
        """
        print(f"📖 Marking message {message_id} as read...")

        try:
            self._request("PATCH", f"/mail/v4/messages/{message_id}", json={"IsRead": 1})

            print("✅ Message marked as read")
            return True

        except Exception as e:
            print(f"❌ Failed to mark as read: {e}")
            return False

    def mark_batch_as_read(self, message_ids: List[str]) -> int:
        """
        Mark multiple messages as read (batch operation).

        Args:
            message_ids: List of message IDs

        Returns:
            int: Number of successfully marked messages
        """
        print(f"📖 Marking {len(message_ids)} messages as read (batch)...")

        success_count = 0
        for msg_id in message_ids:
            if self.mark_as_read(msg_id):
                success_count += 1

        print(f"✅ {success_count}/{len(message_ids)} messages marked as read")
        return success_count

    def get_trash_label_id(self) -> Optional[str]:
        """
        Get the LabelID for Trash folder.

        Returns:
            str: Trash LabelID or None if not found
        """
        response = self._request("GET", "/mail/v4/labels")
        labels = response.get("Labels", [])

        for label in labels:
            if label.get("Name") == "Trash" or label.get("Type") == 3:
                return label.get("ID")

        return None

    def move_to_trash(self, message_id: str) -> bool:
        """
        Move message to Trash (soft delete).

        Args:
            message_id: Proton message ID

        Returns:
            bool: True if successful
        """
        trash_id = self.get_trash_label_id()

        if not trash_id:
            print("❌ Trash folder not found")
            return False

        print(f"🗑️  Moving message {message_id} to Trash...")

        try:
            self._request("PUT", f"/mail/v4/messages/{message_id}/label", json={"LabelIDs": [trash_id]})

            print("✅ Message moved to Trash")
            return True

        except Exception as e:
            print(f"❌ Failed to move to Trash: {e}")
            return False

    def delete_permanently(self, message_id: str) -> bool:
        """
        Permanently delete message (from Trash).

        ⚠️  DESTRUCTIVE OPERATION — Cannot be undone

        Args:
            message_id: Proton message ID

        Returns:
            bool: True if successful
        """
        print(f"☠️  Permanently deleting message {message_id}...")

        try:
            self._request("DELETE", f"/mail/v4/messages/{message_id}")

            print("✅ Message permanently deleted")
            return True

        except Exception as e:
            print(f"❌ Failed to delete: {e}")
            return False

    def batch_delete(self, message_ids: List[str], permanent: bool = False) -> int:
        """
        Delete multiple messages.

        Args:
            message_ids: List of message IDs
            permanent: If True, permanent delete (default: move to Trash)

        Returns:
            int: Number of successfully deleted messages
        """
        print(f"🗑️  Deleting {len(message_ids)} messages (permanent={permanent})...")

        success_count = 0
        for msg_id in message_ids:
            if permanent:
                if self.delete_permanently(msg_id):
                    success_count += 1
            else:
                if self.move_to_trash(msg_id):
                    success_count += 1

        print(f"✅ {success_count}/{len(message_ids)} messages deleted")
        return success_count

    def archive(self, message_id: str) -> bool:
        """
        Archive message (remove from inbox, keep in All Mail).

        Args:
            message_id: Proton message ID

        Returns:
            bool: True if successful
        """
        print(f"📦 Archiving message {message_id}...")

        try:
            # Remove inbox label
            self._request(
                "PUT",
                f"/mail/v4/messages/{message_id}/label",
                json={"LabelIDs": []},  # Empty = remove from inbox, keep in All Mail
            )

            print("✅ Message archived")
            return True

        except Exception as e:
            print(f"❌ Failed to archive: {e}")
            return False


# CLI usage
if __name__ == "__main__":
    from auth import ProtonAuth

    auth = ProtonAuth()
    session = auth.authenticate()

    lifecycle = MessageLifecycle(session, cooldown_ms=1000)

    # Test operations
    # lifecycle.mark_as_read("message_id")
    # lifecycle.move_to_trash("message_id")
    # lifecycle.archive("message_id")

    auth.logout()
