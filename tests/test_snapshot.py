from binctl_server.db.base62 import decode


def test_snapshot_requires_authentication(client):
    assert client.get('/v1/snapshot').status_code == 401


def test_empty_snapshot(client, authed_headers):
    response = client.get('/v1/snapshot', headers=authed_headers)
    assert response.status_code == 200
    assert response.json() == {'nodes': [], 'event_cursor': 0}


def test_snapshot_contains_complete_graph(client, make_node, make_tag, authed_headers):
    root_id = make_node('room', description='root', is_container=True, tags=['zebra', 'alpha'])
    child_id = make_node('item', parent_id=root_id)
    make_tag('unattached')

    response = client.get('/v1/snapshot', headers=authed_headers)

    assert response.status_code == 200
    nodes = response.json()['nodes']
    assert [node['id'] for node in nodes] == sorted([root_id, child_id], key=decode)
    by_id = {node['id']: node for node in nodes}
    assert by_id[root_id]['description'] == 'root'
    assert by_id[root_id]['is_container'] is True
    assert by_id[root_id]['parent_id'] is None
    assert by_id[root_id]['tags'] == ['alpha', 'zebra']
    assert by_id[child_id]['parent_id'] == root_id
    assert by_id[child_id]['tags'] == []
    assert by_id[child_id]['created_at']
    assert by_id[child_id]['updated_at']
    assert 'unattached' not in str(response.json())


def test_snapshot_available_while_idempotency_lock_enabled(client, authed_headers):
    assert client.put('/v1/lock', headers=authed_headers).status_code == 200
    assert client.get('/v1/snapshot', headers=authed_headers).status_code == 200


def test_snapshot_uses_one_database_statement(client, make_node, authed_headers, engine):
    make_node('node')
    statements = []

    from sqlalchemy import event

    def record_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, 'before_cursor_execute', record_statement)
    try:
        response = client.get('/v1/snapshot', headers=authed_headers)
    finally:
        event.remove(engine, 'before_cursor_execute', record_statement)

    assert response.status_code == 200
    snapshot_queries = [statement for statement in statements if 'FROM event_sequence s' in statement]
    assert len(snapshot_queries) == 1
    assert 'LEFT JOIN nodes n' in snapshot_queries[0]
