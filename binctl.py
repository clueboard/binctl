#!/usr/bin/env python3
"""binctl: CLI client for the binctl API.

PYTHON_ARGCOMPLETE_OK
"""

import json

from binctl_client import Client
from binctl_client.api.nodes import (
    get_node_detail,
    get_nodes_list,
    patch_node_update,
    post_node_create,
)
from binctl_client.api.tags import (
    get_tag_detail,
    get_tags_list,
    patch_tag_update,
    post_tag_create,
)
from binctl_client.models import NodeCreate, NodeUpdate, TagCreate, TagUpdate
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


def _check_response(result, label: str):
    """Exit with an error if the API returned None (server returned an error status)."""
    if result is None:
        cli.log.error('%s: server returned an error (resource not found or unexpected status)', label)
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
        page = get_nodes_list.sync(client=client, limit=limit, offset=offset)
        _check_response(page, 'node list')
        assert page is not None  # _check_response raises SystemExit on None; assert narrows the type for ty
        items.extend(page.items)
        if len(items) >= page.total:
            break
        offset += limit
    _echo_json(cli, [n.to_dict() for n in items])


def _node_get(cli, node_id: int):
    client = _get_client(cli)
    node = get_node_detail.sync(client=client, node_id=node_id)
    _check_response(node, f'node {node_id}')
    data = node.to_dict() if hasattr(node, 'to_dict') else node
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

    node = post_node_create.sync(client=client, body=body)
    _check_response(node, 'node create')
    data = node.to_dict() if hasattr(node, 'to_dict') else node
    _echo_json(cli, data)


def _node_update(cli, node_id: int):
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

    node = patch_node_update.sync(client=client, node_id=node_id, body=body)
    _check_response(node, f'node {node_id}')
    data = node.to_dict() if hasattr(node, 'to_dict') else node
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
        page = get_tags_list.sync(client=client, limit=limit, offset=offset)
        _check_response(page, 'tag list')
        assert page is not None  # _check_response raises SystemExit on None; assert narrows the type for ty
        items.extend(page.items)
        if len(items) >= page.total:
            break
        offset += limit
    _echo_json(cli, [t.to_dict() for t in items])


def _tag_get(cli, tag_id: int):
    client = _get_client(cli)
    tag = get_tag_detail.sync(client=client, tag_id=tag_id)
    _check_response(tag, f'tag {tag_id}')
    data = tag.to_dict() if hasattr(tag, 'to_dict') else tag
    _echo_json(cli, data)


def _tag_create(cli):
    client = _get_client(cli)
    body = TagCreate(name=cli.args.name)
    tag = post_tag_create.sync(client=client, body=body)
    _check_response(tag, 'tag create')
    data = tag.to_dict() if hasattr(tag, 'to_dict') else tag
    _echo_json(cli, data)


def _tag_update(cli, tag_id: int):
    client = _get_client(cli)
    body = TagUpdate(name=cli.args.name)
    tag = patch_tag_update.sync(client=client, tag_id=tag_id, body=body)
    _check_response(tag, f'tag {tag_id}')
    data = tag.to_dict() if hasattr(tag, 'to_dict') else tag
    _echo_json(cli, data)


# ---------------------------------------------------------------------------
# Node command group (single-level dispatcher)
# ---------------------------------------------------------------------------


@cli.argument(
    'action',
    choices=['list', 'get', 'create', 'update'],
    help='Node action to perform: list|get|create|update',
)
@cli.argument('--node-id', type=int, help='Node ID (required for get/update)')
@cli.argument('--label', help='Label for create/update')
@cli.argument('--description', help='Description for create/update', default=None)
@cli.argument(
    '--is-container',
    action='store_boolean',
    help='Set container flag (create defaults to False)',
)
@cli.argument('--parent-id', type=int, default=None, help='Parent node ID')
@cli.argument('--no-parent', action='store_true', default=False, help='Detach node from its parent')
@cli.argument('--tag-id', type=int, nargs='*', help='Tag IDs to attach/replace')
@cli.subcommand('Node operations: list, get, create, update.')
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

    cli.log.error(f'Unknown node action: {action}')
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Tag command group (single-level dispatcher)
# ---------------------------------------------------------------------------


@cli.argument(
    'action',
    choices=['list', 'get', 'create', 'update'],
    help='Tag action to perform: list|get|create|update',
)
@cli.argument('--tag-id', type=int, help='Tag ID (required for get/update)')
@cli.argument('--name', help='Tag name for create/update')
@cli.subcommand('Tag operations: list, get, create, update.')
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

    cli.log.error(f'Unknown tag action: {action}')
    raise SystemExit(1)


if __name__ == '__main__':
    cli()
