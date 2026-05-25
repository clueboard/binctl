from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.engine.row import RowMapping

import db
from auth import generate_token, hash_password, hash_token, mask_token
from db.id_gen import new_id

ORPHAN_REASSIGN_CONTAINER_KEY = 'orphan_reassign_container_label'


def fetch_token_and_touch(token: str) -> dict | None:
    """Fetch token+user row and update last_used_at.

    The SELECT and UPDATE are separate statements; last_used_at is a
    best-effort audit field and a missed update on crash is harmless.

    Opens its own connection — safe to call outside a Flask request context
    (e.g. from Connexion's ASGI security middleware).
    Returns None if the token does not exist or has expired.
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


def create_user(username: str, password: str | None) -> int:
    user_id = new_id()
    password_hash = hash_password(password) if password is not None else '!'
    with db.engine.connect() as conn:
        conn.execute(
            text('INSERT INTO users (id, username, password_hash) VALUES (:id, :u, :h)'),
            {'id': user_id, 'u': username, 'h': password_hash},
        )
        conn.commit()
    return user_id


def create_token(user_id: int, expires_at: str | None = None) -> str:
    """Insert a new token for user_id and return the raw token (only exposure)."""
    token = generate_token()
    with db.engine.connect() as conn:
        conn.execute(
            text('INSERT INTO tokens (id, user_id, token_hash, token_suffix, expires_at) VALUES (:id, :uid, :th, :ts, :exp)'),
            {'id': new_id(), 'uid': user_id, 'th': hash_token(token), 'ts': token[-4:], 'exp': expires_at},
        )
        conn.commit()
    return token


def update_password(username: str, password: str) -> bool:
    """Update password for username. Returns False if user not found."""
    with db.engine.connect() as conn:
        result = conn.execute(
            text('UPDATE users SET password_hash = :h WHERE username = :u'),
            {'h': hash_password(password), 'u': username},
        )
        conn.commit()
    return result.rowcount > 0


def fetch_all_users() -> Sequence[RowMapping]:
    with db.engine.connect() as conn:
        return conn.execute(text('SELECT id, username, created_at, last_login_at FROM users ORDER BY id')).mappings().all()


def fetch_tokens_for_username(username: str) -> list[dict] | None:
    """Return tokens for username, or None if the user does not exist."""
    with db.engine.connect() as conn:
        user = conn.execute(text('SELECT id FROM users WHERE username = :u'), {'u': username}).mappings().first()
        if user is None:
            return None
        rows = (
            conn.execute(
                text('SELECT id, token_suffix, created_at, last_used_at, expires_at FROM tokens WHERE user_id = :uid ORDER BY id'),
                {'uid': user['id']},
            )
            .mappings()
            .all()
        )
    return [
        {
            'id': r['id'],
            'token': mask_token(r['token_suffix']),
            'created_at': r['created_at'],
            'last_used_at': r['last_used_at'],
            'expires_at': r['expires_at'],
        }
        for r in rows
    ]


def revoke_tokens_for_username(username: str) -> int | None:
    """Delete all tokens for username. Returns rowcount, or None if user not found."""
    with db.engine.connect() as conn:
        user = conn.execute(text('SELECT id FROM users WHERE username = :u'), {'u': username}).mappings().first()
        if user is None:
            return None
        result = conn.execute(
            text('DELETE FROM tokens WHERE user_id = :uid'),
            {'uid': user['id']},
        )
        conn.commit()
    return result.rowcount


def get_config_value(key: str) -> str | None:
    with db.engine.connect() as conn:
        row = conn.execute(text('SELECT value FROM app_config WHERE key = :key'), {'key': key}).mappings().first()
    return row['value'] if row else None


def set_config_value(key: str, value: str) -> None:
    with db.engine.connect() as conn:
        result = conn.execute(
            text('UPDATE app_config SET value = :value, updated_at = CURRENT_TIMESTAMP WHERE key = :key'),
            {'key': key, 'value': value},
        )
        if result.rowcount == 0:
            conn.execute(
                text('INSERT INTO app_config (key, value) VALUES (:key, :value)'),
                {'key': key, 'value': value},
            )
        conn.commit()


def delete_config_value(key: str) -> bool:
    with db.engine.connect() as conn:
        result = conn.execute(text('DELETE FROM app_config WHERE key = :key'), {'key': key})
        conn.commit()
    return result.rowcount > 0


def get_orphan_reassign_container_label() -> str | None:
    return get_config_value(ORPHAN_REASSIGN_CONTAINER_KEY)


def set_orphan_reassign_container_label(label: str) -> None:
    set_config_value(ORPHAN_REASSIGN_CONTAINER_KEY, label)


def clear_orphan_reassign_container_label() -> bool:
    return delete_config_value(ORPHAN_REASSIGN_CONTAINER_KEY)
