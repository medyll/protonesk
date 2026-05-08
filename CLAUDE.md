# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest tests/

# Run single test file
pytest tests/test_auth.py

# Run single test
pytest tests/test_auth.py::test_function_name

# Lint
flake8 src/ tests/

# Format
black src/ tests/

# One-shot credential setup (interactive, AI-invisible)
python src/secrets.py setup

# Run individual modules as CLI scripts
python src/auth.py
python src/api_client.py
```

## Architecture

Python bridge for Proton Mail's REST API, designed for LLM/AI agent consumption. All credentials are hidden from AI via OS keyring.

### `src/` — Core modules

| Module | Role |
|---|---|
| `auth.py` — `ProtonAuth` | SRP handshake via `proton-python-client`. Loads credentials from OS keyring (via `C:/Users/Mydde/.openclaw/workspace/secrets/manager.py`, invisible to AI). Returns authenticated `ProtonSession`. |
| `api_client.py` — `ProtonAPIClient` | Wraps Proton REST API (`https://mail.proton.me/api/mail/v4/`). Takes a `ProtonSession`. Handles rate-limiting with exponential backoff (3 retries). |
| `send.py` — `ProtonSend` | Full send flow: key lookup → draft creation → PGP encrypt → update draft → send. Enforces 2s cooldown between sends. On failure, deletes the draft atomically. |
| `lifecycle.py` — `MessageLifecycle` | Message state transitions (mark read, archive, move to trash, permanent delete). 1s cooldown on all write ops. Soft-delete preferred (`move_to_trash`) over permanent delete. |
| `crypto.py` — `ProtonCrypto` | Local GPG decryption via `python-gnupg`. Decrypted content never written to disk. Also handles `encrypt_for_recipient()` for outbound PGP. |
| `formatter.py` — `ContextFormatter` | Converts decrypted messages to LLM-ready format. HTML → Markdown, produces structured dicts and prompt strings. |
| `secrets.py` — `SecretManager` | Credential storage: OS keyring (primary), Fernet-encrypted file (fallback). Interactive `getpass` prompts hide values from AI. |

### Data flow

```
ProtonAuth → ProtonSession
                  ↓
           ProtonAPIClient   (read: list/fetch messages)
                  ↓
           ProtonCrypto      (decrypt PGP body in-memory)
                  ↓
           ContextFormatter  (HTML→Markdown, LLM prompt)

           ProtonSend        (write: draft→encrypt→send)
           MessageLifecycle  (write: read/archive/delete)
```

### Credential security model

Credentials flow: `secrets.py setup` → OS keyring → `SecretManager.get_secret()` → `ProtonAuth.__init__()`. The keyring path (`C:/Users/Mydde/.openclaw/workspace/secrets/manager.py`) is outside this repo and cannot be read by AI. Never put credentials in `.env` — the `.env.example` explicitly deprecates that pattern.

### Tests

`tests/conftest.py` mocks the `proton` module entirely so tests run without `proton-python-client` installed. All tests use `MagicMock` for `ProtonSession`.

### Key constraints

- Write operations (send, lifecycle mutations) enforce explicit cooldowns to avoid triggering Proton's rate limiter or abuse detection.
- `ProtonAPIClient._request()` and `ProtonSend._request()` are separate — `send.py` has no retry logic; `api_client.py` has 3-retry backoff.
- `delete_permanently` is a one-way destructive operation; prefer `move_to_trash` in most flows.
