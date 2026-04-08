import logging

from flask import Response, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import BadRequest

from db.flask import (
    count_nodes,
    count_tags,
    create_node,
    create_tag,
    ensure_parent_is_valid,
    fetch_children,
    fetch_node,
    fetch_nodes_for_tag,
    fetch_nodes_page,
    fetch_parent_id,
    fetch_tag,
    fetch_tags_for_node,
    fetch_tags_page,
    node_has_children,
    node_row_to_dict,
    replace_node_tags,
    set_parent,
    tag_row_to_dict,
    transactional,
    update_node_fields,
    update_tag,
)
from web import error

logger = logging.getLogger(__name__)


def _parse_json_body() -> dict:
    """Return parsed JSON body, or raise 400 on malformed JSON / missing body."""
    data = request.get_json(force=True, silent=False)
    if data is None:
        raise BadRequest('Request body must be valid JSON')
    return data


# Tag endpoints
def get_tags_list() -> Response:
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return error(400, 'limit and offset must be integers')
    if limit < 1 or limit > 1000:
        return error(400, 'limit must be between 1 and 1000')
    if offset < 0:
        return error(400, 'offset must be non-negative')

    total = count_tags()
    rows = fetch_tags_page(limit, offset)

    return jsonify(
        {
            'total': total,
            'limit': limit,
            'offset': offset,
            'items': [tag_row_to_dict(r) for r in rows],
        }
    )


def get_tag_detail(tag_id: int) -> Response:
    tag = fetch_tag(tag_id)
    if not tag:
        return error(404, 'Tag not found')

    nodes = fetch_nodes_for_tag(tag_id)

    return jsonify(
        {
            **tag_row_to_dict(tag),
            'nodes': [node_row_to_dict(n) for n in nodes],
        }
    )


def post_tag_create() -> Response:
    data = _parse_json_body()
    name = data.get('name')

    if name is None:
        return error(400, 'Missing required field: name')
    if not name:
        return error(400, 'Required field cannot be empty: name')
    if len(name) > 255:
        return error(400, 'name must be 255 characters or fewer')

    try:
        with transactional():
            tag_id = create_tag(name)
            tag = fetch_tag(tag_id)
    except IntegrityError:
        return error(409, f"Tag with name '{name}' already exists")

    if tag is None:
        logger.error('fetch_tag returned None after create_tag succeeded for name=%r', name)
        return error(500, 'Internal server error')
    resp = jsonify(tag_row_to_dict(tag))
    resp.status_code = 201
    return resp


def patch_tag_update(tag_id: int) -> Response:
    data = _parse_json_body()
    name = data.get('name')

    if name is None:
        return error(400, 'Missing required field: name')
    if not name:
        return error(400, 'Required field cannot be empty: name')
    if len(name) > 255:
        return error(400, 'name must be 255 characters or fewer')

    try:
        with transactional():
            rowcount = update_tag(tag_id, name)
            if rowcount == 0:
                return error(404, 'Tag not found')
            tag = fetch_tag(tag_id)
    except IntegrityError:
        return error(409, f"Tag with name '{name}' already exists")

    if tag is None:
        logger.error('fetch_tag returned None after update_tag succeeded for tag_id=%d', tag_id)
        return error(500, 'Internal server error')
    return jsonify(tag_row_to_dict(tag))


# Node endpoints
def get_nodes_list() -> Response:
    try:
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return error(400, 'limit and offset must be integers')
    if limit < 1 or limit > 1000:
        return error(400, 'limit must be between 1 and 1000')
    if offset < 0:
        return error(400, 'offset must be non-negative')

    total = count_nodes()
    rows = fetch_nodes_page(limit, offset)

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
        return error(400, 'Required field cannot be empty: label')
    if len(label) > 255:
        return error(400, 'label must be 255 characters or fewer')

    description = data.get('description')
    if description is not None and description == '':
        return error(400, 'description cannot be empty')
    is_container = bool(data.get('is_container', False))
    parent_id = data.get('parent_id')
    tag_ids = data.get('tag_ids') or []

    try:
        with transactional():
            if parent_id is not None:
                ensure_parent_is_valid(parent_id)

            node_id = create_node(label, description, is_container)

            if parent_id is not None:
                set_parent(node_id, parent_id)

            if tag_ids:
                replace_node_tags(node_id, tag_ids)

    except ValueError as ve:
        logger.error(f'Validation error in post_node_create: {ve}')
        return error(400, str(ve))

    except IntegrityError:
        return error(400, 'One or more tag_ids do not exist')

    except SQLAlchemyError:
        logger.exception('Database error in post_node_create')
        return error(500, 'Internal server error')

    # Fetch full node representation
    row = fetch_node(node_id)
    if row is None:
        logger.error('fetch_node returned None after create_node succeeded for node_id=%d', node_id)
        return error(500, 'Internal server error')
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
        value = bool(data['is_container'])
        if not value and node_has_children(node_id):
            return error(400, 'cannot set is_container=false on a node that has children')
        fields['is_container'] = value

    parent_provided = 'parent_id' in data
    parent_id = data.get('parent_id') if parent_provided else None

    tag_ids_provided = 'tag_ids' in data
    tag_ids = data.get('tag_ids') or []

    try:
        with transactional():
            if parent_provided and parent_id is not None:
                ensure_parent_is_valid(parent_id, child_id=node_id)

            if fields:
                update_node_fields(node_id, fields)

            if parent_provided:
                set_parent(node_id, parent_id)

            if tag_ids_provided:
                replace_node_tags(node_id, tag_ids)

    except ValueError as ve:
        logger.error(f'Validation error in patch_node_update for node {node_id}: {ve}')
        return error(400, str(ve))

    except IntegrityError:
        return error(400, 'One or more tag_ids do not exist')

    except SQLAlchemyError as e:
        logger.exception(f'Database error in patch_node_update for node {node_id}: {e}')
        return error(500, 'Internal server error')

    # Return updated representation
    row = fetch_node(node_id)
    if row is None:
        logger.error('fetch_node returned None after update succeeded for node_id=%d', node_id)
        return error(500, 'Internal server error')
    parent_id = fetch_parent_id(node_id)
    children = fetch_children(node_id)
    tags = fetch_tags_for_node(node_id)

    node = node_row_to_dict(row)
    node['parent_id'] = parent_id
    node['children'] = children
    node['tags'] = tags

    return jsonify(node)
