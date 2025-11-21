from flask import jsonify, request
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
)
from web import error


# Tag endpoints
def get_tags_list():
    db = get_db()
    stmt = text(
        """
        SELECT id, name, created_at, updated_at
        FROM tags
        ORDER BY name
        """
    )
    rows = db.execute(stmt).mappings().all()

    return jsonify(
        [
            {
                'id': r['id'],
                'name': r['name'],
                'created_at': iso(r['created_at']),
                'updated_at': iso(r['updated_at']),
            }
            for r in rows
        ]
    )


def get_tag_detail(tag_id):
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


def post_tag_create():
    db = get_db()
    data = request.get_json(silent=True) or {}
    name = data.get('name')

    if not name:
        return error(400, 'Missing required field: name')

    try:
        result = db.execute(
            text(
                """
                INSERT INTO tags (name)
                VALUES (:name)
                """
            ),
            {'name': name},
        )

        db.commit()

    except IntegrityError:
        db.rollback()
        return error(409, f"Tag with name '{name}' already exists")

    tag_id = result.lastrowid
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


def post_tag_update(tag_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    name = data.get('name')

    if not name:
        return error(400, 'Missing required field: name')

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
        db.rollback()
        return error(404, 'Tag not found')

    try:
        db.commit()

    except IntegrityError:
        db.rollback()
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
def get_nodes_list():
    db = get_db()
    stmt = text(
        """
        SELECT id, label, description, is_container, created_at, updated_at
        FROM nodes
        ORDER BY id
        """
    )
    rows = db.execute(stmt).mappings().all()

    return jsonify([node_row_to_dict(r) for r in rows])


def get_node_detail(node_id):
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


def post_node_create():
    db = get_db()
    data = request.get_json(silent=True) or {}
    label = data.get('label')

    if not label:
        return error(400, 'Missing required field: label')

    description = data.get('description')
    is_container = bool(data.get('is_container', False))
    parent_id = data.get('parent_id')
    tag_ids = data.get('tag_ids') or []

    if parent_id is not None:
        if err := ensure_parent_is_valid(parent_id):
            return err

    try:
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

        db.commit()

    except ValueError as ve:
        db.rollback()
        return error(400, str(ve))

    except SQLAlchemyError as se:
        db.rollback()
        return error(500, f'Database error: {se}')

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


def post_node_update(node_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    row = fetch_node(node_id)
    fields = {}

    if not row:
        return error(404, 'Node not found')

    if 'label' in data:
        if not data['label']:
            return error(400, 'label cannot be empty')
        fields['label'] = data['label']

    if 'description' in data:
        fields['description'] = data['description']

    if 'is_container' in data:
        fields['is_container'] = bool(data['is_container'])

    parent_provided = 'parent_id' in data
    parent_id = data.get('parent_id') if parent_provided else None

    tag_ids_provided = 'tag_ids' in data
    tag_ids = data.get('tag_ids') or []

    if parent_provided and parent_id is not None:
        if err := ensure_parent_is_valid(parent_id, child_id=node_id):
            return err

    try:
        # Update node core fields
        if fields:
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

        db.commit()

    except ValueError as ve:
        db.rollback()

        return error(400, str(ve))

    except SQLAlchemyError as se:
        db.rollback()

        return error(500, f'Database error: {se}')

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
