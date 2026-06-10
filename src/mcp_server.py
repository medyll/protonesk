#!/usr/bin/env python3
"""
Protonesk — MCP Server

Exposes Proton Mail to LLM agents (Claude Desktop, Claude Code, any MCP client)
as structured tools. Credentials never reach the model — they load from the OS
keyring via src.secrets, same as the rest of the bridge.

Run standalone:
    python src/mcp_server.py

Register with Claude Code:
    claude mcp add proton-mail -- python D:/development/proton-mail-bridge/src/mcp_server.py

Note on stdout: the underlying modules print status lines to stdout, but the MCP
stdio transport uses stdout for JSON-RPC framing. Every tool body therefore runs
under redirect_stdout(stderr) so those prints can't corrupt the protocol stream.
"""

import os
import sys
import contextlib
from functools import wraps
from pathlib import Path

# Allow running as a loose script (python src/mcp_server.py) as well as a module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP  # noqa: E402

# Transport config. Default stdio (client spawns us). HTTP is for a long-running
# boot service that agents connect to over the network.
#   PROTON_MCP_HTTP=1            → streamable-http transport
#   PROTON_MCP_HOST=127.0.0.1   → bind host
#   PROTON_MCP_PORT=8787        → bind port
_HTTP = os.environ.get("PROTON_MCP_HTTP") == "1" or "--http" in sys.argv
_HOST = os.environ.get("PROTON_MCP_HOST", "127.0.0.1")
_PORT = int(os.environ.get("PROTON_MCP_PORT", "8787"))

from src.auth import ProtonAuth  # noqa: E402
from src.api_client import ProtonAPIClient  # noqa: E402
from src.crypto import ProtonCrypto  # noqa: E402
from src.formatter import ContextFormatter  # noqa: E402
from src.send import ProtonSend  # noqa: E402
from src.lifecycle import MessageLifecycle  # noqa: E402
from src.secrets import get_credentials  # noqa: E402

mcp = FastMCP("proton-mail", host=_HOST, port=_PORT)

# ── Lazy singletons ─────────────────────────────────────────────────────────────
# Built on first tool call, not at import. Keeps the server from authenticating
# (and possibly blocking on 2FA) just because a client listed the tool catalogue.

_state = {"auth": None, "session": None, "api": None, "crypto": None,
          "send": None, "lifecycle": None, "formatter": ContextFormatter()}


def _muted(fn):
    """Run a tool body with module stdout chatter pushed to stderr."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with contextlib.redirect_stdout(sys.stderr):
            return fn(*args, **kwargs)
    return wrapper


def _ensure_session():
    if _state["session"] is None:
        auth = ProtonAuth()                      # creds from keyring (AI-invisible)
        _state["auth"] = auth
        _state["session"] = auth.authenticate()
        _state["api"] = ProtonAPIClient(_state["session"])
        _state["lifecycle"] = MessageLifecycle(_state["session"])

        creds = get_credentials()
        key_path = creds.get("key_path")
        key_pass = creds.get("key_passphrase")
        if key_path and key_pass:
            _state["crypto"] = ProtonCrypto(key_path, key_pass)
            _state["send"] = ProtonSend(_state["session"], _state["crypto"])
        _state["username"] = creds["username"]
    return _state


# ── Read tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
@_muted
def list_messages(label: str = "0", unread: bool = False, limit: int = 10) -> list:
    """List messages from a mailbox folder.

    Args:
        label: Proton LabelID. "0" = Inbox, "6" = Archive, "3" = Trash.
               Use list_labels() to discover custom folder IDs.
        unread: Only return unread messages.
        limit: Max messages (default 10).

    Returns:
        Compact metadata list: id, from, subject, date, unread.
    """
    s = _ensure_session()
    msgs = s["api"].get_messages(label=label, unread=unread, limit=limit)
    return [
        {
            "id": m.get("ID"),
            "from": m.get("Sender", {}).get("Address", "Unknown"),
            "subject": m.get("Subject", "No subject"),
            "date": m.get("Time"),
            "unread": bool(m.get("Unread", 0)),
        }
        for m in msgs
    ]


@mcp.tool()
@_muted
def read_message(message_id: str) -> dict:
    """Fetch, decrypt, and format a single message for LLM context.

    Args:
        message_id: Proton message ID (from list_messages).

    Returns:
        Structured dict: from, to, subject, date, body (Markdown), unread.
        If no PGP key is configured the body stays encrypted.
    """
    s = _ensure_session()
    raw = s["api"].get_message(message_id)
    if s["crypto"]:
        body = s["crypto"].decrypt_message_body(raw)
    else:
        body = raw.get("Body", "")
    return s["formatter"].format_message(raw, body)


@mcp.tool()
@_muted
def list_labels() -> list:
    """List all folders/labels with their IDs and names."""
    s = _ensure_session()
    return [
        {"id": l.get("ID"), "name": l.get("Name"), "type": l.get("Type")}
        for l in s["api"].get_labels()
    ]


# ── Write tools ───────────────────────────────────────────────────────────────────

@mcp.tool()
@_muted
def send_message(to: str, subject: str, body: str) -> dict:
    """Send an encrypted email.

    Requires a PGP key configured in the keyring (run `python src/secrets.py setup`).

    Args:
        to: Recipient email address.
        subject: Subject line.
        body: Plaintext/HTML body (encrypted before send).

    Returns:
        {"sent": bool}.
    """
    s = _ensure_session()
    if not s["send"]:
        return {"sent": False, "error": "No PGP key configured — sending disabled."}
    ok = s["send"].send_email(
        subject=subject,
        sender=s["username"],
        recipients=[to],
        body=body,
    )
    return {"sent": bool(ok)}


@mcp.tool()
@_muted
def mark_read(message_id: str) -> dict:
    """Mark a message as read."""
    s = _ensure_session()
    return {"ok": s["lifecycle"].mark_as_read(message_id)}


@mcp.tool()
@_muted
def archive_message(message_id: str) -> dict:
    """Archive a message (remove from inbox, keep in All Mail)."""
    s = _ensure_session()
    return {"ok": s["lifecycle"].archive(message_id)}


@mcp.tool()
@_muted
def trash_message(message_id: str) -> dict:
    """Move a message to Trash (soft delete, reversible)."""
    s = _ensure_session()
    return {"ok": s["lifecycle"].move_to_trash(message_id)}


if __name__ == "__main__":
    if _HTTP:
        print(f"proton-mail MCP (streamable-http) on http://{_HOST}:{_PORT}/mcp", file=sys.stderr)
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
