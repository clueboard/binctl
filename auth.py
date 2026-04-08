import hashlib
import math
import secrets

from passlib.context import CryptContext

_TOKEN_BYTES = 32
TOKEN_LENGTH = math.ceil(_TOKEN_BYTES * 4 / 3)  # base64url length without padding
_crypt = CryptContext(schemes=['bcrypt'], deprecated='auto')


def hash_password(password: str) -> str:
    return _crypt.hash(password)


def generate_token() -> str:
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a raw API token."""
    return hashlib.sha256(token.encode()).hexdigest()


def mask_token(suffix: str, total_length: int = TOKEN_LENGTH) -> str:
    """Return a masked token string, e.g. '************abcd'."""
    return '*' * (total_length - len(suffix)) + suffix
