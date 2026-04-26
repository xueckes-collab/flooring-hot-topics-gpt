"""Symmetric encryption for stored Semrush keys.

We use Fernet (AES-128-CBC + HMAC-SHA256) from `cryptography`.  The
encryption key is loaded from KEY_ENCRYPTION_SECRET in .env.  If the
secret is missing we generate an ephemeral one and log a loud warning
so dev gets bootstrapped, but production MUST set its own (otherwise
restarting the server invalidates all stored tokens).
"""
from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

log = logging.getLogger(__name__)


def _load_fernet() -> Fernet:
    secret = settings.key_encryption_secret.strip()
    if not secret:
        ephemeral = Fernet.generate_key().decode()
        log.warning(
            "KEY_ENCRYPTION_SECRET is empty — using an ephemeral key. "
            "Stored Semrush keys will be UNREADABLE after the next restart. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
        secret = ephemeral
    try:
        return Fernet(secret.encode())
    except Exception as exc:
        raise RuntimeError(
            "KEY_ENCRYPTION_SECRET is set but not a valid Fernet key. "
            "Regenerate with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        ) from exc


_fernet = _load_fernet()


def encrypt(plaintext: str) -> bytes:
    return _fernet.encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    try:
        return _fernet.decrypt(ciphertext).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Failed to decrypt stored Semrush key. The KEY_ENCRYPTION_SECRET "
            "in .env probably changed since this row was written."
        ) from exc


def mask(api_key: str, head: int = 4, tail: int = 4) -> str:
    """For logs / UI: 'sm_xxxx...abcd'."""
    if not api_key:
        return ""
    if len(api_key) <= head + tail:
        return "*" * len(api_key)
    return f"{api_key[:head]}...{api_key[-tail:]}"
