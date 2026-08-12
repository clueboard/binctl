"""Authentication persistence usable outside Flask request contexts."""

from sqlalchemy import text

from ..auth import hash_token
from .engine import engine


def fetch_token_and_touch(token: str) -> dict | None:
    """Return an active token's identity and best-effort update its last-use time."""
    with engine.connect() as conn:
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
        conn.execute(text('UPDATE tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = :id'), {'id': row['token_id']})
        conn.commit()
    return {'token_id': row['token_id'], 'user_id': row['user_id'], 'username': row['username']}
