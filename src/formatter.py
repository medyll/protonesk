#!/usr/bin/env python3
"""
Proton Mail Context Formatter

Cleans and formats decrypted messages for LLM consumption.
HTML → Markdown, strip metadata, JSON output.
"""

import re
import html
from typing import Dict, Any
from datetime import datetime


class ContextFormatter:
    """Format Proton messages for LLM context."""

    def __init__(self):
        pass

    def html_to_markdown(self, html_content: str) -> str:
        """
        Convert HTML to clean Markdown.

        Args:
            html_content: Raw HTML

        Returns:
            str: Markdown text
        """
        if not html_content:
            return ""

        # Unescape HTML entities
        text = html.unescape(html_content)

        # Strip HTML tags (basic)
        text = re.sub(r"<br\s*/?>", "\n", text)
        text = re.sub(r"<p.*?>", "\n\n", text)
        text = re.sub(r"</p>", "", text)
        text = re.sub(r"<h([1-6]).*?>", lambda m: "\n" + "#" * int(m.group(1)) + " ", text)
        text = re.sub(r"</h[1-6]>", "", text)
        text = re.sub(r"<strong.*?>", "**", text)
        text = re.sub(r"</strong>", "**", text)
        text = re.sub(r"<em.*?>", "*", text)
        text = re.sub(r"</em>", "*", text)
        text = re.sub(r'<a.*?href="(.*?)".*?>', lambda m: f"[link]({m.group(1)})", text)
        text = re.sub(r"</a>", "", text)
        text = re.sub(r"<[^>]+>", "", text)

        # Clean up whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = text.strip()

        return text

    def format_message(self, message: dict, decrypted_body: str) -> Dict[str, Any]:
        """
        Format message for LLM context.

        Args:
            message: Message metadata from API
            decrypted_body: Decrypted plaintext body

        Returns:
            dict: Formatted message for LLM
        """
        # Convert timestamp
        time_obj = datetime.fromtimestamp(message.get("Time", 0))
        formatted_date = time_obj.isoformat()

        # Convert body to markdown
        markdown_body = self.html_to_markdown(decrypted_body)

        # Build context object
        to_list = message.get("ToList", [])
        to_address = to_list[0].get("Address", "Unknown") if to_list else "Unknown"

        context = {
            "from": message.get("Sender", {}).get("Address", "Unknown"),
            "to": to_address,
            "subject": message.get("Subject", "No subject"),
            "date": formatted_date,
            "body": markdown_body,
            "labels": message.get("LabelIDs", []),
            "unread": message.get("Unread", False),
        }

        return context

    def format_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        Format context as LLM prompt string.

        Args:
            context: Formatted message dict

        Returns:
            str: Prompt-ready string
        """
        prompt = f"""
📧 Email Context
────────────────
From: {context['from']}
To: {context['to']}
Date: {context['date']}
Subject: {context['subject']}

{context['body']}
────────────────
"""
        return prompt

    def format_batch(self, messages: list) -> str:
        """
        Format multiple messages for LLM.

        Args:
            messages: List of formatted message dicts

        Returns:
            str: Combined prompt
        """
        if not messages:
            return "📭 No messages found."

        prompt = f"📬 Inbox Summary ({len(messages)} messages)\n"
        prompt += "=" * 50 + "\n\n"

        for i, msg in enumerate(messages, 1):
            prompt += f"[{i}] {msg['subject']}\n"
            prompt += f"    From: {msg['from']} | Date: {msg['date']}\n\n"

        return prompt


# CLI usage
if __name__ == "__main__":
    formatter = ContextFormatter()

    # Test HTML → Markdown
    sample_html = "<p>Hello <strong>world</strong>!</p><br><p>Test email.</p>"
    markdown = formatter.html_to_markdown(sample_html)
    print(f"HTML: {sample_html}")
    print(f"Markdown: {markdown}")
