# Product Requirements Document — Proton Mail Bridge

**Version:** 1.0  
**Status:** Production Ready  
**Generated:** 2026-04-20  
**Author:** BMAD PM Agent (Atlas)

---

## Executive Summary

Proton Mail Bridge is a Python application that provides programmatic access to Proton Mail services for developers and AI agents. It enables secure email integration with full PGP encryption, SRP authentication, and message lifecycle management.

**Primary Use Case:** AI agents and automation tools that need to read, send, and manage Proton Mail messages without exposing credentials or compromising end-to-end encryption.

---

## Problem Statement

### Current Limitations

1. **No Official API Access:** Proton Mail's end-to-end encryption makes traditional IMAP/SMTP access impossible without a local bridge
2. **Credential Security:** Storing Proton credentials for automation violates security best practices
3. **PGP Complexity:** Manual key management and encryption is error-prone for developers
4. **Session Management:** SRP authentication handshake is complex to implement correctly

### Target Users

| User Type | Need |
|-----------|------|
| **AI Agents** | Read/send emails for task automation without credential exposure |
| **Developers** | Integrate Proton Mail into applications with minimal code |
| **Power Users** | Automate email workflows (filtering, forwarding, archiving) |
| **Security Teams** | Audit email flows with secure credential storage |

---

## Product Vision

**"Secure programmatic access to Proton Mail — zero credential exposure, full PGP encryption."**

### Design Principles

1. **Zero Plaintext Credentials:** Never store passwords in code or config files
2. **PGP by Default:** All outgoing messages encrypted automatically
3. **SRP Protocol:** Secure Remote Password authentication (no password transmission)
4. **Human-Like Behavior:** Rate limiting and cooldowns to avoid detection
5. **Clean Abstraction:** Simple API hiding cryptographic complexity

---

## Functional Requirements

### FR-1: Authentication

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1.1 | Support SRP authentication with Proton API | Must Have |
| FR-1.2 | Support 2FA/TOTP codes | Must Have |
| FR-1.3 | Fetch credentials from OS keyring (no plaintext) | Must Have |
| FR-1.4 | Support .env file fallback for development | Should Have |
| FR-1.5 | Session token refresh and validation | Must Have |
| FR-1.6 | Clean logout with session invalidation | Must Have |

### FR-2: Message Reading

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-2.1 | Fetch messages from inbox/folders | Must Have |
| FR-2.2 | Filter by unread status | Must Have |
| FR-2.3 | Fetch full message with encrypted body | Must Have |
| FR-2.4 | PGP decrypt message body | Must Have |
| FR-2.5 | Convert HTML to Markdown for LLM contexts | Must Have |
| FR-2.6 | Batch fetch with pagination | Should Have |

### FR-3: Message Lifecycle

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Mark messages as read | Must Have |
| FR-3.2 | Batch mark as read | Must Have |
| FR-3.3 | Archive messages | Must Have |
| FR-3.4 | Move to trash | Must Have |
| FR-3.5 | Permanent deletion | Must Have |
| FR-3.6 | Auto-detect trash folder ID | Must Have |
| FR-3.7 | Cooldown enforcement between operations | Should Have |

### FR-4: Message Sending

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-4.1 | Lookup recipient public keys via Proton Discovery | Must Have |
| FR-4.2 | Create draft messages | Must Have |
| FR-4.3 | PGP encrypt body with recipient keys | Must Have |
| FR-4.4 | Update draft with encrypted body | Must Have |
| FR-4.5 | Send draft | Must Have |
| FR-4.6 | Support threaded replies (ThreadID) | Should Have |
| FR-4.7 | Atomic rollback on send failure | Must Have |
| FR-4.8 | Rate limiting between sends | Must Have |

### FR-5: Security

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-5.1 | Integrate with OS keyring (Windows Credential Manager, macOS Keychain, libsecret) | Must Have |
| FR-5.2 | Support bcrypt for local password hashing | Should Have |
| FR-5.3 | Encrypt session tokens at rest | Should Have |
| FR-5.4 | No credential logging | Must Have |
| FR-5.5 | Secure memory handling (wipe sensitive data) | Nice to Have |

---

## Non-Functional Requirements

### NFR-1: Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1.1 | Authentication latency | < 3 seconds |
| NFR-1.2 | Message fetch latency | < 2 seconds per message |
| NFR-1.3 | Send flow latency | < 5 seconds end-to-end |
| NFR-1.4 | PGP encryption latency | < 1 second per KB |
| NFR-1.5 | API rate limit handling | Automatic retry with backoff |

### NFR-2: Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-2.1 | Test coverage | 100% of critical paths |
| NFR-2.2 | API error recovery | Exponential backoff, max 3 retries |
| NFR-2.3 | Session resilience | Auto-reconnect on timeout |
| NFR-2.4 | Atomicity | Failed sends cleanup draft |

### NFR-3: Security

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-3.1 | Credential storage | OS keyring only (no plaintext) |
| NFR-3.2 | Password transmission | SRP only (never cleartext) |
| NFR-3.3 | Message encryption | PGP with recipient keys |
| NFR-3.4 | TLS pinning | Required for all API calls |

### NFR-4: Usability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-4.1 | API simplicity | < 10 lines for common operations |
| NFR-4.2 | Error messages | Actionable, user-friendly |
| NFR-4.3 | Documentation | Inline docstrings + examples |

---

## User Stories

### Authentication Flow

**US-1: Secure Login**
> As a developer, I want to authenticate without storing my password in code, so that my credentials remain secure even if my codebase is exposed.

**Acceptance Criteria:**
- Credentials fetched from OS keyring automatically
- SRP handshake completes successfully
- 2FA code accepted if enabled
- Session token cached for reuse
- Logout invalidates session

### Message Reading Flow

**US-2: Read Unread Messages**
> As an AI agent, I want to fetch only unread messages from the inbox, so that I can process new emails efficiently.

**Acceptance Criteria:**
- Filter by LabelID (INBOX) and Unread flag
- Return message metadata (ID, Subject, Sender, Timestamp)
- Fetch full message body on demand
- Decrypt PGP body automatically
- Format as Markdown for LLM consumption

### Message Sending Flow

**US-3: Send Encrypted Email**
> As a user, I want to send an email that is automatically encrypted with the recipient's public key, so that privacy is maintained end-to-end.

**Acceptance Criteria:**
- Recipient keys fetched via Proton Discovery
- Draft created with plaintext body
- Body encrypted with recipient's public key
- Draft updated with encrypted body
- Message sent successfully
- Draft deleted on failure (atomicity)

### Message Management Flow

**US-4: Archive Processed Messages**
> As an automation tool, I want to archive messages after processing, so that my inbox stays organized.

**Acceptance Criteria:**
- Mark message as read
- Move to Archive folder
- Support batch operations
- Respect rate limits between operations

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Authentication Success Rate** | > 99% | Logs over 1000 attempts |
| **Message Send Success Rate** | > 98% | Logs over 500 sends |
| **PGP Encryption Coverage** | 100% | All outgoing messages |
| **Credential Exposure Incidents** | 0 | Security audits |
| **Test Pass Rate** | 100% | CI/CD pipeline |
| **Developer Onboarding Time** | < 15 minutes | Time to first successful send |

---

## Out of Scope (v1.0)

- IMAP/SMTP compatibility layer
- Multi-account management
- Attachment handling (encrypt/decrypt)
- Custom label creation/management
- Conversation threading UI
- Desktop notifications
- Scheduled sending
- Contact management

---

## Dependencies

| Dependency | Purpose | Version |
|------------|---------|---------|
| `proton-python-client` | Official Proton API client | >= 0.1.0 |
| `httpx` | Async HTTP client | >= 0.25.0 |
| `python-gnupg` | GPG encryption | >= 0.5.0 |
| `PGPy` | Pure Python PGP | >= 0.6.0 |
| `bcrypt` | Password hashing | >= 4.0.0 |
| `keyring` | OS credential storage | >= 24.0.0 |
| `python-dotenv` | .env file support | >= 1.0.0 |
| `beautifulsoup4` | HTML parsing | >= 4.12.0 |

---

## Release Criteria

**v1.0 Production Release:**
- [x] All Must Have requirements implemented
- [x] 42/42 tests passing
- [x] Zero critical security vulnerabilities
- [x] Documentation complete (PRD, Architecture, Tech-spec)
- [x] Credential storage verified (OS keyring integration)
- [ ] External security audit (pending)
- [ ] Performance benchmark report (pending)

---

## Appendix: Competitive Analysis

| Feature | Proton Mail Bridge | Proton Mail App | Third-Party IMAP |
|---------|-------------------|-----------------|------------------|
| Programmatic Access | ✅ Full API | ❌ None | ⚠️ Limited |
| PGP Encryption | ✅ Automatic | ✅ Automatic | ❌ None |
| Credential Security | ✅ Keyring | ✅ Keyring | ❌ Plaintext |
| SRP Authentication | ✅ Yes | ✅ Yes | ❌ No |
| AI Agent Friendly | ✅ Designed for | ❌ Manual only | ⚠️ Possible |

---

*Document generated by BMAD PM Agent — 2026-04-20*
