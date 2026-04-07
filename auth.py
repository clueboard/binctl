from __future__ import annotations

import secrets
from datetime import datetime, timezone

from connexion.exceptions import Unauthorized
from passlib.context import CryptContext
from sqlalchemy import text

import db as _db

_crypt = CryptContext(schemes=['bcrypt'], deprecated='auto')


def hash_password(password: str) -> str:
    return _crypt.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _crypt.verify(password, password_hash)
    except Exception:
        return False


def create_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with _db.transactional() as conn:
        conn.execute(
            text('INSERT INTO tokens (user_id, token) VALUES (:user_id, :token)'),
            {'user_id': user_id, 'token': token},
        )
    return token


def lookup_token(token: str, required_scopes: object = None) -> dict:  # noqa: ARG001
    """Connexion x-bearerInfoFunc security handler.

    Uses engine.connect() directly because this runs in Connexion's ASGI
    security middleware before Flask pushes an application context, so
    flask.g / get_db() are not available here.
    """
    with _db.engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT t.id AS token_id, t.expires_at,
                       u.id AS user_id, u.username
                FROM tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token = :token
                """
            ),
            {'token': token},
        ).mappings().first()

        if row is None:
            raise Unauthorized('Invalid or expired token')

        if row['expires_at'] is not None:
            expires = row['expires_at']
            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires)
            if expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                raise Unauthorized('Invalid or expired token')

        conn.execute(
            text('UPDATE tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = :id'),
            {'id': row['token_id']},
        )
        conn.commit()

    return {
        'sub': row['username'],
        'user_id': row['user_id'],
        'token_id': row['token_id'],
    }
