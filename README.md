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
pip install git+https://github.com/ProtonMail/proton-python-client.git
```

---

## First-time setup

Run this once to store your Proton credentials securely. Protonesk will never store your password in a file — it goes into your operating system's encrypted keychain (Windows Credential Manager, macOS Keychain, or the Linux secret service).

```bash
python src/secrets.py setup
```

You'll be prompted for your Proton username, password, and optionally your 2FA secret and PGP key.

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

This checks your Python version, installs dependencies, walks you through the config, and sets up the service.

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

---

## Configuration

Create a `config.yaml` file at the root of the project to set your preferences. All settings are optional — the defaults work out of the box.

```yaml
imap_port: 1143
smtp_port: 1025
local_password: bridge      # password your email client uses to connect to Protonesk
tls: false                  # set to true to enable encrypted local connections
log_level: INFO
```

### Multiple Proton accounts

Add an `accounts` section to use more than one Proton account at the same time:

```yaml
accounts:
  - username: personal@proton.me
    label: personal
  - username: work@proton.me
    label: work
```

Your email client will then see separate mailbox folders: `personal/INBOX`, `work/INBOX`, `work/Sent`, etc.

Without an `accounts` section, Protonesk uses the single account configured during setup.

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
| `main.py` | Entry point: starts IMAP + SMTP, manages reconnection |

</details>
