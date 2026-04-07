from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.engine.row import RowMapping

import db
from auth import hash_token


def fetch_token_and_touch(token: str) -> dict | None:
    """Fetch token+user row and update last_used_at atomically.

    Opens its own connection — safe to call outside a Flask request context
    (e.g. from Connexion's ASGI security middleware).
    Returns None if the token does not exist.
    """
    with db.engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    """
                    SELECT t.id AS token_id, u.id AS user_id, u.username
                    FROM tokens t
                    JOIN users u ON u.id = t.user_id
                    WHERE t.token_hash = :token_hash
                      AND (t.expires_at IS NULL OR t.expires_at > CURRENT_TIMESTAMP)
                    """
                ),
                {'token_hash': hash_token(token)},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        conn.execute(
            text('UPDATE tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = :id'),
            {'id': row['token_id']},
        )
        conn.commit()
    return {
        'token_id': row['token_id'],
        'user_id': row['user_id'],
        'username': row['username'],
    }


def create_user(username: str, password_hash: str) -> None:
    with db.engine.connect() as conn:
        conn.execute(
            text('INSERT INTO users (username, password_hash) VALUES (:u, :h)'),
            {'u': username, 'h': password_hash},
        )
        conn.commit()


def fetch_all_users() -> Sequence[RowMapping]:
    with db.engine.connect() as conn:
        return conn.execute(
            text('SELECT id, username, created_at, last_login_at FROM users ORDER BY id')
        ).mappings().all()


def fetch_tokens_for_username(username: str) -> Sequence[RowMapping] | None:
    """Return tokens for username, or None if the user does not exist."""
    with db.engine.connect() as conn:
        user = (
            conn.execute(text('SELECT id FROM users WHERE username = :u'), {'u': username})
            .mappings()
            .first()
        )
        if user is None:
            return None
        return (
            conn.execute(
                text(
                    'SELECT id, token_suffix, created_at, last_used_at, expires_at'
                    ' FROM tokens WHERE user_id = :uid ORDER BY id'
                ),
                {'uid': user['id']},
            )
            .mappings()
            .all()
        )


def revoke_tokens_for_username(username: str) -> int | None:
    """Delete all tokens for username. Returns rowcount, or None if user not found."""
    with db.engine.connect() as conn:
        user = (
            conn.execute(text('SELECT id FROM users WHERE username = :u'), {'u': username})
            .mappings()
            .first()
        )
        if user is None:
            return None
        result = conn.execute(
            text('DELETE FROM tokens WHERE user_id = :uid'),
            {'uid': user['id']},
        )
        conn.commit()
    return result.rowcount
