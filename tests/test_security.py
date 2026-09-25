import pytest
from cryptography.fernet import Fernet

from app.core.security import TokenDecryptionError, decrypt_token, encrypt_token


def test_round_trip():
    assert decrypt_token(encrypt_token("secret-token")) == "secret-token"


def test_ciphertext_is_not_plaintext_and_is_randomised():
    a, b = encrypt_token("secret-token"), encrypt_token("secret-token")
    assert "secret-token" not in a
    assert a != b  # Fernet uses a fresh IV each time


def test_wrong_key_fails_cleanly():
    ct = encrypt_token("secret-token")
    with pytest.raises(TokenDecryptionError):
        decrypt_token(ct, key=Fernet.generate_key().decode())


def test_tampered_ciphertext_fails():
    ct = encrypt_token("secret-token")
    with pytest.raises(TokenDecryptionError):
        decrypt_token(ct[:-4] + "AAAA")
