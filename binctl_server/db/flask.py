import logging
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from flask import current_app, g
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping
from sqlalchemy.exc import IntegrityError

from ..auth import generate_token, hash_password, hash_token, verify_password_hash
from . import base62
from .engine import engine
from .events import append_event
from .id_gen import new_id

logger = logging.getLogger(__name__)

# Pre-computed scrypt hash used when the username is not found, so verify_password
# always does full key-stretching regardless of whether the username exists.
# Prevents timing attacks that distinguish "unknown user" from "wrong password".
_DUMMY_HASH = hash_password('dummy')


def get_db() -> Connection:
    """Return the per-request SQLAlchemy connection, opening it on first access."""
    if 'db' not in g:
        g.db = engine.connect()
    return g.db


@contextmanager
def transactional() -> Iterator[Connection]:
    """Wrap the Flask-g connection in a nestable transaction scope."""
    conn = get_db()
    depth = g.get('transaction_depth', 0)
    g.transaction_depth = depth + 1
    owns_transaction = depth == 0 and not g.get('managed_transaction')
    try:
        yield conn
        if owns_transaction:
            conn.commit()
    except Exception:
        if owns_transaction:
            conn.rollback()
        raise
    finally:
        if depth:
            g.transaction_depth = depth
        else:
            g.pop('transaction_depth', None)


def idempotency_lock_enabled() -> bool:
    return bool(get_db().execute(text('SELECT enabled FROM idempotency_lock WHERE id = 1')).scalar_one())


def set_idempotency_lock(enabled: bool) -> None:
    conn = get_db()
    conn.execute(text('UPDATE idempotency_lock SET enabled = :enabled WHERE id = 1'), {'enabled': db_bool(enabled)})
    conn.commit()


def fetch_idempotency_response(user_id: int, key: str) -> RowMapping | None:
    return (
        get_db()
        .execute(
            text('SELECT request_hash, response_code, response_body FROM idempotency_keys WHERE user_id = :user_id AND key_value = :key'),
            {'user_id': user_id, 'key': key},
        )
        .mappings()
        .first()
    )


def save_idempotency_response(user_id: int, key: str, request_hash: str, response_code: int, response_body: str) -> None:
    get_db().execute(
        text(
            'INSERT INTO idempotency_keys '
            '(user_id, key_value, request_hash, response_code, response_body) '
            'VALUES (:user_id, :key, :request_hash, :response_code, :response_body)'
        ),
        {'user_id': user_id, 'key': key, 'request_hash': request_hash, 'response_code': response_code, 'response_body': response_body},
    )


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


def db_bool(value: bool | int) -> int:
    """Represent a boolean for the shared INTEGER-backed SQL schema."""
    return 1 if value else 0


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
    """Return full canonical representations of the direct child nodes."""
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
    children = []
    for row in rows:
        child = node_row_to_dict(row)
        child['tags'] = fetch_tags_for_node(row['id'])
        children.append(child)
    return children


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


def fetch_tags_for_node(node_id: int) -> list[str]:
    """Return tag names attached to *node_id*."""
    rows = (
        get_db()
        .execute(
            text(
                """
            SELECT t.name
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
    return [r['name'] for r in rows]


def fetch_node_representation(node_id: int) -> dict | None:
    """Return the canonical event representation of a node."""
    row = fetch_node(node_id)
    if row is None:
        return None
    node = node_row_to_dict(row)
    parent_id = fetch_parent_id(node_id)
    node['parent_id'] = base62.encode(parent_id) if parent_id is not None else None
    node['children'] = fetch_children(node_id)
    node['tags'] = fetch_tags_for_node(node_id)
    return node


def _append_node_event(event_type: str, operation: str, node_id: int) -> None:
    """Append a node event using its current canonical representation."""
    node = fetch_node_representation(node_id)
    if node is not None:
        append_event(get_db(), event_type, {'resource_type': 'node', 'operation': operation, 'resource': node})


def _append_parent_updates(parent_ids: set[int | None], *, exclude: set[int] | None = None) -> None:
    """Append one update for each existing parent whose embedded children changed."""
    excluded = exclude or set()
    for parent_id in sorted(parent_id for parent_id in parent_ids if parent_id is not None and parent_id not in excluded):
        _append_node_event('node.updated', 'updated', parent_id)


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


def _validate_tag_name(name: str) -> None:
    if not name:
        raise ValueError('tag names cannot be empty')
    if len(name) > 255:
        raise ValueError('tag names must be 255 characters or fewer')
    if re.fullmatch(r'[a-z-]+', name) is None:
        raise ValueError('tag names may contain only lowercase letters and hyphens')


def ensure_tag(name: str) -> int:
    """Return the internal ID for *name*, creating the tag if needed."""
    _validate_tag_name(name)
    conn = get_db()
    row = conn.execute(text('SELECT id FROM tags WHERE name = :name'), {'name': name}).mappings().first()
    if row:
        return row['id']
    for _ in range(5):
        tag_id = new_id()
        try:
            with conn.begin_nested():
                conn.execute(text('INSERT INTO tags (id, name) VALUES (:id, :name)'), {'id': tag_id, 'name': name})
            tag = fetch_tag(name)
            assert tag is not None
            append_event(conn, 'tag.created', {'resource_type': 'tag', 'operation': 'created', 'resource': tag_row_to_dict(tag)})
            return tag_id
        except IntegrityError:
            row = conn.execute(text('SELECT id FROM tags WHERE name = :name'), {'name': name}).mappings().first()
            if row:
                return row['id']
    raise RuntimeError('could not allocate a unique tag ID')


def replace_node_tags(node_id: int, tag_names: list[str]) -> None:
    """Replace all tag associations, creating missing tag names."""
    conn = get_db()
    conn.execute(text('DELETE FROM tag_node WHERE node_id = :node_id'), {'node_id': node_id})
    tag_ids = [ensure_tag(name) for name in dict.fromkeys(tag_names)]
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


def fetch_graph_snapshot() -> tuple[list[dict], int]:
    """Return every node and its event cursor from one consistent query."""
    rows = (
        get_db()
        .execute(
            text(
                """
            SELECT s.value AS event_cursor,
                   n.id, n.label, n.description, n.is_container,
                   n.created_at, n.updated_at, e.parent_id, t.name AS tag_name
            FROM event_sequence s
            LEFT JOIN nodes n ON 1 = 1
            LEFT JOIN edges e ON e.child_id = n.id
            LEFT JOIN tag_node tn ON tn.node_id = n.id
            LEFT JOIN tags t ON t.id = tn.tag_id
            WHERE s.id = 1
            ORDER BY n.id, t.name
            """
            )
        )
        .mappings()
        .all()
    )

    nodes: list[dict] = []
    current_id = None
    cursor = int(rows[0]['event_cursor'])
    for row in rows:
        if row['id'] is None:
            continue
        if row['id'] != current_id:
            node = node_row_to_dict(row)
            node['tags'] = []
            nodes.append(node)
            current_id = row['id']
        if row['tag_name'] is not None:
            nodes[-1]['tags'].append(row['tag_name'])
    return nodes, cursor


def create_node(
    label: str,
    description: str | None,
    is_container: bool,
    *,
    node_id: int | None = None,
    parent_id: int | None = None,
    tags: list[str] | None = None,
) -> int:
    """Insert a new node and return its id.

    Optionally assigns a parent and attaches tags in the same transaction.
    """
    with transactional():
        generated = node_id is None
        for attempt in range(5):
            candidate = new_id() if generated else node_id
            try:
                with get_db().begin_nested():
                    get_db().execute(
                        text('INSERT INTO nodes (id, label, description, is_container) VALUES (:id, :label, :description, :is_container)'),
                        {'id': candidate, 'label': label, 'description': description, 'is_container': db_bool(is_container)},
                    )
                node_id = candidate
                break
            except IntegrityError:
                if not generated:
                    assert candidate is not None
                    raise ValueError(f"Node with id '{base62.encode(candidate)}' already exists")
                if attempt == 4:
                    raise RuntimeError('could not allocate a unique node ID')
        assert node_id is not None
        if parent_id is not None:
            ensure_parent_is_valid(parent_id)
            set_parent(node_id, parent_id)
        if tags:
            replace_node_tags(node_id, tags)
        _append_node_event('node.created', 'created', node_id)
        _append_parent_updates({parent_id})
    return node_id


_UPDATABLE_NODE_FIELDS = frozenset({'label', 'description', 'is_container'})


def update_node_fields(node_id: int, fields: dict) -> int:
    """Apply a subset of updatable fields to *node_id*. Returns rowcount."""
    invalid = fields.keys() - _UPDATABLE_NODE_FIELDS
    if invalid:
        raise ValueError(f'non-updatable node fields: {invalid}')
    set_clause = ', '.join(f'{k} = :{k}' for k in fields)
    parameters = {**fields, 'id': node_id}
    if 'is_container' in parameters:
        parameters['is_container'] = db_bool(parameters['is_container'])
    result = get_db().execute(
        text(f'UPDATE nodes SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = :id'),
        parameters,
    )
    return result.rowcount


def update_node(
    node_id: int,
    fields: dict,
    *,
    parent_provided: bool = False,
    parent_id: int | None = None,
    tags_provided: bool = False,
    tags: list[str] | None = None,
) -> bool:
    """Update a node's fields, parent, and/or tags atomically. Returns False if node not found."""
    with transactional():
        if not fetch_node(node_id):
            return False
        old_parent_id = fetch_parent_id(node_id)
        if 'is_container' in fields and not fields['is_container'] and node_has_children(node_id):
            raise ValueError('cannot set is_container=false on a node that has children')
        if parent_provided and parent_id is not None:
            ensure_parent_is_valid(parent_id, child_id=node_id)
        if fields:
            if update_node_fields(node_id, fields) == 0:
                return False
        if parent_provided:
            set_parent(node_id, parent_id)
        if tags_provided:
            replace_node_tags(node_id, tags or [])
        new_parent_id = fetch_parent_id(node_id)
        _append_node_event('node.updated', 'updated', node_id)
        _append_parent_updates({old_parent_id, new_parent_id})
    return True


def put_node(node_id: int, label: str, description: str | None, is_container: bool, parent_id: int | None, tags: list[str]) -> bool:
    """Create or fully replace a node. Return True when created."""
    with transactional():
        created = fetch_node(node_id) is None
        if created:
            create_node(label, description, is_container, node_id=node_id, parent_id=parent_id, tags=tags)
            return True
        if not is_container and node_has_children(node_id):
            raise ValueError('cannot set is_container=false on a node that has children')
        old_parent_id = fetch_parent_id(node_id)
        if parent_id is not None:
            ensure_parent_is_valid(parent_id, child_id=node_id)
        get_db().execute(
            text('UPDATE nodes SET label = :label, description = :description, is_container = :is_container, updated_at = CURRENT_TIMESTAMP WHERE id = :id'),
            {'id': node_id, 'label': label, 'description': description, 'is_container': db_bool(is_container)},
        )
        set_parent(node_id, parent_id)
        replace_node_tags(node_id, tags)
        _append_node_event('node.updated', 'updated', node_id)
        _append_parent_updates({old_parent_id, parent_id})
        return False


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
    try:
        with transactional() as conn:
            deleted_resource = fetch_node_representation(node_id)
            if deleted_resource is None:
                raise _NotFound
            old_parent_id = fetch_parent_id(node_id)
            orphan_location = current_app.config.get('ORPHAN_LOCATION')
            orphan_parent_id = None
            has_children = conn.execute(text('SELECT 1 FROM edges WHERE parent_id = :id LIMIT 1'), {'id': node_id}).first() is not None
            if orphan_location and has_children:
                orphan_parent_id = _find_orphan_container(orphan_location)
                if orphan_parent_id is None:
                    orphan_parent_id = create_node(orphan_location, None, True)

            # Deleting the orphan container itself leaves its children parentless.
            if orphan_parent_id == node_id:
                orphan_parent_id = None

            child_rows = conn.execute(text('SELECT child_id FROM edges WHERE parent_id = :id ORDER BY child_id'), {'id': node_id}).mappings().all()
            child_ids = [row['child_id'] for row in child_rows]
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

            for child_id in child_ids:
                _append_node_event('node.updated', 'updated', child_id)
            _append_parent_updates({old_parent_id, orphan_parent_id}, exclude={node_id})
            append_event(
                conn,
                'node.deleted',
                {
                    'resource_type': 'node',
                    'operation': 'deleted',
                    'resource_id': base62.encode(node_id),
                    'resource': deleted_resource,
                    'deleted': {'total': object_count, 'edges': edge_count, 'tags': tag_count, 'nodes': result.rowcount},
                },
            )
            return object_count, edge_count, tag_count, result.rowcount
    except _NotFound:
        return None


# --------------------------------------------------------------------
# Tag helpers
# --------------------------------------------------------------------


def fetch_tag(name: str) -> RowMapping | None:
    """Return the tag row for *name*, or None if it does not exist."""
    return (
        get_db()
        .execute(
            text('SELECT id, name, created_at, updated_at FROM tags WHERE name = :name'),
            {'name': name},
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


def fetch_nodes_for_tag(name: str) -> Sequence[RowMapping]:
    """Return all node rows tagged with *name*, ordered by node id."""
    return (
        get_db()
        .execute(
            text(
                """
            SELECT n.id, n.label, n.description, n.is_container,
                   n.created_at, n.updated_at
            FROM tag_node tn
            JOIN nodes n ON n.id = tn.node_id
            JOIN tags t ON t.id = tn.tag_id
            WHERE t.name = :name
            ORDER BY n.id
            """
            ),
            {'name': name},
        )
        .mappings()
        .all()
    )


def create_tag(name: str) -> int:
    """Insert a new tag with *name* and return its id. Raises ValueError on duplicate name."""
    _validate_tag_name(name)
    with transactional():
        if fetch_tag(name):
            raise ValueError(f"Tag with name '{name}' already exists")
        return ensure_tag(name)


def update_tag(old_name: str, name: str) -> int:
    """Rename *old_name* to *name*. Returns rowcount; raises on duplicate name."""
    _validate_tag_name(name)
    try:
        with transactional():
            node_rows = (
                get_db()
                .execute(
                    text('SELECT tn.node_id FROM tag_node tn JOIN tags t ON t.id = tn.tag_id WHERE t.name = :name ORDER BY tn.node_id'),
                    {'name': old_name},
                )
                .mappings()
                .all()
            )
            result = get_db().execute(
                text('UPDATE tags SET name = :name, updated_at = CURRENT_TIMESTAMP WHERE name = :old_name'),
                {'name': name, 'old_name': old_name},
            )
            if result.rowcount:
                tag = fetch_tag(name)
                assert tag is not None
                append_event(
                    get_db(),
                    'tag.updated',
                    {'resource_type': 'tag', 'operation': 'updated', 'previous_name': old_name, 'resource': tag_row_to_dict(tag)},
                )
                for row in node_rows:
                    _append_node_event('node.updated', 'updated', row['node_id'])
                _append_parent_updates({fetch_parent_id(row['node_id']) for row in node_rows})
    except IntegrityError:
        raise ValueError(f"Tag with name '{name}' already exists")
    return result.rowcount


def delete_tag(name: str) -> tuple[int, int] | None:
    """Deletes a tag and its node associations. Returns (total, node_count) or None if not found."""
    try:
        with transactional() as conn:
            row = conn.execute(text('SELECT id, name, created_at, updated_at FROM tags WHERE name = :name'), {'name': name}).mappings().first()
            if row is None:
                raise _NotFound
            tag_id = row['id']
            node_rows = conn.execute(text('SELECT node_id FROM tag_node WHERE tag_id = :tag_id ORDER BY node_id'), {'tag_id': tag_id}).mappings().all()
            result = conn.execute(text('DELETE FROM tag_node WHERE tag_id = :tag_id'), {'tag_id': tag_id})
            node_count = result.rowcount
            logger.debug('Deleted %d node associations for tag %d.', node_count, tag_id)

            result = conn.execute(text('DELETE FROM tags WHERE id = :id'), {'id': tag_id})
            if result.rowcount == 0:
                raise _NotFound
            tag_count = result.rowcount
            logger.debug('Deleted tag %d.', tag_id)

            for node_row in node_rows:
                _append_node_event('node.updated', 'updated', node_row['node_id'])
            _append_parent_updates({fetch_parent_id(row['node_id']) for row in node_rows})

            append_event(
                conn,
                'tag.deleted',
                {
                    'resource_type': 'tag',
                    'operation': 'deleted',
                    'resource_id': name,
                    'resource': tag_row_to_dict(row),
                    'deleted': {'total': node_count + tag_count, 'associations': node_count},
                },
            )

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
