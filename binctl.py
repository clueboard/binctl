#!/usr/bin/env python3
"""binctl: CLI client for the binctl API.

PYTHON_ARGCOMPLETE_OK
"""

import json

from binctl_client import Client
from binctl_client.api.nodes import (
    delete_node_endpoint,
    get_node_detail,
    get_nodes_list,
    patch_node_update,
    post_node_create,
)
from binctl_client.api.tags import (
    delete_tag_endpoint,
    get_tag_detail,
    get_tags_list,
    patch_tag_update,
    post_tag_create,
)
from binctl_client.models import NodeCreate, NodeUpdate, TagCreate, TagUpdate
from binctl_client.types import Response
from milc import cli


def _get_client(cli) -> Client:
    """Construct an API client from config/args."""
    base_url = cli.config.general.base_url
    token = cli.config.general.token
    if token:
        return Client(base_url=base_url, token=token)
    return Client(base_url=base_url, username=cli.config.general.username, password=cli.config.general.password)


def _echo_json(cli, data):
    cli.echo(json.dumps(data, indent=4, sort_keys=True))


def _check_response(response: Response, label: str):
    """Exit with an error if the API returned a non-success status."""
    if response.parsed is None:
        try:
            body = json.loads(response.content)
            message = body.get('error') or response.content.decode()
        except Exception:
            message = response.content.decode() or 'unknown error'
        cli.log.error('%s: %s %s', label, response.status_code.value, message)
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# Entry point + global options
# ---------------------------------------------------------------------------


@cli.argument(
    '--base-url',
    default='http://localhost:5000',
    help='Base URL for the binctl API (e.g. http://localhost:5000)',
)
@cli.argument('--token', default=None, help='Bearer token for authentication')
@cli.argument('--username', default=None, help='Username for login-based authentication')
@cli.argument(
    '--password',
    default=None,
    help='Password for login-based authentication. WARNING: visible in process listings (ps, top). Prefer --token for production use.',
)
@cli.entrypoint('binctl: manage storage nodes and tags.')
def main(cli):
    """Top-level entrypoint. If no subcommand is given, show help."""
    # If the user runs just `binctl`, print usage.
    cli.print_usage()


# ---------------------------------------------------------------------------
# Nodes helpers
# ---------------------------------------------------------------------------


def _node_list(cli):
    client = _get_client(cli)
    items = []
    offset = 0
    limit = 100
    while True:
        response = get_nodes_list.sync_detailed(client=client, limit=limit, offset=offset)
        _check_response(response, 'node list')
        assert response.parsed is not None  # _check_response raises SystemExit on None; assert narrows the type for ty
        items.extend(response.parsed.items)
        if len(items) >= response.parsed.total:
            break
        offset += limit
    _echo_json(cli, [n.to_dict() for n in items])


def _node_get(cli, node_id: str):
    client = _get_client(cli)
    response = get_node_detail.sync_detailed(client=client, node_id=node_id)
    _check_response(response, f'node {node_id}')
    data = response.parsed.to_dict() if hasattr(response.parsed, 'to_dict') else response.parsed
    _echo_json(cli, data)


def _node_create(cli):
    client = _get_client(cli)
    is_container = False if cli.args.is_container is None else cli.args.is_container
    body = NodeCreate(
        label=cli.args.label,
        description=cli.args.description,
        is_container=is_container,
        parent_id=cli.args.parent_id,
        tag_ids=cli.args.tag_id or [],
    )

    response = post_node_create.sync_detailed(client=client, body=body)
    _check_response(response, 'node create')
    data = response.parsed.to_dict() if hasattr(response.parsed, 'to_dict') else response.parsed
    _echo_json(cli, data)


def _delete_response(cli, response, label: str):
    _check_response(response, label)
    data = response.parsed.to_dict() if hasattr(response.parsed, 'to_dict') else response.parsed
    _echo_json(cli, data)


def _node_delete(cli, node_id: str):
    client = _get_client(cli)
    response = delete_node_endpoint.sync_detailed(client=client, node_id=node_id)
    _delete_response(cli, response, f'node {node_id}')


def _node_update(cli, node_id: str):
    client = _get_client(cli)
    # Build a partial update body. Unspecified fields are left as None.
    body_kwargs = {}

    if cli.args.label is not None:
        body_kwargs['label'] = cli.args.label
    if cli.args.description is not None:
        body_kwargs['description'] = cli.args.description
    # is_container via store_boolean gives True/False/None
    if cli.args.is_container is not None:
        body_kwargs['is_container'] = cli.args.is_container
    if cli.args.parent_id is not None:
        body_kwargs['parent_id'] = cli.args.parent_id
    elif cli.args.no_parent:
        body_kwargs['parent_id'] = None
    if cli.args.tag_id is not None:
        body_kwargs['tag_ids'] = cli.args.tag_id

    body = NodeUpdate(**body_kwargs)

    response = patch_node_update.sync_detailed(client=client, node_id=node_id, body=body)
    _check_response(response, f'node {node_id}')
    data = response.parsed.to_dict() if hasattr(response.parsed, 'to_dict') else response.parsed
    _echo_json(cli, data)


# ---------------------------------------------------------------------------
# Tags helpers
# ---------------------------------------------------------------------------


def _tag_list(cli):
    client = _get_client(cli)
    items = []
    offset = 0
    limit = 100
    while True:
        response = get_tags_list.sync_detailed(client=client, limit=limit, offset=offset)
        _check_response(response, 'tag list')
        assert response.parsed is not None  # _check_response raises SystemExit on None; assert narrows the type for ty
        items.extend(response.parsed.items)
        if len(items) >= response.parsed.total:
            break
        offset += limit
    _echo_json(cli, [t.to_dict() for t in items])


def _tag_get(cli, tag_id: str):
    client = _get_client(cli)
    response = get_tag_detail.sync_detailed(client=client, tag_id=tag_id)
    _check_response(response, f'tag {tag_id}')
    data = response.parsed.to_dict() if hasattr(response.parsed, 'to_dict') else response.parsed
    _echo_json(cli, data)


def _tag_create(cli):
    client = _get_client(cli)
    body = TagCreate(name=cli.args.name)
    response = post_tag_create.sync_detailed(client=client, body=body)
    _check_response(response, 'tag create')
    data = response.parsed.to_dict() if hasattr(response.parsed, 'to_dict') else response.parsed
    _echo_json(cli, data)


def _tag_delete(cli, tag_id: str):
    client = _get_client(cli)
    response = delete_tag_endpoint.sync_detailed(client=client, tag_id=tag_id)
    _delete_response(cli, response, f'tag {tag_id}')


def _tag_update(cli, tag_id: str):
    client = _get_client(cli)
    body = TagUpdate(name=cli.args.name)
    response = patch_tag_update.sync_detailed(client=client, tag_id=tag_id, body=body)
    _check_response(response, f'tag {tag_id}')
    data = response.parsed.to_dict() if hasattr(response.parsed, 'to_dict') else response.parsed
    _echo_json(cli, data)


# ---------------------------------------------------------------------------
# Node command group (single-level dispatcher)
# ---------------------------------------------------------------------------


@cli.argument(
    'action',
    choices=['list', 'get', 'create', 'update', 'delete'],
    help='Node action to perform: list|get|create|update|delete',
)
@cli.argument('--node-id', type=str, help='Node ID (required for get/update/delete)')
@cli.argument('--label', help='Label for create/update')
@cli.argument('--description', help='Description for create/update', default=None)
@cli.argument(
    '--is-container',
    action='store_boolean',
    help='Set container flag (create defaults to False)',
)
@cli.argument('--parent-id', type=str, default=None, help='Parent node ID')
@cli.argument('--no-parent', action='store_true', default=False, help='Detach node from its parent')
@cli.argument('--tag-id', type=str, nargs='*', help='Tag IDs to attach/replace')
@cli.subcommand('Node operations: list, get, create, update, delete.')
def node(cli):
    """binctl node <action> [options]"""
    action = cli.args.action

    if action == 'list':
        _node_list(cli)
        return

    if action == 'get':
        if cli.args.node_id is None:
            cli.log.error('node get requires --node-id')
            raise SystemExit(1)
        _node_get(cli, cli.args.node_id)
        return

    if action == 'create':
        if not cli.args.label:
            cli.log.error('node create requires --label')
            raise SystemExit(1)
        _node_create(cli)
        return

    if action == 'update':
        if cli.args.node_id is None:
            cli.log.error('node update requires --node-id')
            raise SystemExit(1)
        if not cli.args.no_parent and all(
            value is None
            for value in (
                cli.args.label,
                cli.args.description,
                cli.args.is_container,
                cli.args.parent_id,
                cli.args.tag_id,
            )
        ):
            cli.log.error('node update needs at least one field to change')
            raise SystemExit(1)
        _node_update(cli, cli.args.node_id)
        return

    if action == 'delete':
        if cli.args.node_id is None:
            cli.log.error('node delete requires --node-id')
            raise SystemExit(1)
        _node_delete(cli, cli.args.node_id)
        return

    cli.log.error(f'Unknown node action: {action}')
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Tag command group (single-level dispatcher)
# ---------------------------------------------------------------------------


@cli.argument(
    'action',
    choices=['list', 'get', 'create', 'update', 'delete'],
    help='Tag action to perform: list|get|create|update|delete',
)
@cli.argument('--tag-id', type=str, help='Tag ID (required for get/update/delete)')
@cli.argument('--name', help='Tag name for create/update')
@cli.subcommand('Tag operations: list, get, create, update, delete.')
def tag(cli):
    """binctl tag <action> [options]"""
    action = cli.args.action

    if action == 'list':
        _tag_list(cli)
        return

    if action == 'get':
        if cli.args.tag_id is None:
            cli.log.error('tag get requires --tag-id')
            raise SystemExit(1)
        _tag_get(cli, cli.args.tag_id)
        return

    if action == 'create':
        if not cli.args.name:
            cli.log.error('tag create requires --name')
            raise SystemExit(1)
        _tag_create(cli)
        return

    if action == 'update':
        if cli.args.tag_id is None:
            cli.log.error('tag update requires --tag-id')
            raise SystemExit(1)
        if not cli.args.name:
            cli.log.error('tag update requires --name')
            raise SystemExit(1)
        _tag_update(cli, cli.args.tag_id)
        return

    if action == 'delete':
        if cli.args.tag_id is None:
            cli.log.error('tag delete requires --tag-id')
            raise SystemExit(1)
        _tag_delete(cli, cli.args.tag_id)
        return

    cli.log.error(f'Unknown tag action: {action}')
    raise SystemExit(1)


if __name__ == '__main__':
    cli()
