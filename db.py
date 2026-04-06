from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

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

    return [{'id': r['id'], 'name': r['name'], 'created_at': iso(r['created_at']), 'updated_at': iso(r['updated_at'])} for r in rows]


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
