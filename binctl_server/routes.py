import hashlib
import json
import logging

import connexion
from flask import Response, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest

from .db import base62
from .db.flask import (
    count_nodes,
    count_tags,
    create_node,
    create_tag,
    delete_node,
    delete_tag,
    fetch_children,
    fetch_graph_snapshot,
    fetch_idempotency_response,
    fetch_node,
    fetch_nodes_for_tag,
    fetch_nodes_page,
    fetch_parent_id,
    fetch_tag,
    fetch_tags_for_node,
    fetch_tags_page,
    get_db,
    idempotency_lock_enabled,
    node_row_to_dict,
    put_node,
    save_idempotency_response,
    set_idempotency_lock,
    tag_row_to_dict,
    update_node,
    update_tag,
)
from .web import error

logger = logging.getLogger(__name__)


def _decode_id(raw: str, name: str) -> int:
    try:
        return base62.decode_id(raw)
    except (TypeError, ValueError):
        raise BadRequest(f'invalid {name}: {raw!r}')


def _parse_json_body() -> dict:
    """Return parsed JSON body, or raise 400 on malformed JSON / missing body."""
    data = request.get_json(force=True, silent=False)
    if data is None:
        raise BadRequest('Request body must be valid JSON')
    return data


def _idempotent(data: dict, operation) -> Response:
    """Run a mutation and atomically save/replay its successful response."""
    key = request.headers.get('Idempotency-Key')
    conn = get_db()
    lock_enabled = idempotency_lock_enabled()
    if lock_enabled and key is None:
        conn.rollback()
        return error(428, 'Idempotency-Key is required while the idempotency lock is enabled')
    if not lock_enabled and key is not None:
        conn.rollback()
        return error(409, 'Idempotency-Key is not allowed while the idempotency lock is disabled')
    if key is None:
        conn.rollback()
        return operation()
    if not key or len(key) > 255:
        return error(400, 'Idempotency-Key must contain between 1 and 255 characters')

    token_info = connexion.context.context['token_info']
    user_id = token_info['user_id']
    canonical = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    fingerprint = hashlib.sha256(f'{request.method}\n{request.path}\n{canonical}'.encode()).hexdigest()

    def replay(row) -> Response:
        if row['request_hash'] != fingerprint:
            return error(409, 'Idempotency-Key was already used for a different request')
        return Response(row['response_body'], status=row['response_code'], mimetype='application/json')

    row = fetch_idempotency_response(user_id, key)
    if row:
        conn.rollback()
        return replay(row)

    try:
        g.managed_transaction = True
        response = operation()
        if not 200 <= response.status_code < 300:
            conn.rollback()
            return response
        save_idempotency_response(user_id, key, fingerprint, response.status_code, response.get_data(as_text=True))
        conn.commit()
        return response
    except IntegrityError:
        conn.rollback()
        row = fetch_idempotency_response(user_id, key)
        conn.rollback()
        if row:
            return replay(row)
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        g.pop('managed_transaction', None)


def get_lock() -> Response:
    return jsonify({'enabled': idempotency_lock_enabled()})


def enable_lock() -> Response:
    set_idempotency_lock(True)
    return jsonify({'enabled': True})


def disable_lock() -> Response:
    set_idempotency_lock(False)
    return jsonify({'enabled': False})


def _node_response(node_id: int, status: int = 200) -> Response:
    row = fetch_node(node_id)
    if row is None:
        return error(500, 'Internal server error')
    parent_id = fetch_parent_id(node_id)
    node = node_row_to_dict(row)
    node['parent_id'] = base62.encode(parent_id) if parent_id is not None else None
    node['children'] = fetch_children(node_id)
    node['tags'] = fetch_tags_for_node(node_id)
    response = jsonify(node)
    response.status_code = status
    return response


# Config endpoint
def get_config() -> Response:
    return jsonify({'orphan_location': current_app.config.get('ORPHAN_LOCATION')})


def get_snapshot() -> Response:
    nodes, cursor = fetch_graph_snapshot()
    return jsonify({'nodes': nodes, 'event_cursor': cursor})


def get_events(last_event_id: str) -> Response:  # pragma: no cover - handled by EventStreamMiddleware
    raise RuntimeError(f'Event stream middleware did not intercept cursor {last_event_id}')


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


def get_tag_detail(tag_name: str) -> Response:
    tag = fetch_tag(tag_name)
    if not tag:
        return error(404, 'Tag not found')

    nodes = fetch_nodes_for_tag(tag_name)

    return jsonify(
        {
            **tag_row_to_dict(tag),
            'nodes': [node_row_to_dict(n) for n in nodes],
        }
    )


def post_tag_create(idempotency_key: str | None = None) -> Response:  # noqa: ARG001
    data = _parse_json_body()

    def operation():
        name = data['name']
        try:
            create_tag(name)
        except ValueError as e:
            return error(409, str(e))
        tag = fetch_tag(name)
        if tag is None:
            return error(500, 'Internal server error')
        resp = jsonify(tag_row_to_dict(tag))
        resp.status_code = 201
        return resp

    return _idempotent(data, operation)


def delete_tag_endpoint(tag_name: str, idempotency_key: str | None = None) -> Response:  # noqa: ARG001
    def operation():
        delete_op = delete_tag(tag_name)
        if delete_op is None:
            return error(404, 'Tag not found')
        total, node_count = delete_op
        return jsonify({'deleted': {'total': total, 'associations': node_count}})

    return _idempotent({}, operation)


def patch_tag_update(tag_name: str, idempotency_key: str | None = None) -> Response:  # noqa: ARG001
    data = _parse_json_body()

    def operation():
        name = data['name']
        try:
            rowcount = update_tag(tag_name, name)
        except ValueError as e:
            return error(409, str(e))
        if rowcount == 0:
            return error(404, 'Tag not found')
        tag = fetch_tag(name)
        if tag is None:
            return error(500, 'Internal server error')
        return jsonify(tag_row_to_dict(tag))

    return _idempotent(data, operation)


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

    items = []
    for row in rows:
        node = node_row_to_dict(row)
        node['tags'] = fetch_tags_for_node(row['id'])
        items.append(node)
    return jsonify({'total': total, 'limit': limit, 'offset': offset, 'items': items})


def get_node_detail(node_id: str) -> Response:
    node_id_int = _decode_id(node_id, 'node_id')
    row = fetch_node(node_id_int)

    if not row:
        return error(404, 'Node not found')

    parent_id_int = fetch_parent_id(node_id_int)
    tags = fetch_tags_for_node(node_id_int)

    node = node_row_to_dict(row)
    node['parent_id'] = base62.encode(parent_id_int) if parent_id_int is not None else None
    node['children'] = fetch_children(node_id_int)
    node['tags'] = tags

    return jsonify(node)


def post_node_create(idempotency_key: str | None = None) -> Response:  # noqa: ARG001
    data = _parse_json_body()
    label = data.get('label')

    if label is None:
        return error(400, 'Missing required field: label')
    if not label:
        return error(400, 'Required field cannot be empty: label')
    if len(label) > 255:
        return error(400, 'label must be 255 characters or fewer')

    description = data.get('description')
    is_container = bool(data.get('is_container', False))
    raw_parent_id = data.get('parent_id')
    tags = data.get('tags') or []

    try:
        parent_id_int = _decode_id(raw_parent_id, 'parent_id') if raw_parent_id is not None else None
    except BadRequest as e:
        return error(400, e.description)

    def operation():
        try:
            node_id = create_node(label, description, is_container, parent_id=parent_id_int, tags=tags)
        except ValueError as ve:
            return error(400, str(ve))
        return _node_response(node_id, 201)

    return _idempotent(data, operation)


def patch_node_update(node_id: str, idempotency_key: str | None = None) -> Response:  # noqa: ARG001
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
        fields['description'] = data['description']

    if 'is_container' in data:
        fields['is_container'] = bool(data['is_container'])

    parent_provided = 'parent_id' in data
    raw_parent_id = data.get('parent_id') if parent_provided else None

    tags_provided = 'tags' in data
    tags = data.get('tags') or []

    try:
        parent_id_int = _decode_id(raw_parent_id, 'parent_id') if raw_parent_id is not None else None
    except BadRequest as e:
        return error(400, e.description)

    def operation():
        try:
            found = update_node(
                node_id_int,
                fields,
                parent_provided=parent_provided,
                parent_id=parent_id_int,
                tags_provided=tags_provided,
                tags=tags,
            )
        except ValueError as ve:
            return error(400, str(ve))
        if not found:
            return error(404, 'Node not found')
        return _node_response(node_id_int)

    return _idempotent(data, operation)


def put_node_upsert(node_id: str, idempotency_key: str | None = None) -> Response:  # noqa: ARG001
    node_id_int = _decode_id(node_id, 'node_id')
    data = _parse_json_body()
    label = data.get('label')
    if not label:
        return error(400, 'Missing or empty required field: label')
    if len(label) > 255:
        return error(400, 'label must be 255 characters or fewer')
    description = data.get('description')
    is_container = bool(data.get('is_container', False))
    raw_parent_id = data.get('parent_id')
    try:
        parent_id = _decode_id(raw_parent_id, 'parent_id') if raw_parent_id is not None else None
    except BadRequest as exc:
        return error(400, exc.description)
    tags = data.get('tags') or []

    def operation():
        try:
            created = put_node(node_id_int, label, description, is_container, parent_id, tags)
        except ValueError as exc:
            return error(400, str(exc))
        return _node_response(node_id_int, 201 if created else 200)

    return _idempotent(data, operation)


def delete_node_endpoint(node_id: str, idempotency_key: str | None = None) -> Response:  # noqa: ARG001
    node_id_int = _decode_id(node_id, 'node_id')

    def operation():
        delete_op = delete_node(node_id_int)
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

    return _idempotent({}, operation)
