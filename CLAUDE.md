# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Protonesk is a thin Windows wrapper that registers
[hydroxide](https://github.com/emersion/hydroxide) (a third-party Go IMAP/SMTP/CardDAV
bridge for ProtonMail, works with free accounts) as a per-user auto-start
Scheduled Task. There is no Python code in this repo — all mail protocol
handling is done by the `hydroxide` binary.

## Layout

| Path | Role |
|---|---|
| `scripts/install-hydroxide-service-windows.ps1` | Manage the Scheduled Task: `auth`, `install`, `uninstall`, `start`, `stop`, `status` |
| `scripts/hydroxide-runner.ps1` | Restart-loop wrapper around `hydroxide serve`, writes rotating logs |

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
