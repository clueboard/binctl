import logging

from flask import Response, jsonify, request
from werkzeug.exceptions import BadRequest

from db import base62
from db.flask import (
    count_nodes,
    count_tags,
    create_node,
    create_tag,
    delete_node,
    delete_tag,
    fetch_children,
    fetch_node,
    fetch_nodes_for_tag,
    fetch_nodes_page,
    fetch_parent_id,
    fetch_tag,
    fetch_tags_for_node,
    fetch_tags_page,
    node_row_to_dict,
    tag_row_to_dict,
    update_node,
    update_tag,
)
from web import error

logger = logging.getLogger(__name__)


def _decode_id(raw: str, name: str) -> int:
    try:
        return base62.decode(raw)
    except (TypeError, ValueError):
        raise BadRequest(f'invalid {name}: {raw!r}')


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


def get_tag_detail(tag_id: str) -> Response:
    tag_id_int = _decode_id(tag_id, 'tag_id')
    tag = fetch_tag(tag_id_int)
    if not tag:
        return error(404, 'Tag not found')

    nodes = fetch_nodes_for_tag(tag_id_int)

    return jsonify(
        {
            **tag_row_to_dict(tag),
            'nodes': [node_row_to_dict(n) for n in nodes],
        }
    )


def post_tag_create() -> Response:
    data = _parse_json_body()
    name = data['name']

    try:
        tag_id = create_tag(name)
    except ValueError as e:
        return error(409, str(e))

    tag = fetch_tag(tag_id)
    if tag is None:
        logger.error('fetch_tag returned None after create_tag succeeded for name=%r', name)
        return error(500, 'Internal server error')
    resp = jsonify(tag_row_to_dict(tag))
    resp.status_code = 201
    return resp


def delete_tag_endpoint(tag_id: str) -> Response:
    delete_op = delete_tag(_decode_id(tag_id, 'tag_id'))

    if delete_op is None:
        return error(404, 'Tag not found')

    total, node_count = delete_op

    return jsonify({'deleted': {'total': total, 'associations': node_count}})


def patch_tag_update(tag_id: str) -> Response:
    tag_id_int = _decode_id(tag_id, 'tag_id')
    data = _parse_json_body()
    name = data['name']

    try:
        rowcount = update_tag(tag_id_int, name)
    except ValueError as e:
        return error(409, str(e))

    if rowcount == 0:
        return error(404, 'Tag not found')
    tag = fetch_tag(tag_id_int)
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


def get_node_detail(node_id: str) -> Response:
    node_id_int = _decode_id(node_id, 'node_id')
    row = fetch_node(node_id_int)

    if not row:
        return error(404, 'Node not found')

    parent_id_int = fetch_parent_id(node_id_int)
    children = fetch_children(node_id_int)
    tags = fetch_tags_for_node(node_id_int)

    node = node_row_to_dict(row)
    node['parent_id'] = base62.encode(parent_id_int) if parent_id_int is not None else None
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
    if description == '':
        return error(400, 'description cannot be empty')
    is_container = bool(data.get('is_container', False))
    raw_parent_id = data.get('parent_id')
    raw_tag_ids = data.get('tag_ids') or []

    try:
        parent_id_int = _decode_id(raw_parent_id, 'parent_id') if raw_parent_id is not None else None
        tag_id_ints = [_decode_id(t, 'tag_ids') for t in raw_tag_ids]
    except BadRequest as e:
        return error(400, e.description)

    try:
        node_id = create_node(label, description, is_container, parent_id=parent_id_int, tag_ids=tag_id_ints)
    except ValueError as ve:
        logger.error(f'Validation error in post_node_create: {ve}')
        return error(400, str(ve))

    # Fetch full node representation
    row = fetch_node(node_id)
    if row is None:
        logger.error('fetch_node returned None after create_node succeeded for node_id=%d', node_id)
        return error(500, 'Internal server error')
    parent_id_int = fetch_parent_id(node_id)
    children = fetch_children(node_id)
    tags = fetch_tags_for_node(node_id)

    node = node_row_to_dict(row)
    node['parent_id'] = base62.encode(parent_id_int) if parent_id_int is not None else None
    node['children'] = children
    node['tags'] = tags

    resp = jsonify(node)
    resp.status_code = 201

    return resp


def patch_node_update(node_id: str) -> Response:
    node_id_int = _decode_id(node_id, 'node_id')
    data = _parse_json_body()
    fields = {}

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
    raw_parent_id = data.get('parent_id') if parent_provided else None

    tag_ids_provided = 'tag_ids' in data
    raw_tag_ids = data.get('tag_ids') or []

    try:
        parent_id_int = _decode_id(raw_parent_id, 'parent_id') if raw_parent_id is not None else None
        tag_id_ints = [_decode_id(t, 'tag_ids') for t in raw_tag_ids]
    except BadRequest as e:
        return error(400, e.description)

    try:
        found = update_node(
            node_id_int,
            fields,
            parent_provided=parent_provided,
            parent_id=parent_id_int,
            tag_ids_provided=tag_ids_provided,
            tag_ids=tag_id_ints,
        )
    except ValueError as ve:
        logger.error(f'Validation error in patch_node_update for node {node_id}: {ve}')
        return error(400, str(ve))

    if not found:
        return error(404, 'Node not found')

    # Return updated representation
    row = fetch_node(node_id_int)
    if row is None:
        logger.error('fetch_node returned None after update succeeded for node_id=%d', node_id_int)
        return error(500, 'Internal server error')
    parent_id_int = fetch_parent_id(node_id_int)
    children = fetch_children(node_id_int)
    tags = fetch_tags_for_node(node_id_int)

    node = node_row_to_dict(row)
    node['parent_id'] = base62.encode(parent_id_int) if parent_id_int is not None else None
    node['children'] = children
    node['tags'] = tags

    return jsonify(node)


def delete_node_endpoint(node_id: str) -> Response:
    delete_op = delete_node(_decode_id(node_id, 'node_id'))

    if delete_op is None:
        return error(404, 'Node not found')

    object_count, edge_count, tag_count, node_count = delete_op

    return jsonify(
        {
            'deleted': {
                'total': object_count,
                'edges': edge_count,
                'tags': tag_count,
                'nodes': node_count,
            },
        }
    )
