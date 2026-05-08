# Protonesk

Expose Proton Mail via IMAP/SMTP locaux — tout client mail ou agent AI s'y connecte comme à n'importe quel serveur mail.

```
Thunderbird / Claude / n8n
        ↓ IMAP:1143        ↓ SMTP:1025
   IMAPServer           SMTPServer
   (asyncio)            (aiosmtpd)
        ↓                    ↓
   ProtonAPIClient      ProtonSend
   + ProtonCrypto       + ProtonCrypto
        ↓                    ↓
            Proton REST API
```

## Installation

```bash
pip install -r requirements.txt
pip install git+https://github.com/ProtonMail/proton-python-client.git
```

## Configuration credentials (une seule fois)

```bash
python src/secrets.py setup
```

Stockage dans OS keyring — jamais visible par l'AI.

## Démarrage

```bash
# IMAP + SMTP (plaintext local)
python main.py

# Avec TLS (cert auto-signé généré dans ~/.proton-bridge/certs/)
python main.py --tls

# IMAP seulement
python main.py --imap-only

# Ports custom
python main.py --imap-port 2143 --smtp-port 2025
```

## Configuration (optionnelle)

Créer `config.yaml` à la racine — les args CLI surchargent :

```yaml
imap_port: 1143
smtp_port: 1025
imap_host: 127.0.0.1
smtp_host: 127.0.0.1
local_password: bridge
tls: false
log_level: INFO
```

**Multi-compte :**
```yaml
accounts:
  - username: perso@proton.me
    label: perso
  - username: pro@proton.me
    label: pro
```

Sans clé `accounts` → mode mono-compte (comportement par défaut).

## Connexion client

**Thunderbird / tout client IMAP :**
- Serveur : `127.0.0.1`
- Port IMAP : `1143` (ou `1993` avec TLS)
- Port SMTP : `1025`
- Login : n'importe quel username
- Mot de passe : `bridge` (ou `local_password` dans config.yaml)

**Agent AI / script Python :**
```python
import imaplib
mail = imaplib.IMAP4("127.0.0.1", 1143)
mail.login("user", "bridge")
mail.select("INBOX")          # mono-compte
mail.select("perso/INBOX")   # multi-compte
```

## Architecture

| Module | Rôle |
|--------|------|
| `src/auth.py` | SRP handshake Proton via `proton-python-client` |
| `src/api_client.py` | Wrapper REST API Proton (rate limit, retry x3) |
| `src/crypto.py` | Déchiffrement PGP local via GPG (in-memory) |
| `src/send.py` | Flow envoi : draft → chiffrement → send |
| `src/lifecycle.py` | États message : lu, archivé, corbeille, suppression |
| `src/formatter.py` | HTML → Markdown pour contexte LLM |
| `src/secrets.py` | Credentials dans OS keyring (invisible à l'AI) |
| `src/imap_server.py` | Serveur IMAP asyncio (RFC 3501 + IDLE) |
| `src/imap_bridge.py` | Glue IMAP ↔ Proton API (mapping dossiers, cache, fetch+decrypt) |
| `src/smtp_server.py` | Serveur SMTP aiosmtpd → ProtonSend |
| `src/session_manager.py` | Pool de sessions Proton (multi-compte, reconnexion indépendante) |
| `src/multi_account_bridge.py` | Bridge IMAP multi-compte avec namespace `label/mailbox` |
| `src/multi_account_smtp.py` | Handler SMTP multi-compte — routing par `From:` address |
| `src/event_loop.py` | Long-poll `/core/v4/events` — fan-out push vers sessions IDLE via `asyncio.Queue` |
| `src/tls.py` | Cert RSA 2048 auto-signé (SAN localhost, icacls Windows) |
| `src/config.py` | Merge config.yaml + CLI args + validation multi-compte |
| `src/tray.py` | Icône system tray Windows (pystray, `--tray`) |
| `main.py` | Daemon : démarre IMAP+SMTP, reconnexion auto, mono et multi-compte |

## Tests

```bash
pytest tests/        # 221 tests
pytest tests/test_auth.py   # module spécifique
```

## Sécurité

- Credentials stockés dans OS keyring — jamais en clair, jamais dans `.env`
- KDF scrypt (salté, n=2¹⁴) pour chiffrement fichier de secours
- Clé TLS privée : `chmod 0o600` Linux / `icacls` Windows
- Comparaison password via `hmac.compare_digest` (résistant timing attack)
- Déchiffrement PGP in-memory (pas de fichier temp)
- Serveurs écoutent sur `127.0.0.1` uniquement (pas exposés réseau)
- TLS avec cert auto-signé (SAN localhost + 127.0.0.1), renouvelé auto si < 7 jours

