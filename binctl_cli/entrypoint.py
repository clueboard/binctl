#!/usr/bin/env python3
"""binctl: CLI client for the binctl API.

PYTHON_ARGCOMPLETE_OK
"""

import json
import logging

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

cli.milc_options(name='binctl', config_file='/etc/binctl.conf')


def _get_client() -> Client:
    """Construct an API client from config/args."""
    base_url = cli.config.general.base_url
    token = cli.config.general.token
    if token:
        return Client(base_url=base_url, token=token)
    return Client(base_url=base_url, username=cli.config.general.username, password=cli.config.general.password)


_SPINNER_TEXT = {
    ('node', 'list'): 'Fetching nodes...',
    ('node', 'get'): 'Fetching node...',
    ('node', 'create'): 'Creating node...',
    ('node', 'update'): 'Updating node...',
    ('node', 'delete'): 'Deleting node...',
    ('tag', 'list'): 'Fetching tags...',
    ('tag', 'get'): 'Fetching tag...',
    ('tag', 'create'): 'Creating tag...',
    ('tag', 'update'): 'Updating tag...',
    ('tag', 'delete'): 'Deleting tag...',
}


def _format_node(action, result) -> str:
    if action == 'list':
        if not result:
            return 'No nodes.'
        lines = [f'{len(result)} node{"s" if len(result) != 1 else ""}:']
        for n in result:
            kind = 'container' if n.is_container else 'item'
            lines.append(f'  {n.label} ({n.id}) [{kind}]')
        return '\n'.join(lines)
    if action == 'get':
        kind = 'container' if result.is_container else 'item'
        return f'"{result.label}" (id: {result.id}) [{kind}]'
    if action == 'create':
        return f'Created "{result.label}" with node id "{result.id}"'
    if action == 'update':
        return f'Updated "{result.label}" (id: {result.id})'
    if action == 'delete':
        return f'Deleted node "{cli.args.node_id}"'
    return ''


def _format_tag(action, result) -> str:
    if action == 'list':
        if not result:
            return 'No tags.'
        lines = [f'{len(result)} tag{"s" if len(result) != 1 else ""}:']
        for t in result:
            lines.append(f'  {t.name} ({t.id})')
        return '\n'.join(lines)
    if action == 'get':
        return f'"{result.name}" (id: {result.id})'
    if action == 'create':
        return f'Created tag "{result.name}" (id: {result.id})'
    if action == 'update':
        return f'Updated tag "{result.name}" (id: {result.id})'
    if action == 'delete':
        return f'Deleted tag "{cli.args.tag_id}"'
    return ''


def _run_with_output(resource, action, fn, formatter):
    if cli.config_source.general.verbose != 'argument':
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)

    if cli.args.output == 'json':
        result = fn()
        data = [r.to_dict() for r in result] if isinstance(result, list) else result.to_dict()
        cli.echo(json.dumps(data, indent=4, sort_keys=True))
        return

    sp = cli.spinner(_SPINNER_TEXT[(resource, action)])
    sp.start()
    try:
        result = fn()
        sp.succeed(formatter(action, result))
    except Exception as e:
        sp.fail(f'Failed: {e.__class__.__name__}: {e}')
        raise


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


@cli.argument('--base-url', default='http://localhost:5000', help='Base URL for the binctl API (e.g. http://localhost:5000)')
@cli.argument('--token', default=None, help='Bearer token for authentication')
@cli.argument('--username', default=None, help='Username for login-based authentication')
@cli.argument('--password', default=None, help='Password for login-based authentication. WARNING: visible in process listings (ps, top). Prefer --token for production use.')
@cli.argument('-o', '--output', choices=['text', 'json'], default='text', help='Output format: text (human-friendly) or json (raw JSON, no spinner)')
@cli.entrypoint('binctl: manage storage nodes and tags.')
def main(cli):
    """Top-level entrypoint. If no subcommand is given, show help."""
    cli.print_usage()


# ---------------------------------------------------------------------------
# Nodes helpers
# ---------------------------------------------------------------------------


def _node_list():
    client = _get_client()
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
    return items


def _node_get():
    client = _get_client()
    response = get_node_detail.sync_detailed(client=client, node_id=cli.args.node_id)
    _check_response(response, f'node {cli.args.node_id}')
    return response.parsed


def _node_create():
    client = _get_client()
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
    return response.parsed


def _node_delete():
    client = _get_client()
    response = delete_node_endpoint.sync_detailed(client=client, node_id=cli.args.node_id)
    _check_response(response, f'node {cli.args.node_id}')
    return response.parsed


def _node_update():
    client = _get_client()
    # Build a partial update body. Unspecified fields are left as None.
    body_kwargs = {}

    if cli.args.label is not None:
        body_kwargs['label'] = cli.args.label
    if cli.args.description is not None:
        body_kwargs['description'] = cli.args.description
    if cli.config_source.node.is_container == 'argument':
        body_kwargs['is_container'] = cli.args.is_container
    if cli.args.parent_id is not None:
        body_kwargs['parent_id'] = cli.args.parent_id
    elif cli.args.no_parent:
        body_kwargs['parent_id'] = None
    if cli.args.tag_id is not None:
        body_kwargs['tag_ids'] = cli.args.tag_id

    body = NodeUpdate(**body_kwargs)

    response = patch_node_update.sync_detailed(client=client, node_id=cli.args.node_id, body=body)
    _check_response(response, f'node {cli.args.node_id}')
    return response.parsed


# ---------------------------------------------------------------------------
# Tags helpers
# ---------------------------------------------------------------------------


def _tag_list():
    client = _get_client()
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
    return items


def _tag_get():
    client = _get_client()
    response = get_tag_detail.sync_detailed(client=client, tag_id=cli.args.tag_id)
    _check_response(response, f'tag {cli.args.tag_id}')
    return response.parsed


def _tag_create():
    client = _get_client()
    body = TagCreate(name=cli.args.name)
    response = post_tag_create.sync_detailed(client=client, body=body)
    _check_response(response, 'tag create')
    return response.parsed


def _tag_delete():
    client = _get_client()
    response = delete_tag_endpoint.sync_detailed(client=client, tag_id=cli.args.tag_id)
    _check_response(response, f'tag {cli.args.tag_id}')
    return response.parsed


def _tag_update():
    client = _get_client()
    body = TagUpdate(name=cli.args.name)
    response = patch_tag_update.sync_detailed(client=client, tag_id=cli.args.tag_id, body=body)
    _check_response(response, f'tag {cli.args.tag_id}')
    return response.parsed


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
        _run_with_output('node', 'list', _node_list, _format_node)
        return

    if action == 'get':
        if cli.args.node_id is None:
            cli.log.error('node get requires --node-id')
            raise SystemExit(1)
        _run_with_output('node', 'get', _node_get, _format_node)
        return

    if action == 'create':
        if not cli.args.label:
            cli.log.error('node create requires --label')
            raise SystemExit(1)
        _run_with_output('node', 'create', _node_create, _format_node)
        return

    if action == 'update':
        if cli.args.node_id is None:
            cli.log.error('node update requires --node-id')
            raise SystemExit(1)
        if (
            not cli.args.no_parent
            and all(
                value is None
                for value in (
                    cli.args.label,
                    cli.args.description,
                    cli.args.parent_id,
                    cli.args.tag_id,
                )
            )
            and cli.config_source.node.is_container != 'argument'
        ):
            cli.log.error('node update needs at least one field to change')
            raise SystemExit(1)
        _run_with_output('node', 'update', _node_update, _format_node)
        return

    if action == 'delete':
        if cli.args.node_id is None:
            cli.log.error('node delete requires --node-id')
            raise SystemExit(1)
        _run_with_output('node', 'delete', _node_delete, _format_node)
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
        _run_with_output('tag', 'list', _tag_list, _format_tag)
        return

    if action == 'get':
        if cli.args.tag_id is None:
            cli.log.error('tag get requires --tag-id')
            raise SystemExit(1)
        _run_with_output('tag', 'get', _tag_get, _format_tag)
        return

    if action == 'create':
        if not cli.args.name:
            cli.log.error('tag create requires --name')
            raise SystemExit(1)
        _run_with_output('tag', 'create', _tag_create, _format_tag)
        return

    if action == 'update':
        if cli.args.tag_id is None:
            cli.log.error('tag update requires --tag-id')
            raise SystemExit(1)
        if not cli.args.name:
            cli.log.error('tag update requires --name')
            raise SystemExit(1)
        _run_with_output('tag', 'update', _tag_update, _format_tag)
        return

    if action == 'delete':
        if cli.args.tag_id is None:
            cli.log.error('tag delete requires --tag-id')
            raise SystemExit(1)
        _run_with_output('tag', 'delete', _tag_delete, _format_tag)
        return

    cli.log.error(f'Unknown tag action: {action}')
    raise SystemExit(1)


if __name__ == '__main__':
    cli()
