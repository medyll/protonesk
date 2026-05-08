#!/usr/bin/env python3
"""
Proton Mail API Client

Wrapper for Proton's REST API with rate limiting and error handling.
"""

import time
from typing import List
from proton.session import ProtonSession


class ProtonAPIClient:
    """Proton Mail API client with rate limiting."""

    def __init__(self, session: ProtonSession):
        self.session = session
        self.base_url = "https://mail.proton.me/api"
        self.max_retries = 3
        self.base_delay = 1.0  # seconds

    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """
        Make API request with exponential backoff.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/mail/v4/messages')
            **kwargs: Additional request parameters

        Returns:
            dict: API response

        Raises:
            Exception: If request fails after retries
        """
        url = f"{self.base_url}{endpoint}"
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()

            except Exception as e:
                last_error = e

                # Check for rate limit (429)
                if hasattr(e, "response") and e.response.status_code == 429:
                    delay = self.base_delay * (2**attempt)
                    print(f"⏳ Rate limited, waiting {delay}s...")
                    time.sleep(delay)
                    continue

                # Other errors - retry with backoff
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    print(f"⚠️  Request failed, retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    break

        raise Exception(f"API request failed after {self.max_retries} retries: {last_error}")

    def get_messages(self, label: str = "INBOX", unread: bool = False, limit: int = 10) -> List[dict]:
        """
        Fetch messages from mailbox.

        Args:
            label: Folder/label name (default: INBOX)
            unread: Filter for unread only
            limit: Max messages to fetch

        Returns:
            List[dict]: Message metadata
        """
        params = {
            "LabelID": label,
            "Limit": limit,
        }

        if unread:
            params["Unread"] = 1

        print(f"📬 Fetching messages from {label}...")
        response = self._request("GET", "/mail/v4/messages", params=params)

        messages = response.get("Messages", [])
        print(f"✅ Found {len(messages)} messages")

        return messages

    def get_message(self, message_id: str) -> dict:
        """
        Fetch full message body.

        Args:
            message_id: Proton message ID

        Returns:
            dict: Message with encrypted body
        """
        print(f"📄 Fetching message {message_id}...")
        response = self._request("GET", f"/mail/v4/messages/{message_id}")

        message = response.get("Message", {})
        print("✅ Message fetched")

        return message

    def get_labels(self) -> List[dict]:
        """
        Fetch all labels/folders.

        Returns:
            List[dict]: Label metadata
        """
        print("🏷️  Fetching labels...")
        response = self._request("GET", "/mail/v4/labels")

        labels = response.get("Labels", [])
        print(f"✅ Found {len(labels)} labels")

        return labels


# CLI usage
if __name__ == "__main__":
    from auth import ProtonAuth

    auth = ProtonAuth()
    session = auth.authenticate()

    client = ProtonAPIClient(session)

    # Test API
    labels = client.get_labels()
    messages = client.get_messages(unread=True, limit=5)

    for msg in messages:
        print(f"  - {msg.get('Subject', 'No subject')}")

    auth.logout()
