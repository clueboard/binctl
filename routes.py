from __future__ import annotations

import logging

from flask import Response, jsonify, request
from werkzeug.exceptions import BadRequest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db import (
    ensure_parent_is_valid,
    fetch_children,
    fetch_node,
    fetch_parent_id,
    fetch_tags_for_node,
    get_db,
    iso,
    node_row_to_dict,
    replace_node_tags,
    set_parent,
    transactional,
)
from web import error

logger = logging.getLogger(__name__)

_NODE_PATCH_ALLOWED_FIELDS = {'label', 'description', 'is_container'}


def _parse_json_body() -> dict:
    """Return parsed JSON body, or raise 400 on malformed JSON / missing body."""
    data = request.get_json(force=True, silent=False)
    if data is None:
        raise BadRequest('Request body must be valid JSON')
    return data


# Tag endpoints
def get_tags_list() -> Response:
    db = get_db()
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return error(400, 'limit and offset must be integers')
    if limit < 1 or limit > 1000:
        return error(400, 'limit must be between 1 and 1000')
    if offset < 0:
        return error(400, 'offset must be non-negative')

    total = db.execute(text('SELECT COUNT(*) FROM tags')).scalar()
    stmt = text(
        """
        SELECT id, name, created_at, updated_at
        FROM tags
        ORDER BY name
        LIMIT :limit OFFSET :offset
        """
    )
    rows = db.execute(stmt, {'limit': limit, 'offset': offset}).mappings().all()

    return jsonify(
        {
            'total': total,
            'limit': limit,
            'offset': offset,
            'items': [
                {
                    'id': r['id'],
                    'name': r['name'],
                    'created_at': iso(r['created_at']),
                    'updated_at': iso(r['updated_at']),
                }
                for r in rows
            ],
        }
    )


def get_tag_detail(tag_id: int) -> Response:
    db = get_db()
    tag_stmt = text(
        """
        SELECT id, name, created_at, updated_at
        FROM tags
        WHERE id = :id
        """
    )
    tag = db.execute(tag_stmt, {'id': tag_id}).mappings().first()

    if not tag:
        return error(404, 'Tag not found')

    nodes_stmt = text(
        """
        -- tag_node is the join table linking tags to nodes (many-to-many)
        -- join to nodes to retrieve full node fields for each association
        SELECT n.id, n.label, n.description, n.is_container,
               n.created_at, n.updated_at
        FROM tag_node tn
        JOIN nodes n ON n.id = tn.node_id
        WHERE tn.tag_id = :id
        ORDER BY n.id
        """
    )
    nodes = db.execute(nodes_stmt, {'id': tag_id}).mappings().all()

    return jsonify(
        {
            'id': tag['id'],
            'name': tag['name'],
            'created_at': iso(tag['created_at']),
            'updated_at': iso(tag['updated_at']),
            'nodes': [node_row_to_dict(n) for n in nodes],
        }
    )


def post_tag_create() -> Response:
    data = _parse_json_body()
    name = data.get('name')

    if not name:
        return error(400, 'Missing required field: name')
    if len(name) > 255:
        return error(400, 'name must be 255 characters or fewer')

    try:
        with transactional() as db:
            result = db.execute(
                text(
                    """
                    INSERT INTO tags (name)
                    VALUES (:name)
                    """
                ),
                {'name': name},
            )
            tag_id = result.lastrowid
    except IntegrityError:
        return error(409, f"Tag with name '{name}' already exists")
    tag = (
        db.execute(
            text(
                """
            SELECT id, name, created_at, updated_at
            FROM tags
            WHERE id = :id
            """
            ),
            {'id': tag_id},
        )
        .mappings()
        .first()
    )

    resp = jsonify(
        {
            'id': tag['id'],
            'name': tag['name'],
            'created_at': iso(tag['created_at']),
            'updated_at': iso(tag['updated_at']),
        }
    )
    resp.status_code = 201

    return resp


def patch_tag_update(tag_id: int) -> Response:
    data = _parse_json_body()
    name = data.get('name')

    if not name:
        return error(400, 'Missing required field: name')
    if len(name) > 255:
        return error(400, 'name must be 255 characters or fewer')

    try:
        with transactional() as db:
            result = db.execute(
                text(
                    """
                    UPDATE tags
                    SET name = :name
                    WHERE id = :id
                    """
                ),
                {'name': name, 'id': tag_id},
            )
            if result.rowcount == 0:
                return error(404, 'Tag not found')
    except IntegrityError:
        return error(409, f"Tag with name '{name}' already exists")

    tag = (
        db.execute(
            text(
                """
            SELECT id, name, created_at, updated_at
            FROM tags
            WHERE id = :id
            """
            ),
            {'id': tag_id},
        )
        .mappings()
        .first()
    )

    return jsonify(
        {
            'id': tag['id'],
            'name': tag['name'],
            'created_at': iso(tag['created_at']),
            'updated_at': iso(tag['updated_at']),
        }
    )


# Node endpoints
def get_nodes_list() -> Response:
    db = get_db()
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return error(400, 'limit and offset must be integers')
    if limit < 1 or limit > 1000:
        return error(400, 'limit must be between 1 and 1000')
    if offset < 0:
        return error(400, 'offset must be non-negative')

    total = db.execute(text('SELECT COUNT(*) FROM nodes')).scalar()
    stmt = text(
        """
        SELECT id, label, description, is_container, created_at, updated_at
        FROM nodes
        ORDER BY id
        LIMIT :limit OFFSET :offset
        """
    )
    rows = db.execute(stmt, {'limit': limit, 'offset': offset}).mappings().all()

    return jsonify({'total': total, 'limit': limit, 'offset': offset, 'items': [node_row_to_dict(r) for r in rows]})


def get_node_detail(node_id: int) -> Response:
    row = fetch_node(node_id)

    if not row:
        return error(404, 'Node not found')

    parent_id = fetch_parent_id(node_id)
    children = fetch_children(node_id)
    tags = fetch_tags_for_node(node_id)

    node = node_row_to_dict(row)
    node['parent_id'] = parent_id
    node['children'] = children
    node['tags'] = tags

    return jsonify(node)


def post_node_create() -> Response:
    data = _parse_json_body()
    label = data.get('label')

    if label is None:
        return error(400, 'Missing required field: label')
    if not label:
        return error(400, 'label cannot be empty')
    if len(label) > 255:
        return error(400, 'label must be 255 characters or fewer')

    description = data.get('description')
    if description is not None and description == '':
        return error(400, 'description cannot be empty')
    is_container = bool(data.get('is_container', False))
    parent_id = data.get('parent_id')
    tag_ids = data.get('tag_ids') or []

    try:
        if parent_id is not None:
            ensure_parent_is_valid(parent_id)

        with transactional() as db:
            result = db.execute(
                text(
                    """
                    INSERT INTO nodes (label, description, is_container)
                    VALUES (:label, :description, :is_container)
                    """
                ),
                {
                    'label': label,
                    'description': description,
                    'is_container': is_container,
                },
            )
            node_id = result.lastrowid

            # Parent relationship
            if parent_id is not None:
                set_parent(node_id, parent_id)

            # Tags
            if tag_ids:
                replace_node_tags(node_id, tag_ids)

    except ValueError as ve:
        return error(400, str(ve))

    except SQLAlchemyError:
        logger.exception('Database error in post_node_create')
        return error(500, 'Internal server error')

    # Fetch full node representation
    row = fetch_node(node_id)
    parent_id = fetch_parent_id(node_id)
    children = fetch_children(node_id)
    tags = fetch_tags_for_node(node_id)

    node = node_row_to_dict(row)
    node['parent_id'] = parent_id
    node['children'] = children
    node['tags'] = tags

    resp = jsonify(node)
    resp.status_code = 201

    return resp


def patch_node_update(node_id: int) -> Response:
    data = _parse_json_body()
    row = fetch_node(node_id)
    fields = {}

    if not row:
        return error(404, 'Node not found')

    if 'label' in data:
        if not data['label']:
            return error(400, 'label cannot be empty')
        if len(data['label']) > 255:
            return error(400, 'label must be 255 characters or fewer')
        fields['label'] = data['label']

    if 'description' in data:
        if data['description'] == '':
            return error(400, 'description cannot be empty')
        fields['description'] = data['description']

    if 'is_container' in data:
        fields['is_container'] = bool(data['is_container'])

    parent_provided = 'parent_id' in data
    parent_id = data.get('parent_id') if parent_provided else None

    tag_ids_provided = 'tag_ids' in data
    tag_ids = data.get('tag_ids') or []

    try:
        if parent_provided and parent_id is not None:
            ensure_parent_is_valid(parent_id, child_id=node_id)

        with transactional() as db:
            # Update node core fields
            if fields:
                if not fields.keys() <= _NODE_PATCH_ALLOWED_FIELDS:
                    return error(400, 'Invalid field names')
                sets = ', '.join(f'{k} = :{k}' for k in fields.keys())
                params = dict(fields)
                params['id'] = node_id
                stmt = text(
                    f"""
                    UPDATE nodes
                    SET {sets}
                    WHERE id = :id
                    """
                )
                db.execute(stmt, params)

            # Parent relationship
            if parent_provided:
                set_parent(node_id, parent_id)

            # Tags
            if tag_ids_provided:
                replace_node_tags(node_id, tag_ids)

    except ValueError as ve:
        logger.error(f'Validation error in patch_node_update for node {node_id}: {ve}')
        return error(400, str(ve))

    except SQLAlchemyError as e:
        logger.exception(f'Database error in patch_node_update for node {node_id}: {e}')
        return error(500, 'Internal server error')

    # Return updated representation
    row = fetch_node(node_id)
    parent_id = fetch_parent_id(node_id)
    children = fetch_children(node_id)
    tags = fetch_tags_for_node(node_id)

    node = node_row_to_dict(row)
    node['parent_id'] = parent_id
    node['children'] = children
    node['tags'] = tags

    return jsonify(node)
