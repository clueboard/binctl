from sqlalchemy import text


def enable_mode(client, authed_headers):
    response = client.put('/v1/lock', headers=authed_headers)
    assert response.status_code == 200
    assert response.json() == {'enabled': True}


def test_post_replay_returns_original_node(client, authed_headers, engine):
    enable_mode(client, authed_headers)
    headers = {**authed_headers, 'Idempotency-Key': 'create-offline-operation'}
    first = client.post('/v1/nodes', json={'label': 'one'}, headers=headers)
    second = client.post('/v1/nodes', json={'label': 'one'}, headers=headers)

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    with engine.connect() as conn:
        assert conn.execute(text('SELECT COUNT(*) FROM nodes')).scalar_one() == 1
        assert conn.execute(text('SELECT COUNT(*) FROM idempotency_keys')).scalar_one() == 1


def test_reusing_key_for_different_request_conflicts(client, authed_headers):
    enable_mode(client, authed_headers)
    headers = {**authed_headers, 'Idempotency-Key': 'same-key'}
    assert client.post('/v1/nodes', json={'label': 'one'}, headers=headers).status_code == 201
    response = client.post('/v1/nodes', json={'label': 'two'}, headers=headers)
    assert response.status_code == 409


def test_failed_request_does_not_consume_key(client, authed_headers):
    enable_mode(client, authed_headers)
    headers = {**authed_headers, 'Idempotency-Key': 'retry-after-failure'}
    assert client.post('/v1/nodes', json={'label': 'child', 'parent_id': 'abc'}, headers=headers).status_code == 400
    assert client.post('/v1/nodes', json={'label': 'child'}, headers=headers).status_code == 201


def test_put_replay_preserves_original_response(client, authed_headers):
    enable_mode(client, authed_headers)
    headers = {**authed_headers, 'Idempotency-Key': 'put-operation'}
    first = client.put('/v1/nodes/abc', json={'label': 'offline'}, headers=headers)
    second = client.put('/v1/nodes/abc', json={'label': 'offline'}, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()


def test_key_is_scoped_to_user(app, client, authed_headers, clean_db):
    from binctl_server.db.direct import create_token, create_user

    enable_mode(client, authed_headers)
    first = client.post('/v1/nodes', json={'label': 'one'}, headers={**authed_headers, 'Idempotency-Key': 'shared'})
    user_id = create_user('second', 'password')
    token = create_token(user_id)
    second = app.test_client().post(
        '/v1/nodes',
        json={'label': 'two'},
        headers={'Authorization': f'Bearer {token}', 'Idempotency-Key': 'shared'},
    )
    assert first.status_code == second.status_code == 201
    assert first.json()['id'] != second.json()['id']


def test_mode_defaults_disabled_and_rejects_keys(client, authed_headers):
    assert client.get('/v1/lock', headers=authed_headers).json() == {'enabled': False}
    response = client.post(
        '/v1/nodes',
        json={'label': 'one'},
        headers={**authed_headers, 'Idempotency-Key': 'not-enabled'},
    )
    assert response.status_code == 409


def test_enabled_mode_requires_keys_for_all_inventory_mutations(client, make_node, make_tag, authed_headers):
    node_id = make_node('node')
    tag_name = make_tag('tag')
    enable_mode(client, authed_headers)

    assert client.post('/v1/nodes', json={'label': 'new'}, headers=authed_headers).status_code == 428
    assert client.patch(f'/v1/nodes/{node_id}', json={'label': 'new'}, headers=authed_headers).status_code == 428
    assert client.delete(f'/v1/nodes/{node_id}', headers=authed_headers).status_code == 428
    assert client.post('/v1/tags', json={'name': 'new'}, headers=authed_headers).status_code == 428
    assert client.patch(f'/v1/tags/{tag_name}', json={'name': 'new'}, headers=authed_headers).status_code == 428
    assert client.delete(f'/v1/tags/{tag_name}', headers=authed_headers).status_code == 428


def test_disabling_mode_rejects_keys_again(client, authed_headers):
    enable_mode(client, authed_headers)
    response = client.delete('/v1/lock', headers=authed_headers)
    assert response.status_code == 200
    assert response.json() == {'enabled': False}
    response = client.post(
        '/v1/nodes',
        json={'label': 'one'},
        headers={**authed_headers, 'Idempotency-Key': 'disabled-again'},
    )
    assert response.status_code == 409


def test_delete_is_replayed_while_enabled(client, make_node, authed_headers):
    node_id = make_node('delete me')
    enable_mode(client, authed_headers)
    headers = {**authed_headers, 'Idempotency-Key': 'delete-operation'}
    first = client.delete(f'/v1/nodes/{node_id}', headers=headers)
    second = client.delete(f'/v1/nodes/{node_id}', headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
