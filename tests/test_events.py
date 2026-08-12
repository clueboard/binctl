import json

from sqlalchemy import text

from binctl_server.db.events import append_event, event_bounds, fetch_events_after
from binctl_server.sse import sse_event


def _events(engine):
    with engine.connect() as conn:
        return list(fetch_events_after(conn, 0, 100))


def test_snapshot_includes_cursor(client, authed_headers):
    response = client.get('/v1/snapshot', headers=authed_headers)
    assert response.status_code == 200
    assert response.json() == {'nodes': [], 'event_cursor': 0}


def test_node_and_implicit_tag_events_are_atomic(client, authed_headers, engine):
    response = client.post('/v1/nodes', json={'label': 'Drill', 'tags': ['tool']}, headers=authed_headers)
    assert response.status_code == 201

    rows = _events(engine)
    assert [row['event_type'] for row in rows] == ['tag.created', 'node.created']
    node_event = json.loads(rows[1]['data'])
    assert node_event['resource']['id'] == response.json()['id']
    assert node_event['resource']['tags'] == ['tool']
    assert node_event['operation'] == 'created'


def test_create_child_emits_updated_parent(client, authed_headers, engine):
    parent_id = client.post('/v1/nodes', json={'label': 'Box', 'is_container': True}, headers=authed_headers).json()['id']
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM inventory_events'))

    child_id = client.post('/v1/nodes', json={'label': 'Drill', 'parent_id': parent_id}, headers=authed_headers).json()['id']

    rows = _events(engine)
    assert [row['event_type'] for row in rows] == ['node.created', 'node.updated']
    parent = json.loads(rows[1]['data'])['resource']
    assert parent['id'] == parent_id
    assert [child['id'] for child in parent['children']] == [child_id]


def test_update_child_emits_updated_parent(client, authed_headers, engine):
    parent_id = client.post('/v1/nodes', json={'label': 'Box', 'is_container': True}, headers=authed_headers).json()['id']
    child_id = client.post('/v1/nodes', json={'label': 'Drill', 'parent_id': parent_id}, headers=authed_headers).json()['id']
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM inventory_events'))

    response = client.patch(f'/v1/nodes/{child_id}', json={'label': 'Cordless drill', 'tags': ['tool']}, headers=authed_headers)
    assert response.status_code == 200
    rows = _events(engine)
    assert [row['event_type'] for row in rows] == ['tag.created', 'node.updated', 'node.updated']
    parent = json.loads(rows[2]['data'])['resource']
    assert parent['children'][0]['label'] == 'Cordless drill'
    assert parent['children'][0]['tags'] == ['tool']


def test_move_child_emits_both_updated_parents(client, authed_headers, engine):
    old_parent = client.post('/v1/nodes', json={'label': 'Old', 'is_container': True}, headers=authed_headers).json()['id']
    new_parent = client.post('/v1/nodes', json={'label': 'New', 'is_container': True}, headers=authed_headers).json()['id']
    child_id = client.post('/v1/nodes', json={'label': 'Drill', 'parent_id': old_parent}, headers=authed_headers).json()['id']
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM inventory_events'))

    response = client.patch(f'/v1/nodes/{child_id}', json={'parent_id': new_parent}, headers=authed_headers)
    assert response.status_code == 200
    rows = _events(engine)
    assert [row['event_type'] for row in rows] == ['node.updated', 'node.updated', 'node.updated']
    parents = {event['resource']['id']: event['resource'] for event in (json.loads(row['data']) for row in rows[1:])}
    assert parents[old_parent]['children'] == []
    assert [child['id'] for child in parents[new_parent]['children']] == [child_id]


def test_delete_child_emits_updated_parent(client, authed_headers, engine):
    parent_id = client.post('/v1/nodes', json={'label': 'Box', 'is_container': True}, headers=authed_headers).json()['id']
    child_id = client.post('/v1/nodes', json={'label': 'Drill', 'parent_id': parent_id}, headers=authed_headers).json()['id']
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM inventory_events'))

    response = client.delete(f'/v1/nodes/{child_id}', headers=authed_headers)
    assert response.status_code == 200
    rows = _events(engine)
    assert [row['event_type'] for row in rows] == ['node.updated', 'node.deleted']
    assert json.loads(rows[0]['data'])['resource']['children'] == []


def test_failed_mutation_does_not_append_event(client, authed_headers, engine):
    response = client.post('/v1/nodes', json={'label': 'Bad', 'tags': ['INVALID']}, headers=authed_headers)
    assert response.status_code == 400
    assert _events(engine) == []


def test_idempotency_replay_does_not_duplicate_event(client, authed_headers, engine):
    client.put('/v1/lock', headers=authed_headers)
    headers = {**authed_headers, 'Idempotency-Key': 'once'}
    first = client.post('/v1/tags', json={'name': 'tool'}, headers=headers)
    second = client.post('/v1/tags', json={'name': 'tool'}, headers=headers)
    assert first.status_code == second.status_code == 201
    assert len(_events(engine)) == 1


def test_delete_container_emits_child_update_before_delete(client, authed_headers, engine):
    parent = client.post('/v1/nodes', json={'label': 'Box', 'is_container': True}, headers=authed_headers).json()['id']
    child = client.post('/v1/nodes', json={'label': 'Drill', 'parent_id': parent}, headers=authed_headers).json()['id']
    with engine.connect() as conn:
        conn.execute(text('DELETE FROM inventory_events'))
        conn.commit()

    response = client.delete(f'/v1/nodes/{parent}', headers=authed_headers)
    assert response.status_code == 200
    rows = _events(engine)
    assert [row['event_type'] for row in rows] == ['node.updated', 'node.deleted']
    assert json.loads(rows[0]['data'])['resource']['id'] == child
    assert json.loads(rows[0]['data'])['resource']['parent_id'] is None


def test_tag_rename_emits_updated_nodes(client, authed_headers, engine):
    node_id = client.post('/v1/nodes', json={'label': 'Drill', 'tags': ['tool']}, headers=authed_headers).json()['id']
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM inventory_events'))
    response = client.patch('/v1/tags/tool', json={'name': 'power-tool'}, headers=authed_headers)
    assert response.status_code == 200
    rows = _events(engine)
    assert [row['event_type'] for row in rows] == ['tag.updated', 'node.updated']
    node = json.loads(rows[1]['data'])['resource']
    assert node['id'] == node_id
    assert node['tags'] == ['power-tool']


def test_tag_delete_emits_updated_nodes_before_delete(client, authed_headers, engine):
    node_id = client.post('/v1/nodes', json={'label': 'Drill', 'tags': ['tool']}, headers=authed_headers).json()['id']
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM inventory_events'))
    response = client.delete('/v1/tags/tool', headers=authed_headers)
    assert response.status_code == 200
    rows = _events(engine)
    assert [row['event_type'] for row in rows] == ['node.updated', 'tag.deleted']
    node = json.loads(rows[0]['data'])['resource']
    assert node['id'] == node_id
    assert node['tags'] == []


def test_retention_prunes_old_events(engine, clean_db, monkeypatch):
    monkeypatch.setenv('EVENT_RETENTION_LIMIT', '2')
    with engine.begin() as conn:
        append_event(conn, 'tag.created', {'n': 1})
        append_event(conn, 'tag.created', {'n': 2})
        append_event(conn, 'tag.created', {'n': 3})
    with engine.connect() as conn:
        assert event_bounds(conn) == (2, 3)
        assert [row['id'] for row in fetch_events_after(conn, 0)] == [2, 3]


def test_sse_serialization():
    assert sse_event(7, 'node.updated', {'label': 'A'}) == b'id: 7\nevent: node.updated\ndata: {"label":"A"}\n\n'
