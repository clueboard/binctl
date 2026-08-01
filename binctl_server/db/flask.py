import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from flask import current_app, g
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.exc import IntegrityError

from .. import db
from ..auth import generate_token, hash_password, hash_token, verify_password_hash
from . import base62
from .id_gen import new_id

logger = logging.getLogger(__name__)

# Pre-computed scrypt hash used when the username is not found, so verify_password
# always does full key-stretching regardless of whether the username exists.
# Prevents timing attacks that distinguish "unknown user" from "wrong password".
_DUMMY_HASH = hash_password('dummy')


def get_db() -> Connection:
    """Return the per-request SQLAlchemy connection, opening it on first access."""
    if 'db' not in g:
        g.db = db.engine.connect()
    return g.db


@contextmanager
def transactional() -> Iterator[Connection]:
    """Wrap the current Flask-g connection in a commit/rollback block.

    WARNING: Nesting transactional() is not supported. The inner call reuses
    the same connection and commits on exit, which may commit data the outer
    caller expected to hold until its own exit. Do not nest transactional().
    """
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
    """Return an ISO 8601 string for *dt*, or None if *dt* is None."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def node_row_to_dict(row: RowMapping) -> dict:
    """Serialize a nodes row to a plain dict suitable for JSON responses."""
    result = {
        'id': base62.encode(row['id']),
        'label': row['label'],
        'description': row['description'],
        'is_container': bool(row['is_container']),
        'created_at': iso(row['created_at']),
        'updated_at': iso(row['updated_at']),
    }
    if 'parent_id' in row:
        result['parent_id'] = base62.encode(row['parent_id']) if row['parent_id'] is not None else None
    return result


def tag_row_to_dict(row: RowMapping) -> dict:
    """Serialize a tags row to a plain dict suitable for JSON responses."""
    return {
        'id': base62.encode(row['id']),
        'name': row['name'],
        'created_at': iso(row['created_at']),
        'updated_at': iso(row['updated_at']),
    }


# --------------------------------------------------------------------
# Node helpers
# --------------------------------------------------------------------


def fetch_node(node_id: int) -> RowMapping | None:
    """Return the nodes row for *node_id*, or None if it does not exist."""
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
    """Return the parent node id of *node_id*, or None if it has no parent."""
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
    """Return serialized dicts for all direct children of *node_id*."""
    rows = (
        get_db()
        .execute(
            text(
                """
            SELECT n.id, n.label, n.description, n.is_container,
                   n.created_at, n.updated_at, e.parent_id
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
    """Return True if *node_id* has at least one child edge."""
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
    """Return serialized tag dicts for all tags attached to *node_id*."""
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
    return [tag_row_to_dict(r) for r in rows]


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
    """Replace all tag associations for *node_id* with *tag_ids*."""
    conn = get_db()
    conn.execute(text('DELETE FROM tag_node WHERE node_id = :node_id'), {'node_id': node_id})
    if tag_ids:
        conn.execute(
            text('INSERT INTO tag_node (tag_id, node_id) VALUES (:tag_id, :node_id)'),
            [{'tag_id': tid, 'node_id': node_id} for tid in set(tag_ids)],
        )


def count_nodes() -> int:
    """Return the total number of nodes."""
    return get_db().execute(text('SELECT COUNT(*) FROM nodes')).scalar() or 0


def fetch_nodes_page(limit: int, offset: int) -> Sequence[RowMapping]:
    """Return a page of node rows ordered by id."""
    return (
        get_db()
        .execute(
            text(
                """
            SELECT n.id, n.label, n.description, n.is_container,
                   n.created_at, n.updated_at, e.parent_id
            FROM nodes n
            LEFT JOIN edges e ON e.child_id = n.id
            ORDER BY n.id
            LIMIT :limit OFFSET :offset
            """
            ),
            {'limit': limit, 'offset': offset},
        )
        .mappings()
        .all()
    )


def create_node(
    label: str,
    description: str | None,
    is_container: bool,
    *,
    parent_id: int | None = None,
    tag_ids: list[int] | None = None,
) -> int:
    """Insert a new node and return its id.

    Optionally assigns a parent and attaches tags in the same transaction.
    Raises ValueError for invalid parent_id or unknown tag_ids.
    """
    with transactional():
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
        if parent_id is not None:
            ensure_parent_is_valid(parent_id)
            set_parent(node_id, parent_id)
        if tag_ids:
            try:
                replace_node_tags(node_id, tag_ids)
            except IntegrityError:
                raise ValueError('One or more tag_ids do not exist')
    return node_id


_UPDATABLE_NODE_FIELDS = frozenset({'label', 'description', 'is_container'})


def update_node_fields(node_id: int, fields: dict) -> int:
    """Apply a subset of updatable fields to *node_id*. Returns rowcount."""
    invalid = fields.keys() - _UPDATABLE_NODE_FIELDS
    if invalid:
        raise ValueError(f'non-updatable node fields: {invalid}')
    set_clause = ', '.join(f'{k} = :{k}' for k in fields)
    result = get_db().execute(
        text(f'UPDATE nodes SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = :id'),
        {**fields, 'id': node_id},
    )
    return result.rowcount


def update_node(
    node_id: int,
    fields: dict,
    *,
    parent_provided: bool = False,
    parent_id: int | None = None,
    tag_ids_provided: bool = False,
    tag_ids: list[int] | None = None,
) -> bool:
    """Update a node's fields, parent, and/or tags atomically. Returns False if node not found."""
    with transactional():
        if not fetch_node(node_id):
            return False
        if 'is_container' in fields and not fields['is_container'] and node_has_children(node_id):
            raise ValueError('cannot set is_container=false on a node that has children')
        if parent_provided and parent_id is not None:
            ensure_parent_is_valid(parent_id, child_id=node_id)
        if fields:
            if update_node_fields(node_id, fields) == 0:
                return False
        if parent_provided:
            set_parent(node_id, parent_id)
        if tag_ids_provided:
            try:
                replace_node_tags(node_id, tag_ids or [])
            except IntegrityError:
                raise ValueError('One or more tag_ids do not exist')
    return True


class _NotFound(Exception):
    pass


def _find_orphan_container(label: str) -> int | None:
    """Return the id of the first existing container with *label*.

    Returns None if no such container exists.
    """
    row = (
        get_db()
        .execute(
            text('SELECT id FROM nodes WHERE label = :label AND is_container = 1 ORDER BY id LIMIT 1'),
            {'label': label},
        )
        .mappings()
        .first()
    )
    return row['id'] if row else None


def _reassign_children_of_deleted_node(node_id: int, parent_id: int | None) -> int:
    """Reassign direct children of *node_id* to *parent_id*.

    If *parent_id* is None or the node has no children, returns 0 immediately.
    Returns the number of reassigned children.
    """
    if parent_id is None:
        return 0

    rows = (
        get_db()
        .execute(
            text('SELECT child_id FROM edges WHERE parent_id = :id ORDER BY child_id'),
            {'id': node_id},
        )
        .mappings()
        .all()
    )
    child_ids = [row['child_id'] for row in rows]
    if not child_ids:
        return 0

    for child_id in child_ids:
        get_db().execute(text('DELETE FROM edges WHERE child_id = :id'), {'id': child_id})
        get_db().execute(
            text('INSERT INTO edges (parent_id, child_id) VALUES (:parent_id, :child_id)'),
            {'parent_id': parent_id, 'child_id': child_id},
        )

    return len(child_ids)


def delete_node(node_id: int) -> tuple[int, int, int, int] | None:
    """Delete a node and its associated edges and tag associations.

    Children of the deleted node are reassigned to the ORPHAN_LOCATION container
    (read from app config) when that setting is configured; otherwise they are
    left without a parent.

    Returns a (total, edge_count, tag_count, node_count) tuple on success, or
    None if the node does not exist.
    """
    orphan_location = current_app.config.get('ORPHAN_LOCATION')
    orphan_parent_id = None
    if orphan_location:
        orphan_parent_id = _find_orphan_container(orphan_location)
        if orphan_parent_id is None:
            orphan_parent_id = create_node(orphan_location, None, True)

    # If the node being deleted is itself the orphan container, do not attempt
    # to re-parent its children there — they will be left without a parent instead.
    if orphan_parent_id == node_id:
        orphan_parent_id = None

    try:
        with transactional() as conn:
            reassigned = _reassign_children_of_deleted_node(node_id, orphan_parent_id)
            edge_count = reassigned
            object_count = reassigned

            result = conn.execute(text('DELETE FROM edges WHERE parent_id = :id'), {'id': node_id})
            object_count += result.rowcount
            edge_count += result.rowcount
            logger.debug('Deleted %d edges where %s is the parent.', result.rowcount, node_id)

            result = conn.execute(text('DELETE FROM edges WHERE child_id = :id'), {'id': node_id})
            object_count += result.rowcount
            edge_count += result.rowcount
            logger.debug('Deleted %d edges where %s is the child.', result.rowcount, node_id)

            # Delete tag associations
            result = conn.execute(text('DELETE FROM tag_node WHERE node_id = :node_id'), {'node_id': node_id})
            object_count += result.rowcount
            tag_count = result.rowcount
            logger.debug('Deleted %d tags associated with %s.', result.rowcount, node_id)

            # Delete the node itself
            result = conn.execute(text('DELETE FROM nodes WHERE id = :id'), {'id': node_id})
            if result.rowcount == 0:
                raise _NotFound
            object_count += result.rowcount

            return object_count, edge_count, tag_count, result.rowcount
    except _NotFound:
        return None


# --------------------------------------------------------------------
# Tag helpers
# --------------------------------------------------------------------


def fetch_tag(tag_id: int) -> RowMapping | None:
    """Return the tags row for *tag_id*, or None if it does not exist."""
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
    """Return the total number of tags."""
    return get_db().execute(text('SELECT COUNT(*) FROM tags')).scalar() or 0


def fetch_tags_page(limit: int, offset: int) -> Sequence[RowMapping]:
    """Return a page of tag rows ordered by name."""
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
    """Return all node rows tagged with *tag_id*, ordered by node id."""
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
    """Insert a new tag with *name* and return its id. Raises ValueError on duplicate name."""
    tag_id = new_id()
    try:
        with transactional():
            get_db().execute(text('INSERT INTO tags (id, name) VALUES (:id, :name)'), {'id': tag_id, 'name': name})
    except IntegrityError:
        raise ValueError(f"Tag with name '{name}' already exists")
    return tag_id


def update_tag(tag_id: int, name: str) -> int:
    """Rename *tag_id* to *name*. Returns rowcount; raises ValueError on duplicate name."""
    try:
        with transactional():
            result = get_db().execute(
                text('UPDATE tags SET name = :name, updated_at = CURRENT_TIMESTAMP WHERE id = :id'),
                {'name': name, 'id': tag_id},
            )
    except IntegrityError:
        raise ValueError(f"Tag with name '{name}' already exists")
    return result.rowcount


def delete_tag(tag_id: int) -> tuple[int, int] | None:
    """Deletes a tag and its node associations. Returns (total, node_count) or None if not found."""
    try:
        with transactional() as conn:
            result = conn.execute(text('DELETE FROM tag_node WHERE tag_id = :tag_id'), {'tag_id': tag_id})
            node_count = result.rowcount
            logger.debug('Deleted %d node associations for tag %d.', node_count, tag_id)

            result = conn.execute(text('DELETE FROM tags WHERE id = :id'), {'id': tag_id})
            if result.rowcount == 0:
                raise _NotFound
            tag_count = result.rowcount
            logger.debug('Deleted tag %d.', tag_id)

            return node_count + tag_count, node_count
    except _NotFound:
        return None


# --------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------


def get_user(username: str) -> RowMapping | None:
    """Return the users row for *username*, or None if it does not exist."""
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

    Always runs full scrypt verification to prevent timing attacks.
    """
    row = get_user(username)
    stored_hash = row['password_hash'] if row else _DUMMY_HASH
    try:
        valid = verify_password_hash(password, stored_hash)
    except Exception as e:
        valid = False
        logger.error("Error trying to verify %s's password: %s: %s", username, e.__class__.__name__, e)
    if not valid or row is None:
        return None
    return row


def update_user_last_login(user_id: int) -> None:
    """Update last_login_at to the current timestamp for *user_id*."""
    get_db().execute(
        text('UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = :id'),
        {'id': user_id},
    )


def create_user_session(user_id: int) -> str:
    """Update last_login_at, insert a new token, and return the raw token (only exposure)."""
    token = generate_token()
    lifetime_days = current_app.config['SESSION_LIFETIME_DAYS']
    expires_at = datetime.now(timezone.utc) + timedelta(days=lifetime_days)
    with transactional():
        update_user_last_login(user_id)
        get_db().execute(
            text('INSERT INTO tokens (id, user_id, token_hash, token_suffix, expires_at) VALUES (:id, :user_id, :token_hash, :token_suffix, :expires_at)'),
            {'id': new_id(), 'user_id': user_id, 'token_hash': hash_token(token), 'token_suffix': token[-4:], 'expires_at': expires_at},
        )
    return token


def revoke_token(token_id: int) -> None:
    """Delete the token row identified by *token_id*."""
    with transactional():
        get_db().execute(
            text('DELETE FROM tokens WHERE id = :id'),
            {'id': token_id},
        )
