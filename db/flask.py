from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime

from flask import g
from passlib.context import CryptContext as _CryptContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping

import db
from auth import generate_token, hash_token
from db.id_gen import new_id

_crypt = _CryptContext(schemes=['bcrypt'], deprecated='auto')

# Pre-computed bcrypt hash used when the username is not found, so verify_password
# always does full key-stretching regardless of whether the username exists.
# Prevents timing attacks that distinguish "unknown user" from "wrong password".
_DUMMY_HASH = '$2b$12$.OT9HVdRiWO/c/eawiYjjOa1.ujHVTxLo3eKEU9gdhRAMwUSvO/ei'


def get_db() -> Connection:
    if 'db' not in g:
        g.db = db.engine.connect()
    return g.db


@contextmanager
def transactional() -> Iterator[Connection]:
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------


def iso(dt: datetime | str | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def node_row_to_dict(row: RowMapping) -> dict:
    return {
        'id': row['id'],
        'label': row['label'],
        'description': row['description'],
        'is_container': bool(row['is_container']),
        'created_at': iso(row['created_at']),
        'updated_at': iso(row['updated_at']),
    }


def tag_row_to_dict(row: RowMapping) -> dict:
    return {
        'id': row['id'],
        'name': row['name'],
        'created_at': iso(row['created_at']),
        'updated_at': iso(row['updated_at']),
    }


# --------------------------------------------------------------------
# Node helpers
# --------------------------------------------------------------------


def fetch_node(node_id: int) -> RowMapping | None:
    return (
        get_db()
        .execute(
            text(
                """
            SELECT id, label, description, is_container, created_at, updated_at
            FROM nodes
            WHERE id = :id
            """
            ),
            {'id': node_id},
        )
        .mappings()
        .first()
    )


def fetch_parent_id(node_id: int) -> int | None:
    row = (
        get_db()
        .execute(
            text('SELECT parent_id FROM edges WHERE child_id = :id'),
            {'id': node_id},
        )
        .mappings()
        .first()
    )
    return row['parent_id'] if row else None


def fetch_children(node_id: int) -> list[dict]:
    rows = (
        get_db()
        .execute(
            text(
                """
            SELECT n.id, n.label, n.description, n.is_container,
                   n.created_at, n.updated_at
            FROM edges e
            JOIN nodes n ON n.id = e.child_id
            WHERE e.parent_id = :id
            ORDER BY n.id
            """
            ),
            {'id': node_id},
        )
        .mappings()
        .all()
    )
    return [node_row_to_dict(r) for r in rows]


def node_has_children(node_id: int) -> bool:
    return (
        get_db()
        .execute(
            text('SELECT 1 FROM edges WHERE parent_id = :id LIMIT 1'),
            {'id': node_id},
        )
        .first()
        is not None
    )


def fetch_tags_for_node(node_id: int) -> list[dict]:
    rows = (
        get_db()
        .execute(
            text(
                """
            SELECT t.id, t.name, t.created_at, t.updated_at
            FROM tag_node tn
            JOIN tags t ON t.id = tn.tag_id
            WHERE tn.node_id = :id
            ORDER BY t.name
            """
            ),
            {'id': node_id},
        )
        .mappings()
        .all()
    )
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

    row = (
        get_db()
        .execute(
            text('SELECT id, is_container FROM nodes WHERE id = :id'),
            {'id': parent_id},
        )
        .mappings()
        .first()
    )

    if not row:
        raise ValueError(f'parent_id {parent_id} does not exist')

    if not row['is_container']:
        raise ValueError('parent_id must refer to a container node')

    if child_id is not None:
        cycle_row = (
            get_db()
            .execute(
                text(
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
                ),
                {'parent_id': parent_id, 'child_id': child_id},
            )
            .first()
        )
        if cycle_row:
            raise ValueError('setting this parent would create a cycle')


def set_parent(node_id: int, parent_id: int | None) -> None:
    """Sets (or clears) a node's parent."""
    conn = get_db()
    conn.execute(text('DELETE FROM edges WHERE child_id = :id'), {'id': node_id})
    if parent_id is not None:
        conn.execute(
            text('INSERT INTO edges (parent_id, child_id) VALUES (:parent_id, :child_id)'),
            {'parent_id': parent_id, 'child_id': node_id},
        )


def replace_node_tags(node_id: int, tag_ids: list[int]) -> None:
    conn = get_db()
    conn.execute(text('DELETE FROM tag_node WHERE node_id = :node_id'), {'node_id': node_id})
    if tag_ids:
        conn.execute(
            text('INSERT INTO tag_node (tag_id, node_id) VALUES (:tag_id, :node_id)'),
            [{'tag_id': tid, 'node_id': node_id} for tid in set(tag_ids)],
        )


def count_nodes() -> int:
    return get_db().execute(text('SELECT COUNT(*) FROM nodes')).scalar()


def fetch_nodes_page(limit: int, offset: int) -> Sequence[RowMapping]:
    return (
        get_db()
        .execute(
            text(
                """
            SELECT id, label, description, is_container, created_at, updated_at
            FROM nodes
            ORDER BY id
            LIMIT :limit OFFSET :offset
            """
            ),
            {'limit': limit, 'offset': offset},
        )
        .mappings()
        .all()
    )


def create_node(label: str, description: str | None, is_container: bool) -> int:
    node_id = new_id()
    get_db().execute(
        text(
            """
            INSERT INTO nodes (id, label, description, is_container)
            VALUES (:id, :label, :description, :is_container)
            """
        ),
        {'id': node_id, 'label': label, 'description': description, 'is_container': is_container},
    )
    return node_id


def update_node_fields(node_id: int, fields: dict) -> None:
    set_clause = ', '.join(f'{k} = :{k}' for k in fields)
    get_db().execute(
        text(f'UPDATE nodes SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = :id'),
        {**fields, 'id': node_id},
    )


# --------------------------------------------------------------------
# Tag helpers
# --------------------------------------------------------------------


def fetch_tag(tag_id: int) -> RowMapping | None:
    return (
        get_db()
        .execute(
            text('SELECT id, name, created_at, updated_at FROM tags WHERE id = :id'),
            {'id': tag_id},
        )
        .mappings()
        .first()
    )


def count_tags() -> int:
    return get_db().execute(text('SELECT COUNT(*) FROM tags')).scalar()


def fetch_tags_page(limit: int, offset: int) -> Sequence[RowMapping]:
    return (
        get_db()
        .execute(
            text(
                """
            SELECT id, name, created_at, updated_at
            FROM tags
            ORDER BY name
            LIMIT :limit OFFSET :offset
            """
            ),
            {'limit': limit, 'offset': offset},
        )
        .mappings()
        .all()
    )


def fetch_nodes_for_tag(tag_id: int) -> Sequence[RowMapping]:
    return (
        get_db()
        .execute(
            text(
                """
            SELECT n.id, n.label, n.description, n.is_container,
                   n.created_at, n.updated_at
            FROM tag_node tn
            JOIN nodes n ON n.id = tn.node_id
            WHERE tn.tag_id = :id
            ORDER BY n.id
            """
            ),
            {'id': tag_id},
        )
        .mappings()
        .all()
    )


def create_tag(name: str) -> int:
    tag_id = new_id()
    get_db().execute(text('INSERT INTO tags (id, name) VALUES (:id, :name)'), {'id': tag_id, 'name': name})
    return tag_id


def update_tag(tag_id: int, name: str) -> int:
    result = get_db().execute(
        text('UPDATE tags SET name = :name, updated_at = CURRENT_TIMESTAMP WHERE id = :id'),
        {'name': name, 'id': tag_id},
    )
    return result.rowcount


# --------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------


def fetch_user_by_username(username: str) -> RowMapping | None:
    return (
        get_db()
        .execute(
            text('SELECT id, password_hash FROM users WHERE username = :u'),
            {'u': username},
        )
        .mappings()
        .first()
    )


def verify_password(username: str, password: str) -> RowMapping | None:
    """Return the user row if credentials are valid, None otherwise.

    Always runs full bcrypt verification to prevent timing attacks.
    """
    row = fetch_user_by_username(username)
    stored_hash = row['password_hash'] if row is not None else _DUMMY_HASH
    try:
        valid = _crypt.verify(password, stored_hash)
    except Exception:
        valid = False
    if not valid or row is None:
        return None
    return row


def update_user_last_login(user_id: int) -> None:
    get_db().execute(
        text('UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = :id'),
        {'id': user_id},
    )


def create_user_session(user_id: int) -> str:
    """Update last_login_at, insert a new token, and return the raw token (only exposure)."""
    token = generate_token()
    with transactional():
        update_user_last_login(user_id)
        get_db().execute(
            text(
                'INSERT INTO tokens (id, user_id, token_hash, token_suffix)'
                ' VALUES (:id, :user_id, :token_hash, :token_suffix)'
            ),
            {'id': new_id(), 'user_id': user_id, 'token_hash': hash_token(token), 'token_suffix': token[-4:]},
        )
    return token


def revoke_token(token_id: int) -> None:
    with transactional():
        get_db().execute(
            text('DELETE FROM tokens WHERE id = :id'),
            {'id': token_id},
        )
