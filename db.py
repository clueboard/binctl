import os

from flask import g
from sqlalchemy import create_engine, text

from web import error

# Configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'mysql+mysqlconnector://user:password@localhost:3306/storage_db')


def get_db():
    if 'db' not in g:
        engine = create_engine(DATABASE_URL, future=True)
        g.db = engine.connect()

    return g.db


# --------------------------------------------------------------------
# Node helpers
# --------------------------------------------------------------------
def iso(dt):
    if dt:
        return dt.isoformat()


def fetch_node(node_id):
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


def fetch_parent_id(node_id):
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


def fetch_children(node_id):
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


def fetch_tags_for_node(node_id):
    db = get_db()
    stmt = text(
        """
        SELECT t.id, t.name
        FROM tag_node tn
        JOIN tags t ON t.id = tn.tag_id
        WHERE tn.node_id = :id
        ORDER BY t.name
        """
    )
    rows = db.execute(stmt, {'id': node_id}).mappings().all()

    return [{'id': r['id'], 'name': r['name']} for r in rows]


def ensure_parent_is_valid(parent_id, child_id=None):
    """
    Ensures parent exists and (optionally) isn't equal to child.
    Optionally enforces that parent is a container.
    """
    if parent_id is None:
        return None

    if child_id is not None and parent_id == child_id:
        return error(400, 'parent_id cannot equal node_id')

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
        return error(400, f'parent_id {parent_id} does not exist')

    if not row['is_container']:
        return error(400, 'parent_id must refer to a container node')

    return None


def set_parent(node_id, parent_id):
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


def replace_node_tags(node_id, tag_ids):
    db = get_db()

    # Ensure all tags exist
    if tag_ids:
        stmt = text(
            """
            SELECT id FROM tags
            WHERE id IN :ids
            """
        )
        existing = db.execute(stmt, {'ids': tuple(tag_ids)}).scalars().all()
        missing = set(tag_ids) - set(existing)

        if missing:
            raise ValueError(f'Unknown tag_ids: {sorted(missing)}')

    # Delete tags not in new set
    if tag_ids:
        db.execute(
            text(
                """
                DELETE FROM tag_node
                WHERE node_id = :node_id
                  AND tag_id NOT IN :ids
                """
            ),
            {'node_id': node_id, 'ids': tuple(tag_ids)},
        )

    else:
        db.execute(
            text('DELETE FROM tag_node WHERE node_id = :node_id'),
            {'node_id': node_id},
        )

    # Insert missing associations
    if tag_ids:
        for tid in set(tag_ids):
            db.execute(
                text(
                    """
                    INSERT INTO tag_node (tag_id, node_id)
                    VALUES (:tag_id, :node_id)
                    ON DUPLICATE KEY UPDATE created_at = created_at
                    """
                ),
                {'tag_id': tid, 'node_id': node_id},
            )


def node_row_to_dict(row):
    return {
        'id': row['id'],
        'label': row['label'],
        'description': row['description'],
        'is_container': bool(row['is_container']),
        'created_at': iso(row['created_at']),
        'updated_at': iso(row['updated_at']),
    }
