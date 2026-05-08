#!/usr/bin/env python3
"""
Tests unitaires — Context Formatter (HTML → Markdown)

Run: pytest tests/test_formatter.py -v
"""

import pytest
import os
from datetime import datetime

# Import module à tester
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from formatter import ContextFormatter


class TestContextFormatter:
    """Tests pour ContextFormatter."""
    
    @pytest.fixture
    def formatter(self):
        """Fixture: Formatter instance."""
        return ContextFormatter()
    
    def test_html_to_markdown_empty(self, formatter):
        """Test: Empty HTML returns empty string."""
        result = formatter.html_to_markdown("")
        assert result == ""
    
    def test_html_to_markdown_paragraphs(self, formatter):
        """Test: HTML paragraphs converted to markdown."""
        html = "<p>Hello world!</p><p>Second paragraph.</p>"
        result = formatter.html_to_markdown(html)
        
        assert "Hello world!" in result
        assert "Second paragraph." in result
    
    def test_html_to_markdown_bold(self, formatter):
        """Test: Bold tags converted to markdown."""
        html = "<p><strong>Bold text</strong></p>"
        result = formatter.html_to_markdown(html)
        
        assert "**Bold text**" in result
    
    def test_html_to_markdown_italic(self, formatter):
        """Test: Italic tags converted to markdown."""
        html = "<p><em>Italic text</em></p>"
        result = formatter.html_to_markdown(html)
        
        assert "*Italic text*" in result
    
    def test_html_to_markdown_links(self, formatter):
        """Test: Links converted to markdown."""
        html = '<p>Visit <a href="https://example.com">Example</a></p>'
        result = formatter.html_to_markdown(html)
        
        assert "[link](https://example.com)" in result
    
    def test_html_to_markdown_line_breaks(self, formatter):
        """Test: Line breaks preserved."""
        html = "<p>Line 1<br>Line 2</p>"
        result = formatter.html_to_markdown(html)
        
        assert "\n" in result
    
    def test_html_to_markdown_headings(self, formatter):
        """Test: Headings converted to markdown."""
        html = "<h1>Title</h1><h2>Subtitle</h2>"
        result = formatter.html_to_markdown(html)
        
        assert "# Title" in result
        assert "## Subtitle" in result
    
    def test_html_to_markdown_stripped_tags(self, formatter):
        """Test: All HTML tags stripped."""
        html = "<div><p><span>Content</span></p></div>"
        result = formatter.html_to_markdown(html)
        
        assert "Content" in result
        assert "<" not in result  # No HTML tags remaining
    
    def test_format_message_basic(self, formatter):
        """Test: Format message for LLM context."""
        message = {
            "Sender": {"Address": "sender@example.com"},
            "ToList": [{"Address": "me@proton.me"}],
            "Subject": "Test Email",
            "Time": datetime(2026, 4, 8, 10, 0, 0).timestamp(),
            "LabelIDs": ["inbox"],
            "Unread": True
        }
        decrypted_body = "Hello from sender!"
        
        result = formatter.format_message(message, decrypted_body)
        
        assert result["from"] == "sender@example.com"
        assert result["to"] == "me@proton.me"
        assert result["subject"] == "Test Email"
        assert result["body"] == "Hello from sender!"
        assert result["unread"] == True
    
    def test_format_message_empty_lists(self, formatter):
        """Test: Format message with empty ToList."""
        message = {
            "Sender": {"Address": "sender@example.com"},
            "ToList": [],
            "Subject": "Test",
            "Time": 0,
            "LabelIDs": [],
            "Unread": False
        }
        
        result = formatter.format_message(message, "Body")
        
        assert result["to"] == "Unknown"
    
    def test_format_for_prompt(self, formatter):
        """Test: Format context as LLM prompt string."""
        context = {
            "from": "sender@example.com",
            "to": "me@proton.me",
            "date": "2026-04-08T10:00:00",
            "subject": "Test Subject",
            "body": "Email body content",
            "labels": ["inbox"],
            "unread": True
        }
        
        result = formatter.format_for_prompt(context)
        
        assert "📧 Email Context" in result
        assert "From: sender@example.com" in result
        assert "Subject: Test Subject" in result
        assert "Email body content" in result
    
    def test_format_batch_empty(self, formatter):
        """Test: Format empty batch."""
        result = formatter.format_batch([])
        
        assert "No messages found" in result
    
    def test_format_batch_multiple(self, formatter):
        """Test: Format multiple messages."""
        messages = [
            {
                "from": "sender1@example.com",
                "to": "me@proton.me",
                "date": "2026-04-08T10:00:00",
                "subject": "Email 1",
                "body": "Body 1",
                "labels": ["inbox"],
                "unread": True
            },
            {
                "from": "sender2@example.com",
                "to": "me@proton.me",
                "date": "2026-04-08T11:00:00",
                "subject": "Email 2",
                "body": "Body 2",
                "labels": ["inbox"],
                "unread": False
            }
        ]
        
        result = formatter.format_batch(messages)
        
        assert "Inbox Summary (2 messages)" in result
        assert "[1] Email 1" in result
        assert "[2] Email 2" in result
        assert "From: sender1@example.com" in result


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
