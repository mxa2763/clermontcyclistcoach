from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class TokenDecryptionError(Exception):
    pass


def _fernet(key: str | None = None) -> Fernet:
    return Fernet((key or get_settings().fernet_key).encode())


def encrypt_token(plaintext: str, key: str | None = None) -> str:
    return _fernet(key).encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str, key: str | None = None) -> str:
    try:
        return _fernet(key).decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise TokenDecryptionError("Stored token could not be decrypted (wrong FERNET_KEY?)") from exc
