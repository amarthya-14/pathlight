"""
Encryption at rest for per-user OAuth tokens — Gate 10, brought forward from the
Security gate (docs/SECURITY.md) because Gmail is the first tool in this project that
needs a real per-user token. Fernet (AES-128-CBC + HMAC-SHA256, from the `cryptography`
package) with a single app-level key from TOKEN_ENCRYPTION_KEY.

No key = no encryption = the integration refuses to work (TokenEncryptionUnavailable),
never a silent fallback to storing plaintext. Key rotation (MultiFernet) is deliberately
out of scope for this gate — see docs/AUTONOMOUS_APPLICATIONS.md §10.
"""
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class TokenEncryptionUnavailable(RuntimeError):
    """TOKEN_ENCRYPTION_KEY is unset or not a valid Fernet key."""


def _fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        raise TokenEncryptionUnavailable("TOKEN_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as e:
        raise TokenEncryptionUnavailable(f"TOKEN_ENCRYPTION_KEY is not a valid Fernet key: {e}") from e


def encryption_available() -> bool:
    try:
        _fernet()
        return True
    except TokenEncryptionUnavailable:
        return False


def encrypt_token(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        # Wrong/rotated key or a tampered value — surfaced as a hard failure, not ""
        raise TokenEncryptionUnavailable("Stored token could not be decrypted with the current key") from e
