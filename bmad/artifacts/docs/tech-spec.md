# Technical Specification — Protonesk

**Version:** 1.0  
**Status:** Production Ready  
**Generated:** 2026-04-20  
**Author:** BMAD Architect Agent (Kai)

---

## 1. Introduction

### 1.1 Purpose

This document provides the technical specification for Protonesk, a Python application enabling secure programmatic access to Proton Mail services.

### 1.2 Scope

This specification covers:
- API contracts for all modules
- Data structures and types
- Error handling strategies
- Security implementations
- Performance requirements
- Testing requirements

### 1.3 Audience

- **Developers:** Implementation reference
- **Reviewers:** Code audit checklist
- **Security Auditors:** Security control verification
- **Maintainers:** Troubleshooting guide

---

## 2. System Interfaces

### 2.1 Proton Mail API

**Base URL:** `https://mail.proton.me/api`

**Authentication:** SRP Protocol via `proton-python-client`

**Rate Limits:**
- Read operations: 100 requests/minute
- Write operations: 20 requests/minute
- Send operations: 5 messages/minute (human-like)

**Key Endpoints:**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/mail/v4/messages` | GET | Fetch message list |
| `/mail/v4/messages/{id}` | GET | Fetch single message |
| `/mail/v4/messages/{id}` | PUT | Update message |
| `/mail/v4/messages/{id}/send` | POST | Send message |
| `/mail/v4/messages/{id}` | DELETE | Delete message |
| `/mail/v4/drafts` | POST | Create draft |
| `/mail/v4/labels` | GET | Fetch folders/labels |
| `/mail/v4/keys/{email}` | GET | Recipient key discovery |

### 2.2 OS Keyring Interface

**Library:** `keyring` >= 24.0.0

**Service Name:** `proton-mail-bridge`

**Credential Keys:**
- `proton-username`
- `proton-password`
- `proton-totp` (optional)
- `proton-session-token` (ephemeral)

**API:**
```python
import keyring

# Store credential
keyring.set_password("proton-mail-bridge", "proton-username", "user@proton.me")

# Retrieve credential
username = keyring.get_password("proton-mail-bridge", "proton-username")

# Delete credential
keyring.delete_password("proton-mail-bridge", "proton-username")
```

### 2.3 GPG Interface

**Primary Library:** `python-gnupg` >= 0.5.0  
**Fallback:** `PGPy` >= 0.6.0

**GPG Home Directory:** `~/.gnupg` (default) or custom path

**Key Requirements:**
- RSA 2048-bit minimum
- SHA-256 hash algorithm
- AES-256 symmetric encryption

---

## 3. Module Specifications

### 3.1 Authentication Module (`auth.py`)

#### 3.1.1 Class: `ProtonAuth`

**Constructor:**
```python
def __init__(
    self,
    username: Optional[str] = None,
    password: Optional[str] = None,
    totp: Optional[str] = None
)
```

**Parameters:**
| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| `username` | str | No | None | Proton username (fetches from keyring if None) |
| `password` | str | No | None | Proton password (fetches from keyring if None) |
| `totp` | str | No | None | TOTP 2FA secret (optional) |

**Raises:**
- `ValueError`: If credentials not found after all retrieval attempts

**Methods:**

**`authenticate() -> ProtonSession`**
```python
def authenticate(self) -> ProtonSession:
    """
    Perform SRP handshake.
    
    Returns:
        ProtonSession: Authenticated session
        
    Raises:
        ValueError: If authentication fails
    """
```

**`is_authenticated() -> bool`**
```python
def is_authenticated(self) -> bool:
    """
    Check if session is valid.
    
    Returns:
        bool: True if authenticated
    """
```

**`logout() -> None`**
```python
def logout(self) -> None:
    """
    Invalidate session and clear tokens.
    """
```

#### 3.1.2 Authentication Flow

```
1. Check if username/password provided
   ├─ Yes → Use provided credentials
   └─ No → Fetch from keyring
       ├─ Success → Use keyring credentials
       └─ Failure → Raise ValueError

2. Initialize ProtonSession

3. Perform SRP handshake
   ├─ Send SRP start request
   ├─ Receive challenge
   ├─ Compute SRP response
   ├─ Send SRP verify
   └─ Receive session token

4. If TOTP enabled:
   └─ Send 2FA code

5. Return authenticated session
```

---

### 3.2 API Client Module (`api_client.py`)

#### 3.2.1 Class: `ProtonAPIClient`

**Constructor:**
```python
def __init__(
    self,
    session: ProtonSession,
    max_retries: int = 3,
    base_delay: float = 1.0
)
```

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `session` | ProtonSession | Required | Authenticated Proton session |
| `max_retries` | int | 3 | Maximum retry attempts |
| `base_delay` | float | 1.0 | Base backoff delay (seconds) |

**Methods:**

**`_request(method, endpoint, **kwargs) -> dict`**
```python
def _request(
    self,
    method: str,
    endpoint: str,
    **kwargs
) -> dict:
    """
    Make API request with exponential backoff.
    
    Parameters:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint (e.g., '/mail/v4/messages')
        **kwargs: Additional request parameters
        
    Returns:
        dict: API response JSON
        
    Raises:
        Exception: If request fails after retries
    """
```

**Retry Logic:**
```python
for attempt in range(max_retries):
    try:
        response = session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except HTTP 429:
        delay = base_delay * (2 ** attempt)
        sleep(delay)
        continue
    except Exception:
        if attempt < max_retries - 1:
            delay = base_delay * (2 ** attempt)
            sleep(delay)
        else:
            raise
```

**`get_messages(label, unread, limit) -> List[dict]`**
```python
def get_messages(
    self,
    label: str = "INBOX",
    unread: bool = False,
    limit: int = 10
) -> List[dict]:
    """
    Fetch messages from mailbox.
    
    Parameters:
        label: Folder/label ID (default: INBOX)
        unread: Filter for unread only
        limit: Maximum messages to fetch
        
    Returns:
        List[dict]: Message metadata list
    """
```

**Query Parameters:**
```python
params = {
    "LabelID": label,
    "Limit": limit,
    "Unread": 1 if unread else 0
}
```

**`get_message(message_id) -> dict`**
```python
def get_message(self, message_id: str) -> dict:
    """
    Fetch full message body.
    
    Parameters:
        message_id: Proton message ID
        
    Returns:
        dict: Message with encrypted body
    """
```

**`get_labels() -> List[dict]`**
```python
def get_labels(self) -> List[dict]:
    """
    Fetch all folders/labels.
    
    Returns:
        List[dict]: Label metadata list
    """
```

---

### 3.3 Cryptography Module (`crypto.py`)

#### 3.3.1 Class: `ProtonCrypto`

**Constructor:**
```python
def __init__(
    self,
    key_path: str,
    passphrase: str,
    gpg_home: Optional[str] = None
)
```

**Parameters:**
| Name | Type | Required | Description |
|------|------|----------|-------------|
| `key_path` | str | Yes | Path to private key file |
| `passphrase` | str | Yes | Key passphrase |
| `gpg_home` | str | No | GPG home directory (optional) |

**Methods:**

**`decrypt_message(encrypted_body) -> str`**
```python
def decrypt_message(self, encrypted_body: str) -> str:
    """
    Decrypt PGP message body.
    
    Parameters:
        encrypted_body: PGP encrypted block
        
    Returns:
        str: Decrypted plaintext
        
    Raises:
        ValueError: If decryption fails
    """
```

**`encrypt_for_recipient(body, recipient_keys) -> str`**
```python
def encrypt_for_recipient(
    self,
    body: str,
    recipient_keys: List[dict]
) -> str:
    """
    Encrypt message with recipient's public key.
    
    Parameters:
        body: Plaintext message body
        recipient_keys: List of recipient key objects
        
    Returns:
        str: PGP encrypted block
        
    Raises:
        ValueError: If no valid keys provided
    """
```

#### 3.3.2 Encryption Process

```
1. Validate recipient keys
   ├─ Check key existence
   ├─ Verify key algorithm (RSA/ECDSA)
   └─ Check key expiration

2. Import public key into GPG keyring

3. Encrypt message
   ├─ Use AES-256 symmetric encryption
   ├─ Encrypt symmetric key with recipient's public key
   └─ Combine into PGP block

4. Return encrypted block
```

**PGP Block Format:**
```
-----BEGIN PGP MESSAGE-----
Version: OpenPGP.js v4.10.10
Comment: https://openpgpjs.org

wx4EBAMI... (encrypted content)
...
=abcd
-----END PGP MESSAGE-----
```

---

### 3.4 Formatter Module (`formatter.py`)

#### 3.4.1 Class: `ContextFormatter`

**Constructor:**
```python
def __init__(self)
```

**Methods:**

**`html_to_markdown(html) -> str`**
```python
def html_to_markdown(self, html: str) -> str:
    """
    Convert HTML to Markdown.
    
    Parameters:
        html: HTML string
        
    Returns:
        str: Markdown string
    """
```

**Conversion Rules:**

| HTML | Markdown | Notes |
|------|----------|-------|
| `<h1>` | `# Heading` | Preserve hierarchy |
| `<h2>` | `## Heading` | |
| `<p>` | Paragraph | Blank line between |
| `<strong>` | `**bold**` | |
| `<em>` | `*italic*` | |
| `<a href="url">` | `[text](url)` | Preserve links |
| `<ul><li>` | `- item` | Unordered list |
| `<ol><li>` | `1. item` | Ordered list |
| `<br>` | `  \n` | Double space + newline |
| `<blockquote>` | `> quote` | |
| `<code>` | `` `code` `` | Inline code |
| `<pre>` | ` ``` ` | Code block |
| `<script>` | *(stripped)* | Security |
| `<style>` | *(stripped)* | Security |

**`format_message(message) -> dict`**
```python
def format_message(self, message: dict) -> dict:
    """
    Format message for LLM context.
    
    Parameters:
        message: Proton message dict
        
    Returns:
        dict: Formatted message with Markdown body
    """
```

**Output Format:**
```python
{
    "id": "message_id",
    "subject": "Email Subject",
    "sender": "sender@proton.me",
    "timestamp": "2026-04-20T10:30:00Z",
    "body": "# Heading\n\nMarkdown content...",
    "labels": ["INBOX", "UNREAD"]
}
```

**`format_batch(messages) -> List[dict]`**
```python
def format_batch(self, messages: List[dict]) -> List[dict]:
    """
    Format multiple messages.
    
    Parameters:
        messages: List of message dicts
        
    Returns:
        List[dict]: Formatted message list
    """
```

---

### 3.5 Lifecycle Module (`lifecycle.py`)

#### 3.5.1 Class: `MessageLifecycle`

**Constructor:**
```python
def __init__(
    self,
    api_client: ProtonAPIClient,
    session: ProtonSession,
    cooldown_ms: int = 2000
)
```

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `api_client` | ProtonAPIClient | Required | API client instance |
| `session` | ProtonSession | Required | Authenticated session |
| `cooldown_ms` | int | 2000 | Cooldown between operations |

**Methods:**

**`mark_as_read(message_id) -> bool`**
```python
def mark_as_read(self, message_id: str) -> bool:
    """
    Mark message as read.
    
    Parameters:
        message_id: Proton message ID
        
    Returns:
        bool: True if successful
    """
```

**Request:**
```python
PUT /mail/v4/messages/{message_id}
{
    "Message": {
        "ID": message_id,
        "Read": 1
    }
}
```

**`mark_batch_as_read(message_ids) -> int`**
```python
def mark_batch_as_read(self, message_ids: List[str]) -> int:
    """
    Mark multiple messages as read.
    
    Parameters:
        message_ids: List of message IDs
        
    Returns:
        int: Number of messages marked
    """
```

**`get_trash_label_id() -> str`**
```python
def get_trash_label_id(self) -> str:
    """
    Get Trash folder ID.
    
    Returns:
        str: Trash LabelID
        
    Raises:
        ValueError: If Trash folder not found
    """
```

**Algorithm:**
```python
labels = api_client.get_labels()
trash = next((l for l in labels if l['Name'] == 'Trash'), None)
if not trash:
    raise ValueError("Trash folder not found")
return trash['ID']
```

**`move_to_trash(message_id) -> bool`**
```python
def move_to_trash(self, message_id: str) -> bool:
    """
    Move message to Trash.
    
    Parameters:
        message_id: Proton message ID
        
    Returns:
        bool: True if successful
    """
```

**Request:**
```python
PUT /mail/v4/messages/{message_id}
{
    "Message": {
        "ID": message_id,
        "LabelIDs": ["trash_label_id"]
    }
}
```

**`delete_permanently(message_id) -> bool`**
```python
def delete_permanently(self, message_id: str) -> bool:
    """
    Permanently delete message.
    
    Parameters:
        message_id: Proton message ID
        
    Returns:
        bool: True if successful
    """
```

**Request:**
```python
DELETE /mail/v4/messages/{message_id}
```

**`archive(message_id) -> bool`**
```python
def archive(self, message_id: str) -> bool:
    """
    Archive message (remove from INBOX).
    
    Parameters:
        message_id: Proton message ID
        
    Returns:
        bool: True if successful
    """
```

**Request:**
```python
PUT /mail/v4/messages/{message_id}
{
    "Message": {
        "ID": message_id,
        "LabelIDs": []  # Remove all labels (archives)
    }
}
```

---

### 3.6 Send Module (`send.py`)

#### 3.6.1 Class: `ProtonSend`

**Constructor:**
```python
def __init__(
    self,
    session: ProtonSession,
    crypto_module: ProtonCrypto,
    cooldown_ms: int = 2000
)
```

**Methods:**

**`get_recipient_keys(email) -> dict`**
```python
def get_recipient_keys(self, email: str) -> dict:
    """
    Get recipient's public keys via Proton Discovery.
    
    Parameters:
        email: Recipient email address
        
    Returns:
        dict: Key information or empty dict if not found
    """
```

**Request:**
```python
GET /mail/v4/keys/{email}
```

**Response:**
```json
{
    "Keys": [
        {
            "PublicKey": "-----BEGIN PGP PUBLIC KEY BLOCK-----...",
            "Fingerprint": "ABC123...",
            "Algorithm": "rsa_encrypt_sign"
        }
    ]
}
```

**`create_draft(subject, sender, recipients, body, thread_id) -> str`**
```python
def create_draft(
    self,
    subject: str,
    sender: str,
    recipients: List[str],
    body: str,
    thread_id: Optional[str] = None
) -> str:
    """
    Create draft message.
    
    Parameters:
        subject: Email subject
        sender: Sender email address
        recipients: List of recipient emails
        body: Plaintext body
        thread_id: ThreadID for replies (optional)
        
    Returns:
        str: MessageID of created draft
        
    Raises:
        ValueError: If draft creation fails
    """
```

**Request:**
```python
POST /mail/v4/drafts
{
    "Message": {
        "Subject": subject,
        "Sender": {"Address": sender},
        "ToList": [{"Address": r} for r in recipients],
        "Body": body,
        "MIMEType": "text/html",
        "ThreadID": thread_id  # optional
    }
}
```

**`encrypt_body(body, recipient_keys) -> str`**
```python
def encrypt_body(
    self,
    body: str,
    recipient_keys: List[dict]
) -> str:
    """
    Encrypt message body.
    
    Parameters:
        body: Plaintext body
        recipient_keys: List of recipient public keys
        
    Returns:
        str: PGP encrypted block
    """
```

**`update_draft(message_id, encrypted_body) -> bool`**
```python
def update_draft(
    self,
    message_id: str,
    encrypted_body: str
) -> bool:
    """
    Update draft with encrypted body.
    
    Parameters:
        message_id: Draft MessageID
        encrypted_body: PGP encrypted body
        
    Returns:
        bool: True if successful
    """
```

**Request:**
```python
PUT /mail/v4/messages/{message_id}
{
    "Message": {
        "ID": message_id,
        "Body": encrypted_body,
        "MIMEType": "text/html"
    }
}
```

**`send_draft(message_id) -> bool`**
```python
def send_draft(self, message_id: str) -> bool:
    """
    Send the draft.
    
    Parameters:
        message_id: Draft MessageID
        
    Returns:
        bool: True if successful
    """
```

**Request:**
```python
POST /mail/v4/messages/{message_id}/send
```

**`send_email(subject, sender, recipients, body, thread_id) -> bool`**
```python
def send_email(
    self,
    subject: str,
    sender: str,
    recipients: List[str],
    body: str,
    thread_id: Optional[str] = None
) -> bool:
    """
    Complete send flow.
    
    Parameters:
        subject: Email subject
        sender: Sender email address
        recipients: List of recipient emails
        body: Plaintext body
        thread_id: ThreadID for replies (optional)
        
    Returns:
        bool: True if send successful
    """
```

**Flow:**
```
1. Enforce cooldown
2. Get recipient keys (all recipients)
3. Create draft → get MessageID
4. Encrypt body with recipient keys
5. Update draft with encrypted body
6. Send draft
7. On failure: DELETE draft (atomicity)
8. Return success/failure
```

---

## 4. Error Handling

### 4.1 Error Codes

| Error | Code | Handling |
|-------|------|----------|
| Authentication Failed | `AUTH_001` | Retry with fresh credentials |
| Session Expired | `AUTH_002` | Re-authenticate |
| Rate Limited | `API_429` | Exponential backoff |
| Not Found | `API_404` | Log and skip |
| Server Error | `API_500` | Retry up to 3 times |
| PGP Decryption Failed | `CRYPTO_001` | Log error, return raw HTML |
| Key Not Found | `CRYPTO_002` | Send unencrypted (warn user) |
| Credential Not Found | `SECRET_001` | Prompt user to setup |

### 4.2 Exception Hierarchy

```python
class ProtonBridgeError(Exception):
    """Base exception"""
    pass

class AuthenticationError(ProtonBridgeError):
    """SRP authentication failed"""
    pass

class APIError(ProtonBridgeError):
    """API request failed"""
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message

class CryptoError(ProtonBridgeError):
    """PGP encryption/decryption failed"""
    pass

class SecretError(ProtonBridgeError):
    """Credential retrieval failed"""
    pass
```

---

## 5. Security Requirements

### 5.1 Credential Storage

**Requirement:** Credentials MUST be stored in OS keyring

**Implementation:**
```python
import keyring

SERVICE = "proton-mail-bridge"

def store_credentials(username, password, totp=None):
    keyring.set_password(SERVICE, "username", username)
    keyring.set_password(SERVICE, "password", password)
    if totp:
        keyring.set_password(SERVICE, "totp", totp)

def retrieve_credentials():
    username = keyring.get_password(SERVICE, "username")
    password = keyring.get_password(SERVICE, "password")
    totp = keyring.get_password(SERVICE, "totp")
    return {
        "username": username,
        "password": password,
        "totp": totp
    }
```

### 5.2 Session Token Handling

**Requirement:** Session tokens MUST NOT be persisted to disk

**Implementation:**
```python
class ProtonAuth:
    def __init__(self):
        self._session_token = None  # Memory only
    
    def logout(self):
        self._session_token = None  # Explicit wipe
        self.session.logout()
```

### 5.3 TLS Configuration

**Requirement:** All API calls MUST use TLS 1.3 with certificate pinning

**Implementation:**
```python
import httpx

client = httpx.Client(
    verify=True,  # Certificate validation
    http2=True,   # HTTP/2 support
    timeout=30.0
)
```

---

## 6. Performance Requirements

### 6.1 Latency Targets

| Operation | Target | P95 | P99 |
|-----------|--------|-----|-----|
| Authentication | < 3s | 4s | 5s |
| Fetch Messages | < 2s | 3s | 4s |
| Send Email | < 5s | 7s | 10s |
| PGP Encrypt (1KB) | < 1s | 1.5s | 2s |
| PGP Decrypt (1KB) | < 1s | 1.5s | 2s |

### 6.2 Throughput Targets

| Operation | Target | Max |
|-----------|--------|-----|
| Messages/sec (read) | 10 | 20 |
| Emails/sec (send) | 1 | 3 (rate limited) |
| API calls/sec | 5 | 10 |

---

## 7. Testing Requirements

### 7.1 Test Coverage

**Requirement:** 100% coverage of critical paths

**Critical Paths:**
1. Authentication (success/failure)
2. Message fetch (empty/non-empty)
3. Message send (success/failure/rollback)
4. PGP encrypt/decrypt
5. Lifecycle operations (read/archive/delete)

### 7.2 Test Types

| Type | Coverage | Tool |
|------|----------|------|
| Unit Tests | All functions | pytest |
| Integration Tests | Module interactions | pytest + mocks |
| E2E Tests | Full send/receive flows | pytest + real API |

### 7.3 Test Execution

**Command:**
```bash
pytest tests/ -v --cov=src --cov-report=html
```

**Requirements:**
- All 42 tests must pass
- Coverage >= 90%
- No warnings or errors

---

## 8. Deployment

### 8.1 Installation

**Requirements:**
```bash
pip install -r requirements.txt
```

**Setup:**
```bash
# Store credentials in OS keyring
python src/secrets.py setup

# Verify installation
python -c "from auth import ProtonAuth; print('OK')"
```

### 8.2 Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `PROTON_USERNAME` | Fallback username | No |
| `PROTON_PASSWORD` | Fallback password | No |
| `PROTON_TOTP` | 2FA secret | No |
| `GPG_HOME` | Custom GPG directory | No |

---

*Document generated by BMAD Architect Agent — 2026-04-20*
