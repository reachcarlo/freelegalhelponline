"""Tests for privacy.encryption — FieldEncryptor and key derivation."""

from __future__ import annotations

import pytest

from employee_help.privacy.encryption import FieldEncryptor, derive_fernet_key


# ---------------------------------------------------------------------------
# derive_fernet_key
# ---------------------------------------------------------------------------


class TestDeriveFernetKey:
    def test_produces_valid_fernet_key(self):
        """Key must be 44-char url-safe base64 (32 bytes encoded)."""
        key = derive_fernet_key("test-secret")
        assert isinstance(key, bytes)
        assert len(key) == 44  # base64url of 32 bytes

    def test_deterministic(self):
        assert derive_fernet_key("same") == derive_fernet_key("same")

    def test_different_secrets_produce_different_keys(self):
        assert derive_fernet_key("secret-a") != derive_fernet_key("secret-b")


# ---------------------------------------------------------------------------
# FieldEncryptor — encrypt / decrypt
# ---------------------------------------------------------------------------


class TestFieldEncryptorBasics:
    @pytest.fixture()
    def enc(self):
        return FieldEncryptor(derive_fernet_key("test"))

    def test_round_trip(self, enc: FieldEncryptor):
        plain = "Hello, attorney-client privilege!"
        cipher = enc.encrypt(plain)
        assert cipher != plain
        assert enc.decrypt(cipher) == plain

    def test_none_encrypt(self, enc: FieldEncryptor):
        assert enc.encrypt(None) is None

    def test_none_decrypt(self, enc: FieldEncryptor):
        assert enc.decrypt(None) is None

    def test_empty_string(self, enc: FieldEncryptor):
        cipher = enc.encrypt("")
        assert cipher is not None
        assert enc.decrypt(cipher) == ""

    def test_unicode(self, enc: FieldEncryptor):
        text = "Confidential: \u00a9 2026 \u2014 names like Garc\u00eda"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_large_text(self, enc: FieldEncryptor):
        text = "x" * 100_000
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_multiline(self, enc: FieldEncryptor):
        text = "line1\nline2\n\ttabbed"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_ciphertext_is_str(self, enc: FieldEncryptor):
        """Ciphertext must be a string for SQLite TEXT columns."""
        cipher = enc.encrypt("test")
        assert isinstance(cipher, str)

    def test_different_ciphertext_each_call(self, enc: FieldEncryptor):
        """Fernet uses a random IV — same plaintext should produce different ciphertexts."""
        c1 = enc.encrypt("same")
        c2 = enc.encrypt("same")
        assert c1 != c2

    def test_wrong_key_fails(self):
        enc_a = FieldEncryptor(derive_fernet_key("key-a"))
        enc_b = FieldEncryptor(derive_fernet_key("key-b"))
        cipher = enc_a.encrypt("secret")
        with pytest.raises(Exception):
            enc_b.decrypt(cipher)


# ---------------------------------------------------------------------------
# FieldEncryptor — is_encrypted
# ---------------------------------------------------------------------------


class TestIsEncrypted:
    @pytest.fixture()
    def enc(self):
        return FieldEncryptor(derive_fernet_key("test"))

    def test_encrypted_value(self, enc: FieldEncryptor):
        cipher = enc.encrypt("hello")
        assert enc.is_encrypted(cipher) is True

    def test_plaintext_value(self, enc: FieldEncryptor):
        assert enc.is_encrypted("just plain text") is False

    def test_none_value(self, enc: FieldEncryptor):
        assert enc.is_encrypted(None) is False

    def test_empty_string(self, enc: FieldEncryptor):
        assert enc.is_encrypted("") is False

    def test_wrong_key(self):
        enc_a = FieldEncryptor(derive_fernet_key("key-a"))
        enc_b = FieldEncryptor(derive_fernet_key("key-b"))
        cipher = enc_a.encrypt("hello")
        # Different key — looks encrypted but can't be decrypted
        assert enc_b.is_encrypted(cipher) is False
