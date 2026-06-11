# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Protonesk has two parts:

1. A thin Windows wrapper that registers
   [hydroxide](https://github.com/emersion/hydroxide) (a third-party Go IMAP/SMTP/CardDAV
   bridge for ProtonMail, works with free accounts) as a per-user auto-start
   Scheduled Task. All mail protocol handling (auth, IMAP, SMTP) is done by
   the `hydroxide` binary.
2. A Node/TypeScript **MCP server** (`src/`) that connects to hydroxide's
   local IMAP/SMTP bridge and exposes mail operations (list/search/read/send,
   flags, move, delete) as MCP tools for LLM agents.

The two parts are independent processes: hydroxide must be running and
authenticated for the MCP server to work, but the MCP server is not managed
by the Scheduled Task.

## Layout

| Path | Role |
|---|---|
| `scripts/install-hydroxide-service-windows.ps1` | Manage the Scheduled Task: `auth`, `install`, `uninstall`, `start`, `stop`, `status` |
| `scripts/hydroxide-runner.ps1` | Restart-loop wrapper around `hydroxide serve`, writes rotating logs |
| `src/index.ts` | MCP server entry point (stdio transport) |
| `src/config.ts` | Env config for connecting to hydroxide's local IMAP/SMTP |
| `src/mail/imap.ts` | ImapFlow helpers: list folders/messages, search, flags, move, delete |
| `src/mail/smtp.ts` | nodemailer wrapper for sending mail |
| `src/tools.ts` | MCP tool registrations (`list_folders`, `list_messages`, `get_message`, `search_messages`, `send_message`, `mark_message`, `move_message`, `delete_message`) |

## MCP server

- Config via `.env` (copy from `.env.example`): `HYDROXIDE_HOST`,
  `HYDROXIDE_IMAP_PORT` (1143), `HYDROXIDE_SMTP_PORT` (1025), `HYDROXIDE_USER`,
  `HYDROXIDE_PASSWORD` (the bridge password printed by `hydroxide auth`, not
  the Proton account password).
- Build: `npm install && npm run build`. Run: `npm start` (`node dist/index.js`).
- Connects with `tls.rejectUnauthorized: false` since hydroxide uses a
  self-signed local cert.
- POP3 and CardDAV/contacts are out of scope — hydroxide doesn't support POP3,
  and only IMAP/SMTP are wired up so far.

## Key facts

- hydroxide config/session: `%APPDATA%\hydroxide\auth.json`
- Logs: `%LOCALAPPDATA%\Hydroxide\logs\hydroxide.log`
- hydroxide binary: built via `go install github.com/emersion/hydroxide/cmd/hydroxide@latest`, lands in `%USERPROFILE%\go\bin\hydroxide.exe`
- `hydroxide auth <email>` is interactive (password + 2FA prompt) — cannot run unattended/from a service
- Scheduled Task runs at logon under the current user (per-user `%APPDATA%`, no admin needed)

## Previous approach (removed)

An earlier version of this repo recoded the *official* Proton Mail Bridge
REST API in Python (SRP auth, PGP, IMAP/SMTP servers, MCP server for LLM
agents). That approach requires a paid Proton plan and was scrapped in favor
of wrapping hydroxide, which works with free accounts and needs no custom
protocol code.

## bmad/

The `bmad/` directory documents the old (removed) Python implementation and
is stale — do not use it as a source of truth for current architecture.
