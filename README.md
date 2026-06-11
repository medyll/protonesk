# Protonesk

Use your Proton Mail account in any email client — Thunderbird, Apple Mail, Outlook — or connect it to AI agents and automation tools. No paid subscription required.

Protonesk runs locally on your machine and acts as a standard mail server. Your email client talks to Protonesk; Protonesk talks to Proton. Everything stays encrypted end-to-end.

---

## Requirements

- Python 3.11 or later
- A Proton Mail account (free plan works)

---

## Installation

```bash
pip install -r requirements.txt
pip install setuptools python-gnupg
pip install --no-build-isolation git+https://github.com/ProtonMail/proton-python-client.git
```

> `proton-python-client` isn't on PyPI and its setup script needs `gnupg`/`setuptools` already present at build time — that's why it's a separate, ordered step.

---

## First-time setup

Run this once to store your **real Proton account credentials** securely. Protonesk never writes your password to a file — it goes into your operating system's encrypted keychain (Windows Credential Manager, macOS Keychain, or the Linux secret service).

```bash
python src/secrets.py setup
```

You'll be prompted for:

| Prompt | What to enter |
|---|---|
| Proton username | your Proton Mail address, e.g. `you@proton.me` |
| Proton password | your **real Proton account password** |
| 2FA enabled? | `y` if your Proton account has TOTP 2FA, then enter the secret |
| PGP private key path | optional — leave empty to skip (required only for `send_message` / SMTP sending) |

That's it for one account. This is unrelated to the "local password" below — see [Connecting your email client](#connecting-your-email-client).

---

## Running Protonesk

### Option 1 — Run manually (terminal stays open)

```bash
python main.py
```

Protonesk starts and prints the connection details. Keep the terminal open while you use it.

### Option 2 — Run as a background service (recommended)

Protonesk can install itself as a system service that starts automatically with your computer.

**Windows:**
```powershell
.\scripts\install-service-windows.ps1 install
.\scripts\install-service-windows.ps1 start
```

To check status, stop, or uninstall:
```powershell
.\scripts\install-service-windows.ps1 status
.\scripts\install-service-windows.ps1 stop
.\scripts\install-service-windows.ps1 uninstall
```

**Linux:**
```bash
./scripts/install-service-linux.sh install
systemctl --user start protonesk
systemctl --user status protonesk
journalctl --user -u protonesk -f   # live logs
```

### Option 3 — Cross-platform installer (detects your OS automatically)

```bash
python scripts/install.py
```

This checks your Python version, installs dependencies, walks you through the config, sets up the IMAP/SMTP service, **and** installs the [MCP server](#connecting-ai-agents-mcp) as a second auto-start service.

### Option 4 — System tray (Windows, optional)

```bash
python main.py --tray
```

Shows a colored icon in your taskbar: green when connected, red on error. Right-click to start/stop or open the config.

---

## Connecting your email client

Once Protonesk is running, add a new account in your email client with these settings:

| Setting | Value |
|---------|-------|
| Incoming (IMAP) server | `127.0.0.1` |
| IMAP port | `1143` (or `1993` with TLS enabled) |
| Outgoing (SMTP) server | `127.0.0.1` |
| SMTP port | `1025` |
| Username | anything (e.g. your email address) |
| Password | `bridge` (you can change this in `config.yaml`) |
| Connection security | None, or TLS if you enabled `--tls` |

> **Two different passwords, don't mix them up:**
> - **Proton password** — your real Proton account password, stored in the OS keychain via `python src/secrets.py setup`. Protonesk uses this to talk to Proton. You enter it once, never again.
> - **Local password** (`bridge` by default) — an arbitrary password *you invent*, set in `config.yaml` as `local_password`. Your email client uses this to talk to Protonesk on `127.0.0.1`. It has nothing to do with your Proton account — change it to anything you like.

---

## Connecting AI agents (MCP)

Protonesk also exposes a [Model Context Protocol](https://modelcontextprotocol.io) server so LLM agents (Claude Code, Claude Desktop, or any MCP client) can read and send mail through the same encrypted Proton session — without ever seeing your credentials.

**Tools provided:** `list_messages`, `read_message`, `list_labels`, `send_message`, `mark_read`, `archive_message`, `trash_message`.

### Run as a service (installed by `scripts/install.py`)

The installer sets up a second auto-start service serving over `streamable-http`:

```
http://127.0.0.1:8787/mcp
```

Connect Claude Code:
```bash
claude mcp add --transport http proton-mail http://127.0.0.1:8787/mcp
```

Manage it directly:

**Windows:**
```powershell
.\scripts\install-mcp-service-windows.ps1 install   # requires nssm.exe — run install-service-windows.ps1 first
.\scripts\install-mcp-service-windows.ps1 start
.\scripts\install-mcp-service-windows.ps1 status
```

**Linux:**
```bash
./scripts/install-mcp-service-linux.sh install
systemctl --user start proton-mcp
journalctl --user -u proton-mcp -f
```

Override the bind address/port before installing: `PROTON_MCP_HOST` / `PROTON_MCP_PORT` (default `127.0.0.1:8787`).

### Run on-demand (stdio, no service)

If your MCP client spawns its own server process instead:

```bash
claude mcp add proton-mail -- python /path/to/proton-mail-bridge/src/mcp_server.py
```

### Security

- Same keychain-based credentials as the bridge — the model never sees usernames, passwords, or PGP keys.
- HTTP transport binds to `127.0.0.1` by default (local only).
- `send_message` requires a PGP key configured via `python src/secrets.py setup`.
- `trash_message` is a soft delete; there is no permanent-delete tool exposed to agents.

---

## Configuration

`config.yaml` (project root) is **entirely optional**. With no file at all, Protonesk uses sensible defaults (ports 1143/1025, local password `bridge`) and the single account you stored with `python src/secrets.py setup`. Create the file only if you want to change something:

```yaml
imap_port: 1143
smtp_port: 1025
local_password: bridge      # password your email client uses to connect to Protonesk
tls: false                  # set to true to enable encrypted local connections
log_level: INFO
```

### Single account (default — most users)

Nothing to configure. Run `python src/secrets.py setup` once, then start Protonesk. Done.

### Multiple Proton accounts

Two steps — config.yaml alone is not enough, each extra account also needs its own password in the keychain.

**1. List the accounts in `config.yaml`:**

```yaml
accounts:
  - username: personal@proton.me
    label: personal
  - username: work@proton.me
    label: work
```

**2. Store a password for each `label`** using the `keyring` CLI (installed with the requirements). The first account you set up with `secrets.py setup` is reused as a fallback, but every additional account needs its own entry:

```bash
python -m keyring set proton-mail-bridge proton_password_personal
python -m keyring set proton-mail-bridge proton_password_work
# optional, only if that account has 2FA:
python -m keyring set proton-mail-bridge proton_totp_work
```

(`proton-mail-bridge` is the fixed keychain service name Protonesk uses — type it exactly as shown. You'll be prompted to paste each password.)

Your email client will then see separate mailbox folders: `personal/INBOX`, `work/INBOX`, `work/Sent`, etc.

---

## Common tasks

**Change the local password** (the one your email client uses):

Edit `config.yaml` and set `local_password: yourpassword`, then restart Protonesk.

**Enable TLS** (encrypted connection between your email client and Protonesk):

```bash
python main.py --tls
# or in config.yaml: tls: true
```

A self-signed certificate is generated automatically the first time. Your email client will show a security warning — this is expected for a local certificate. Add an exception to proceed.

**Use a different port** (if 1143 or 1025 are taken):

```bash
python main.py --imap-port 2143 --smtp-port 2025
```

**View logs** when running as a service:

- Windows: `%LOCALAPPDATA%\Protonesk\logs\bridge.log`
- Linux: `journalctl --user -u protonesk -f`

**Stop the service:**

- Windows: `.\scripts\install-service-windows.ps1 stop`
- Linux: `systemctl --user stop protonesk`

---

## Security

Protonesk is designed so that your credentials are never accessible to AI agents or other software running on your machine:

- Passwords are stored in your OS keychain, not in any file
- PGP decryption happens in memory — decrypted content is never written to disk
- Protonesk only listens on `127.0.0.1` (your own machine), never on the network
- The local password used by your email client is separate from your Proton password
- TLS certificates are renewed automatically before they expire

---

## For developers

<details>
<summary>Module overview, running tests, architecture details</summary>

### Running tests

```bash
pytest tests/        # 221 tests
pytest tests/test_auth.py   # specific module
```

### Module overview

| Module | Role |
|--------|------|
| `src/auth.py` | SRP authentication with Proton API |
| `src/api_client.py` | Proton REST API wrapper (rate limiting, retry) |
| `src/crypto.py` | PGP decryption via GPG (in-memory) |
| `src/send.py` | Send flow: draft → encrypt → deliver |
| `src/lifecycle.py` | Message state: read, archive, trash, delete |
| `src/formatter.py` | HTML → Markdown for LLM contexts |
| `src/secrets.py` | OS keychain credential storage |
| `src/imap_server.py` | Async IMAP4 server (RFC 3501 + IDLE) |
| `src/imap_bridge.py` | IMAP ↔ Proton API mapping, cache, fetch+decrypt |
| `src/smtp_server.py` | SMTP server (aiosmtpd) → ProtonSend |
| `src/session_manager.py` | Multi-account session pool, independent reconnect |
| `src/multi_account_bridge.py` | Multi-account IMAP with `label/mailbox` namespaces |
| `src/multi_account_smtp.py` | Multi-account SMTP routing by `From:` address |
| `src/event_loop.py` | Proton event long-poll → push to IMAP IDLE sessions |
| `src/tls.py` | Auto-generated RSA 2048 self-signed certificate |
| `src/config.py` | config.yaml + CLI args merge |
| `src/tray.py` | Windows system tray icon (pystray) |
| `src/mcp_server.py` | MCP server — exposes mail tools to LLM agents (stdio or HTTP) |
| `main.py` | Entry point: starts IMAP + SMTP, manages reconnection |

</details>
