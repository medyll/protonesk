# Architecture Document — Protonesk

**Version:** 1.0  
**Status:** Production Ready  
**Generated:** 2026-04-20  
**Author:** BMAD Architect Agent (Kai)

---

## System Overview

Protonesk is a modular Python application that provides secure programmatic access to Proton Mail services. The architecture follows a **layered design** with clear separation of concerns.

```
┌─────────────────────────────────────────────────────────────┐
│                      Application Layer                       │
│                    (User Scripts / CLI)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Facade Layer                            │
│              (ProtonAuth, ProtonSend, etc.)                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Service Layer                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │   Auth   │ │  Crypto  │ │ Lifecycle│ │  Send    │        │
│  │ Service  │ │ Service  │ │ Service  │ │ Service  │        │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      API Client Layer                        │
│           (ProtonAPIClient with rate limiting)               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   External Dependencies                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Proton Mail  │  │   OS Keyring │  │   GPG Keys   │       │
│  │     API      │  │   (Secrets)  │  │   (PGP)      │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Architecture

### 1. `auth.py` — Authentication Module

**Purpose:** SRP authentication with Proton API

**Responsibilities:**
- Credential retrieval from OS keyring
- SRP handshake protocol
- Session token management
- 2FA/TOTP support
- Session validation and logout

**Dependencies:**
- `proton-python-client` (ProtonSession)
- `keyring` (credential storage)
- `pyotp` (TOTP generation)

**Key Classes:**
```python
class ProtonAuth:
    def __init__(self, username=None, password=None, totp=None)
    def authenticate(self) -> ProtonSession
    def is_authenticated(self) -> bool
    def logout(self) -> None
```

**Security Model:**
- Passwords never transmitted in cleartext (SRP protocol)
- Credentials stored in OS keyring (Windows Credential Manager, macOS Keychain, libsecret)
- Session tokens held in memory only
- Automatic credential fallback to .env for development

---

### 2. `api_client.py` — API Client Module

**Purpose:** HTTP client wrapper with rate limiting and error handling

**Responsibilities:**
- REST API communication
- Exponential backoff on failures
- Rate limit detection (HTTP 429)
- Request/response logging
- Endpoint abstraction

**Dependencies:**
- `proton-python-client` (ProtonSession)
- `httpx` (async HTTP fallback)

**Key Classes:**
```python
class ProtonAPIClient:
    def __init__(self, session: ProtonSession)
    def _request(method, endpoint, **kwargs) -> dict
    def get_messages(label, unread, limit) -> List[dict]
    def get_message(message_id) -> dict
    def get_labels() -> List[dict]
```

**Rate Limiting Strategy:**
- Base delay: 1 second
- Exponential backoff: `delay = base_delay * (2 ^ attempt)`
- Max retries: 3
- Automatic 429 detection and retry

---

### 3. `crypto.py` — Cryptography Module

**Purpose:** PGP encryption and decryption

**Responsibilities:**
- GPG key management
- Message encryption for recipients
- Message decryption from senders
- Key fingerprint validation

**Dependencies:**
- `python-gnupg` (GPG interface)
- `PGPy` (pure Python PGP fallback)

**Key Classes:**
```python
class ProtonCrypto:
    def __init__(self, key_path, passphrase)
    def decrypt_message(encrypted_body) -> str
    def encrypt_for_recipient(body, recipient_keys) -> str
```

**Encryption Flow:**
1. Fetch recipient public keys via Proton Discovery API
2. Validate key fingerprints
3. Encrypt message body with recipient's public key
4. Replace draft body with PGP block
5. Send encrypted message

---

### 4. `formatter.py` — Content Formatter Module

**Purpose:** Convert HTML email content to Markdown for LLM contexts

**Responsibilities:**
- HTML to Markdown conversion
- Link preservation
- Heading detection (h1-h6)
- List formatting (ordered/unordered)
- Stripping dangerous tags (scripts, styles)

**Dependencies:**
- `beautifulsoup4` (HTML parsing)
- `markdown` (Markdown generation)

**Key Classes:**
```python
class ContextFormatter:
    def __init__(self)
    def html_to_markdown(html) -> str
    def format_message(message) -> dict
    def format_batch(messages) -> List[dict]
```

**Conversion Rules:**
| HTML Tag | Markdown Output |
|----------|-----------------|
| `<h1>` - `<h6>` | `#` - `######` |
| `<p>` | Paragraph with blank line |
| `<strong>` | `**bold**` |
| `<em>` | `*italic*` |
| `<a href>` | `[text](url)` |
| `<ul>/<ol>` | `-` / `1.` lists |
| `<br>` | Double space + newline |
| `<script>` | Stripped |
| `<style>` | Stripped |

---

### 5. `lifecycle.py` — Message Lifecycle Module

**Purpose:** Manage message state (read, archive, delete, trash)

**Responsibilities:**
- Mark messages as read (single/batch)
- Archive messages
- Move to trash folder
- Permanent deletion
- Trash folder detection
- Cooldown enforcement

**Dependencies:**
- `api_client.py` (ProtonAPIClient)

**Key Classes:**
```python
class MessageLifecycle:
    def __init__(self, api_client, session)
    def mark_as_read(message_id) -> bool
    def mark_batch_as_read(message_ids) -> int
    def archive(message_id) -> bool
    def move_to_trash(message_id) -> bool
    def delete_permanently(message_id) -> bool
    def get_trash_label_id() -> str
```

**Cooldown Mechanism:**
- Minimum 2 seconds between operations
- Human-like behavior to avoid detection
- Enforced via `last_operation_time` tracking

---

### 6. `send.py` — Email Sending Module

**Purpose:** Complete email send flow with PGP encryption

**Responsibilities:**
- Recipient key discovery
- Draft creation
- PGP body encryption
- Draft update
- Send draft
- Atomic rollback on failure

**Dependencies:**
- `api_client.py` (ProtonAPIClient)
- `crypto.py` (ProtonCrypto)

**Key Classes:**
```python
class ProtonSend:
    def __init__(self, session, crypto_module)
    def get_recipient_keys(email) -> dict
    def create_draft(subject, sender, recipients, body) -> str
    def encrypt_body(body, recipient_keys) -> str
    def update_draft(message_id, encrypted_body) -> bool
    def send_draft(message_id) -> bool
    def send_email(subject, sender, recipients, body) -> bool
```

**Send Flow (5 Steps):**
```
1. Get Recipient Keys → Proton Discovery API
2. Create Draft → POST /mail/v4/drafts
3. Encrypt Body → PGP with recipient public key
4. Update Draft → PUT /mail/v4/messages/{id}
5. Send Draft → POST /mail/v4/messages/{id}/send
```

**Failure Handling:**
- If any step fails, delete draft (atomicity)
- Log error with full stack trace
- Return False to caller

---

### 7. `secrets.py` — Secrets Management Module

**Purpose:** Secure credential storage and retrieval

**Responsibilities:**
- OS keyring integration
- .env file fallback
- Credential encryption at rest
- Secure credential deletion

**Dependencies:**
- `keyring` (OS credential storage)
- `python-dotenv` (.env parsing)
- `cryptography` (token encryption)

**Key Functions:**
```python
def get_proton_credentials() -> dict
def set_proton_credentials(username, password, totp) -> bool
def delete_proton_credentials() -> bool
def get_session_token() -> str
def set_session_token(token) -> bool
```

**Credential Storage Priority:**
1. OS Keyring (Windows Credential Manager, macOS Keychain, libsecret)
2. .env file (development only, with warning)
3. Environment variables (ephemeral, process-only)

---

## Data Flow Diagrams

### Authentication Flow

```
┌─────────┐     ┌──────────┐     ┌───────────────┐     ┌──────────┐
│  User   │     │ ProtonAuth│     │OS Keyring    │     │Proton API│
│  Script │     │           │     │              │     │          │
└────┬────┘     └────┬─────┘     └───────┬───────┘     └────┬─────┘
     │               │                    │                  │
     │ authenticate()│                    │                  │
     │──────────────>│                    │                  │
     │               │ get_credentials()  │                  │
     │               │───────────────────>│                  │
     │               │                    │                  │
     │               │<───────────────────│ credentials      │
     │               │                    │                  │
     │               │ SRP Handshake      │                  │
     │               │─────────────────────────────────────>│
     │               │                    │                  │
     │               │<─────────────────────────────────────│ session token
     │               │                    │                  │
     │ session       │                    │                  │
     │<──────────────│                    │                  │
     │               │                    │                  │
```

### Message Send Flow

```
┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│  User   │  │ProtonSend│  │Crypto    │  │Proton API│  │  GPG     │
│  Script │  │          │  │Module    │  │          │  │  Keys    │
└────┬────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │            │             │             │              │
     │ send_email()             │             │              │
     │───────────>│             │             │              │
     │            │             │             │              │
     │            │get_keys()   │             │              │
     │            │────────────────────────>│              │
     │            │             │             │              │
     │            │<────────────────────────│ keys         │
     │            │             │             │              │
     │            │create_draft()            │              │
     │            │────────────────────────>│              │
     │            │             │             │              │
     │            │<────────────────────────│ message_id   │
     │            │             │             │              │
     │            │encrypt_body()            │              │
     │            │────────────>│             │              │
     │            │             │fetch keys   │              │
     │            │             │──────────────────────────>│
     │            │             │             │              │
     │            │             │<──────────────────────────│ public key
     │            │             │             │              │
     │            │<────────────│ encrypted    │              │
     │            │             │             │              │
     │            │update_draft(encrypted)    │              │
     │            │────────────────────────>│              │
     │            │             │             │              │
     │            │send_draft() │             │              │
     │            │────────────────────────>│              │
     │            │             │             │              │
     │            │<────────────────────────│ success      │
     │            │             │             │              │
     │<───────────│ success     │             │              │
     │            │             │             │              │
```

---

## Security Architecture

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Credential theft | OS keyring only, no plaintext storage |
| Password interception | SRP protocol (password never transmitted) |
| Session hijacking | Token encryption, HTTPS-only, auto-expiry |
| Man-in-the-middle | TLS pinning, certificate validation |
| Key tampering | Fingerprint validation, Proton Discovery API |
| Memory scraping | Sensitive data wiped after use |

### Credential Storage

```
┌─────────────────────────────────────────────────────────────┐
│                    Credential Hierarchy                      │
├─────────────────────────────────────────────────────────────┤
│  Priority 1: OS Keyring (Production)                        │
│  - Windows: Credential Manager                              │
│  - macOS: Keychain                                          │
│  - Linux: libsecret / GNOME Keyring                         │
│  - Encrypted at rest by OS                                  │
├─────────────────────────────────────────────────────────────┤
│  Priority 2: .env File (Development Only)                   │
│  - Plaintext warning in code                                │
│  - .gitignore enforced                                      │
│  - Never committed to version control                       │
├─────────────────────────────────────────────────────────────┤
│  Priority 3: Environment Variables (Ephemeral)              │
│  - Process-only lifetime                                    │
│  - Cleared on process exit                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing Architecture

### Test Pyramid

```
                    ┌─────────┐
                    │  E2E    │  ← 5 tests (full send flow)
                   ─┼─────────┼─
                  ─│Integration│─ ← 15 tests (module interactions)
                 ──┼─────────┼──
                ──│   Unit   │─── ← 22 tests (individual functions)
               ───┼─────────┼────
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| `auth.py` | 6 | Init, authenticate, logout, 2FA |
| `formatter.py` | 13 | HTML conversion, edge cases |
| `lifecycle.py` | 11 | Read, archive, delete, trash |
| `send.py` | 12 | Draft, encrypt, send, rollback |
| **Total** | **42** | **100% critical paths** |

---

## Deployment Architecture

### Runtime Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.9+ |
| OS | Windows 10+, macOS 10.15+, Linux (glibc 2.17+) |
| Memory | 50MB minimum |
| Disk | 10MB for installation |
| Network | HTTPS access to mail.proton.me |

### Dependency Graph

```
proton-mail-bridge
├── proton-python-client (SRP auth)
├── httpx (async HTTP)
├── requests (fallback HTTP)
├── python-gnupg (GPG encryption)
├── PGPy (pure Python PGP)
├── bcrypt (password hashing)
├── pyopenssl (TLS/SSL)
├── cryptography (token encryption)
├── pyotp (TOTP 2FA)
├── python-dotenv (.env support)
├── keyring (OS credential storage)
└── beautifulsoup4 (HTML parsing)
```

---

## Extension Points

### Adding New Features

1. **New API Endpoint:**
   - Add method to `api_client.py`
   - Follow `_request()` pattern with error handling
   - Add rate limiting if write operation

2. **New Authentication Provider:**
   - Extend `ProtonAuth` class
   - Implement SRP handshake variant
   - Update credential retrieval logic

3. **New Encryption Scheme:**
   - Extend `ProtonCrypto` class
   - Implement `encrypt_for_recipient()` variant
   - Update key management

4. **New Message Operation:**
   - Add to `MessageLifecycle` class
   - Enforce cooldown if write operation
   - Add test coverage

---

*Document generated by BMAD Architect Agent — 2026-04-20*
