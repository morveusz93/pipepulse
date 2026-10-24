import pytest
from cryptography.fernet import Fernet

from pipepulse.crypto import (
    EncryptionKeyMissingError,
    TokenCipher,
    TokenDecryptionError,
    token_hint,
)

# Assembled at runtime so secret scanners don't flag a token-shaped literal in the source.
TOKEN = "glpat-" + "fake" * 5


def test_roundtrip_and_ciphertext_hides_token() -> None:
    cipher = TokenCipher(Fernet.generate_key().decode())
    encrypted = cipher.encrypt(TOKEN)
    assert TOKEN.encode() not in encrypted
    assert cipher.decrypt(encrypted) == TOKEN


def test_wrong_key_raises_without_leaking() -> None:
    encrypted = TokenCipher(Fernet.generate_key().decode()).encrypt(TOKEN)
    other = TokenCipher(Fernet.generate_key().decode())
    with pytest.raises(TokenDecryptionError) as exc_info:
        other.decrypt(encrypted)
    assert TOKEN not in str(exc_info.value)


def test_key_rotation() -> None:
    old_key, new_key = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    encrypted_old = TokenCipher(old_key).encrypt(TOKEN)

    rotating = TokenCipher(f"{new_key},{old_key}")
    assert rotating.decrypt(encrypted_old) == TOKEN

    rotated = rotating.rotate(encrypted_old)
    assert TokenCipher(new_key).decrypt(rotated) == TOKEN


def test_empty_key_rejected() -> None:
    with pytest.raises(EncryptionKeyMissingError):
        TokenCipher(" , ")


def test_token_hint() -> None:
    assert token_hint(TOKEN) == "fake"
