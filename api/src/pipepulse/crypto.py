"""Encryption of GitLab tokens at rest.

PIPEPULSE_ENCRYPTION_KEY holds one or more comma-separated Fernet keys. The first key
encrypts; all keys can decrypt, so a key can be rotated by prepending a new one and
re-encrypting stored tokens before removing the old key.
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from pipepulse.config import get_settings


class EncryptionKeyMissingError(RuntimeError):
    pass


class TokenDecryptionError(RuntimeError):
    pass


class TokenCipher:
    def __init__(self, keys: str) -> None:
        fernets = [Fernet(key.strip()) for key in keys.split(",") if key.strip()]
        if not fernets:
            raise EncryptionKeyMissingError("PIPEPULSE_ENCRYPTION_KEY is empty")
        self._fernet = MultiFernet(fernets)

    def encrypt(self, token: str) -> bytes:
        return self._fernet.encrypt(token.encode())

    def decrypt(self, encrypted: bytes) -> str:
        try:
            return self._fernet.decrypt(encrypted).decode()
        except InvalidToken as exc:
            # Never include the ciphertext or token in the message.
            raise TokenDecryptionError(
                "stored token cannot be decrypted with current keys"
            ) from exc

    def rotate(self, encrypted: bytes) -> bytes:
        """Re-encrypt with the primary (first) key."""
        return self._fernet.rotate(encrypted)


def get_cipher() -> TokenCipher:
    key = get_settings().encryption_key
    if key is None or not key.get_secret_value().strip():
        raise EncryptionKeyMissingError(
            "PIPEPULSE_ENCRYPTION_KEY is not set — required to store or use GitLab tokens"
        )
    return TokenCipher(key.get_secret_value())


def token_hint(token: str) -> str:
    """Last 4 characters, for masked display like glpat-****abcd."""
    return token[-4:]
