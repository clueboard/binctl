from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone

from flask import g
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL environment variable is not set')

engine = create_engine(DATABASE_URL, future=True)


def get_db() -> Connection:
    if 'db' not in g:
        g.db = engine.connect()

    return g.db


@contextmanager
def transactional() -> Iterator[Connection]:
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise


# --------------------------------------------------------------------
# Node helpers
# --------------------------------------------------------------------
def _as_utc(dt: datetime | str | None) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def iso(dt: datetime | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def fetch_node(node_id: int) -> RowMapping | None:
    db = get_db()
    stmt = text(
        """
        SELECT id, label, description, is_container, created_at, updated_at
        FROM nodes
        WHERE id = :id
        """
    )
    row = db.execute(stmt, {'id': node_id}).mappings().first()

    return row


def fetch_parent_id(node_id: int) -> int | None:
    db = get_db()
    stmt = text(
        """
        SELECT parent_id
        FROM edges
        WHERE child_id = :id
        """
    )
    row = db.execute(stmt, {'id': node_id}).mappings().first()

    return row['parent_id'] if row else None


def fetch_children(node_id: int) -> list[dict]:
    db = get_db()
    stmt = text(
        """
        SELECT n.id, n.label, n.description, n.is_container,
               n.created_at, n.updated_at
        FROM edges e
        JOIN nodes n ON n.id = e.child_id
        WHERE e.parent_id = :id
        ORDER BY n.id
        """
    )
    rows = db.execute(stmt, {'id': node_id}).mappings().all()

    return [
        {
            'id': r['id'],
            'label': r['label'],
            'description': r['description'],
            'is_container': bool(r['is_container']),
            'created_at': iso(r['created_at']),
            'updated_at': iso(r['updated_at']),
        }
        for r in rows
    ]


def node_has_children(node_id: int) -> bool:
    db = get_db()
    stmt = text('SELECT 1 FROM edges WHERE parent_id = :id LIMIT 1')
    return db.execute(stmt, {'id': node_id}).first() is not None


def fetch_tags_for_node(node_id: int) -> list[dict]:
    db = get_db()
    stmt = text(
        """
        SELECT t.id, t.name, t.created_at, t.updated_at
        FROM tag_node tn
        JOIN tags t ON t.id = tn.tag_id
        WHERE tn.node_id = :id
        ORDER BY t.name
        """
    )
    rows = db.execute(stmt, {'id': node_id}).mappings().all()

    return [
        {'id': r['id'], 'name': r['name'], 'created_at': iso(r['created_at']), 'updated_at': iso(r['updated_at'])}
        for r in rows
    ]


def ensure_parent_is_valid(parent_id: int, child_id: int | None = None) -> None:
    """
    Validates that parent_id refers to an existing container node.
    Raises ValueError on any violation.
    """
    if child_id is not None and parent_id == child_id:
        raise ValueError('parent_id cannot equal node_id')

    db = get_db()
    stmt = text(
        """
        SELECT id, is_container
        FROM nodes
        WHERE id = :id
        """
    )
    row = db.execute(stmt, {'id': parent_id}).mappings().first()

    if not row:
        raise ValueError(f'parent_id {parent_id} does not exist')

    if not row['is_container']:
        raise ValueError('parent_id must refer to a container node')

    if child_id is not None:
        cycle_stmt = text(
            """
            WITH RECURSIVE ancestors AS (
                SELECT parent_id AS ancestor_id
                FROM   edges
                WHERE  child_id = :parent_id
                UNION ALL
                SELECT e.parent_id
                FROM   edges e
                JOIN   ancestors a ON e.child_id = a.ancestor_id
            )
            SELECT 1 FROM ancestors WHERE ancestor_id = :child_id LIMIT 1
            """
        )
        cycle_row = db.execute(cycle_stmt, {'parent_id': parent_id, 'child_id': child_id}).first()
        if cycle_row:
            raise ValueError('setting this parent would create a cycle')


def set_parent(node_id: int, parent_id: int | None) -> None:
    """
    Sets (or clears) a node's parent.
    If parent_id is None, removes parent.
    """
    db = get_db()

    db.execute(text('DELETE FROM edges WHERE child_id = :id'), {'id': node_id})  # Remove existing edge

    if parent_id is not None:
        db.execute(
            text(
                """
                INSERT INTO edges (parent_id, child_id)
                VALUES (:parent_id, :child_id)
                """
            ),
            {'parent_id': parent_id, 'child_id': node_id},
        )


def replace_node_tags(node_id: int, tag_ids: list[int]) -> None:
    db = get_db()

    db.execute(
        text('DELETE FROM tag_node WHERE node_id = :node_id'),
        {'node_id': node_id},
    )

    if tag_ids:
        db.execute(
            text('INSERT INTO tag_node (tag_id, node_id) VALUES (:tag_id, :node_id)'),
            [{'tag_id': tid, 'node_id': node_id} for tid in set(tag_ids)],
        )


def node_row_to_dict(row: RowMapping) -> dict:
    return {
        'id': row['id'],
        'label': row['label'],
        'description': row['description'],
        'is_container': bool(row['is_container']),
        'created_at': iso(row['created_at']),
        'updated_at': iso(row['updated_at']),
    }


# --------------------------------------------------------------------
# Tag helpers
# --------------------------------------------------------------------


def tag_row_to_dict(row: RowMapping) -> dict:
    return {
        'id': row['id'],
        'name': row['name'],
        'created_at': iso(row['created_at']),
        'updated_at': iso(row['updated_at']),
    }


def fetch_tag(tag_id: int) -> RowMapping | None:
    db = get_db()
    stmt = text(
        """
        SELECT id, name, created_at, updated_at
        FROM tags
        WHERE id = :id
        """
    )
    return db.execute(stmt, {'id': tag_id}).mappings().first()


def count_tags() -> int:
    return get_db().execute(text('SELECT COUNT(*) FROM tags')).scalar()


def fetch_tags_page(limit: int, offset: int) -> Sequence[RowMapping]:
    stmt = text(
        """
        SELECT id, name, created_at, updated_at
        FROM tags
        ORDER BY name
        LIMIT :limit OFFSET :offset
        """
    )
    return get_db().execute(stmt, {'limit': limit, 'offset': offset}).mappings().all()


def fetch_nodes_for_tag(tag_id: int) -> Sequence[RowMapping]:
    stmt = text(
        """
        SELECT n.id, n.label, n.description, n.is_container,
               n.created_at, n.updated_at
        FROM tag_node tn
        JOIN nodes n ON n.id = tn.node_id
        WHERE tn.tag_id = :id
        ORDER BY n.id
        """
    )
    return get_db().execute(stmt, {'id': tag_id}).mappings().all()


def create_tag(name: str) -> int:
    result = get_db().execute(text('INSERT INTO tags (name) VALUES (:name)'), {'name': name})
    return result.lastrowid


def update_tag(tag_id: int, name: str) -> int:
    result = get_db().execute(
        text('UPDATE tags SET name = :name, updated_at = CURRENT_TIMESTAMP WHERE id = :id'),
        {'name': name, 'id': tag_id},
    )
    return result.rowcount


# --------------------------------------------------------------------
# Node write helpers
# --------------------------------------------------------------------


def count_nodes() -> int:
    return get_db().execute(text('SELECT COUNT(*) FROM nodes')).scalar()


def fetch_nodes_page(limit: int, offset: int) -> Sequence[RowMapping]:
    stmt = text(
        """
        SELECT id, label, description, is_container, created_at, updated_at
        FROM nodes
        ORDER BY id
        LIMIT :limit OFFSET :offset
        """
    )
    return get_db().execute(stmt, {'limit': limit, 'offset': offset}).mappings().all()


def create_node(label: str, description: str | None, is_container: bool) -> int:
    result = get_db().execute(
        text(
            """
            INSERT INTO nodes (label, description, is_container)
            VALUES (:label, :description, :is_container)
            """
        ),
        {'label': label, 'description': description, 'is_container': is_container},
    )
    return result.lastrowid


def update_node_fields(node_id: int, fields: dict) -> None:
    set_clause = ', '.join(f'{k} = :{k}' for k in fields)
    get_db().execute(
        text(f'UPDATE nodes SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = :id'),
        {**fields, 'id': node_id},
    )


# --------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------
def fetch_user_by_username(username: str) -> RowMapping | None:
    return get_db().execute(
        text('SELECT id, password_hash FROM users WHERE username = :u'),
        {'u': username},
    ).mappings().first()


def update_user_last_login(user_id: int) -> None:
    get_db().execute(
        text('UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = :id'),
        {'id': user_id},
    )


def create_user_session(user_id: int, token: str) -> None:
    """Update last_login_at and insert a new token in a single transaction."""
    with transactional():
        update_user_last_login(user_id)
        get_db().execute(
            text('INSERT INTO tokens (user_id, token) VALUES (:user_id, :token)'),
            {'user_id': user_id, 'token': token},
        )


def revoke_token(token_id: int) -> None:
    with transactional():
        get_db().execute(
            text('DELETE FROM tokens WHERE id = :id'),
            {'id': token_id},
        )


def fetch_token_and_touch(token: str) -> dict | None:
    """Fetch token+user row and update last_used_at atomically.

    Uses engine.connect() directly — safe to call outside a Flask request
    context (e.g. from Connexion's ASGI security middleware).
    Returns None if the token does not exist.
    """
    with engine.connect() as conn:
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
            return None
        conn.execute(
            text('UPDATE tokens SET last_used_at = CURRENT_TIMESTAMP WHERE id = :id'),
            {'id': row['token_id']},
        )
        conn.commit()
    return {
        'token_id': row['token_id'],
        'expires_at': _as_utc(row['expires_at']),
        'user_id': row['user_id'],
        'username': row['username'],
    }
