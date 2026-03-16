"""Column-level encryption for sensitive case data using Fernet (AES-128-CBC + HMAC-SHA256)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def derive_fernet_key(secret: str) -> bytes:
    """Derive a Fernet-compatible key from a shared secret (e.g. AUTH_JWT_SECRET).

    Uses SHA-256 to produce a 32-byte key, then base64url-encodes it
    as required by Fernet.
    """
    raw = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)


class FieldEncryptor:
    """Transparent encryption/decryption for SQLite text columns.

    Wraps ``cryptography.fernet.Fernet`` to provide simple encrypt/decrypt
    helpers that handle ``None`` values and return strings (not bytes) so
    they can be stored directly in SQLite TEXT columns.

    Usage::

        key = derive_fernet_key(os.environ["AUTH_JWT_SECRET"])
        enc = FieldEncryptor(key)

        ciphertext = enc.encrypt("sensitive data")
        plaintext  = enc.decrypt(ciphertext)
    """

    def __init__(self, key: bytes) -> None:
        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str | None) -> str | None:
        """Encrypt a plaintext string. Returns ``None`` if input is ``None``."""
        if plaintext is None:
            return None
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str | None) -> str | None:
        """Decrypt a ciphertext string. Returns ``None`` if input is ``None``."""
        if ciphertext is None:
            return None
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def is_encrypted(self, value: str | None) -> bool:
        """Check whether a value appears to be Fernet-encrypted.

        Useful for idempotent migration — skip values already encrypted.
        Does NOT guarantee the value can be decrypted with *this* key.
        """
        if value is None:
            return False
        try:
            self._fernet.decrypt(value.encode())
            return True
        except (InvalidToken, Exception):
            return False
