#!/usr/bin/env python3
"""
Proton Mail Bridge — TLS Certificate Management

Auto-generates a self-signed certificate for local IMAP/SMTP TLS.
Cert stored in ~/.proton-bridge/certs/ — never transmitted.
"""

import os
import ssl
import datetime
import ipaddress
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CERT_DIR = Path.home() / ".proton-bridge" / "certs"
CERT_FILE = CERT_DIR / "server.crt"
KEY_FILE = CERT_DIR / "server.key"
CERT_VALIDITY_DAYS = 365


def _generate_cert():
    """Generate self-signed RSA 2048 cert with SAN for localhost."""
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "proton-bridge-local"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Proton Bridge"),
        ]
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=CERT_VALIDITY_DAYS))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    CERT_DIR.mkdir(parents=True, exist_ok=True)

    with open(CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(KEY_FILE, "wb") as f:
        f.write(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )

    # Restrict key file permissions
    if os.name == "nt":
        import subprocess

        subprocess.run(
            ["icacls", str(KEY_FILE), "/inheritance:r", "/grant:r", f"{os.environ['USERNAME']}:R"],
            check=False,
            capture_output=True,
        )
    else:
        os.chmod(KEY_FILE, 0o600)
    logger.info(f"🔐 TLS cert generated: {CERT_FILE}")


def _is_cert_expired() -> bool:
    """Check if existing cert is expired or expiring within 7 days."""
    if not CERT_FILE.exists():
        return True
    try:
        from cryptography import x509

        with open(CERT_FILE, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        now = datetime.datetime.now(datetime.timezone.utc)
        return cert.not_valid_after_utc < (now + datetime.timedelta(days=7))
    except Exception:
        return True


def get_ssl_context() -> ssl.SSLContext:
    """
    Return SSLContext for local IMAP/SMTP servers.
    Auto-generates cert if missing or expired.
    """
    if _is_cert_expired():
        logger.info("Generating TLS certificate...")
        _generate_cert()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=str(CERT_FILE), keyfile=str(KEY_FILE))
    logger.info(f"✅ TLS ready (cert: {CERT_FILE})")
    return ctx


def cert_info() -> dict:
    """Return basic cert info for display."""
    if not CERT_FILE.exists():
        return {"exists": False}
    try:
        from cryptography import x509

        with open(CERT_FILE, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        return {
            "exists": True,
            "path": str(CERT_FILE),
            "expires": cert.not_valid_after_utc.isoformat(),
            "expired": _is_cert_expired(),
        }
    except Exception as e:
        return {"exists": True, "error": str(e)}
