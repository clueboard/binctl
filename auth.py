from __future__ import annotations

import secrets
from datetime import datetime, timezone

from connexion.exceptions import Unauthorized
from passlib.context import CryptContext

import db

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


def lookup_token(token: str, required_scopes: object = None) -> dict:  # noqa: ARG001
    """Connexion x-bearerInfoFunc security handler.

    Uses db.fetch_token_and_touch() which opens its own engine connection,
    safe to call outside a Flask application context.
    """
    row = db.fetch_token_and_touch(token)

    if row is None:
        raise Unauthorized('Invalid or expired token')

    if row['expires_at'] is not None:
        expires = row['expires_at']
        if isinstance(expires, str):
            expires = datetime.fromisoformat(expires)
        if expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise Unauthorized('Invalid or expired token')

    return {
        'sub': row['username'],
        'user_id': row['user_id'],
        'token_id': row['token_id'],
    }
