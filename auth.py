from __future__ import annotations

import hashlib
import secrets

from passlib.context import CryptContext

_crypt = CryptContext(schemes=['bcrypt'], deprecated='auto')


def hash_password(password: str) -> str:
    return _crypt.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _crypt.verify(password, password_hash)
    except Exception:
        return False


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a raw API token."""
    return hashlib.sha256(token.encode()).hexdigest()


def mask_token(suffix: str, total_length: int = 43) -> str:
    """Return a masked token string, e.g. '************abcd'.

    total_length=43 matches len(secrets.token_urlsafe(32)).
    """
    return '*' * (total_length - len(suffix)) + suffix
