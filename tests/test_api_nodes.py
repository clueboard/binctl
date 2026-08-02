from sqlalchemy import text

from binctl_server.db import base62


class TestNodeCreate:
    def test_create_minimal(self, client, authed_headers):
        resp = client.post('/v1/nodes', json={'label': 'shelf-A'}, headers=authed_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body['label'] == 'shelf-A'
        assert body['is_container'] is False
        assert body['parent_id'] is None
        assert body['children'] == []
        assert body['tags'] == []
        assert body['id'] is not None

    def test_create_missing_label(self, client, authed_headers):
        resp = client.post('/v1/nodes', json={'description': 'oops'}, headers=authed_headers)
        assert resp.status_code == 400

    def test_create_empty_label(self, client, authed_headers):
        resp = client.post('/v1/nodes', json={'label': ''}, headers=authed_headers)
        assert resp.status_code == 400

    def test_create_empty_description(self, client, authed_headers):
        resp = client.post('/v1/nodes', json={'label': 'item', 'description': ''}, headers=authed_headers)
        assert resp.status_code == 201
        assert resp.json()['description'] == ''

    def test_create_with_container_parent(self, client, make_node, authed_headers):
        container_id = make_node('room', is_container=True)
        resp = client.post('/v1/nodes', json={'label': 'shelf', 'parent_id': container_id}, headers=authed_headers)
        assert resp.status_code == 201
        assert resp.json()['parent_id'] == container_id

    def test_create_nonexistent_parent(self, client, authed_headers):
        resp = client.post('/v1/nodes', json={'label': 'shelf', 'parent_id': 99999}, headers=authed_headers)
        assert resp.status_code == 400

    def test_create_non_container_parent(self, client, make_node, authed_headers):
        item_id = make_node('item', is_container=False)
        resp = client.post('/v1/nodes', json={'label': 'child', 'parent_id': item_id}, headers=authed_headers)
        assert resp.status_code == 400

    def test_create_with_tags(self, client, make_node, make_tag, authed_headers):
        t1 = make_tag('electronics')
        t2 = make_tag('fragile')
        resp = client.post('/v1/nodes', json={'label': 'laptop', 'tag_ids': [t1, t2]}, headers=authed_headers)
        assert resp.status_code == 201
        tag_names = {t['name'] for t in resp.json()['tags']}
        assert tag_names == {'electronics', 'fragile'}

    def test_create_nonexistent_tag(self, client, authed_headers):
        resp = client.post('/v1/nodes', json={'label': 'item', 'tag_ids': [99999]}, headers=authed_headers)
        assert resp.status_code == 400

    def test_create_with_integer_parent_id(self, client, authed_headers):
        resp = client.post('/v1/nodes', json={'label': 'item', 'parent_id': 123}, headers=authed_headers)
        assert resp.status_code == 400

    def test_create_with_null_tag_id(self, client, authed_headers):
        resp = client.post('/v1/nodes', json={'label': 'item', 'tag_ids': [None]}, headers=authed_headers)
        assert resp.status_code == 400


class TestNodeGet:
    def test_get_detail_full(self, client, make_node, make_tag, authed_headers):
        container_id = make_node('room', is_container=True)
        child_id = make_node('shelf', is_container=True, parent_id=container_id)
        grandchild_id = make_node('box', parent_id=child_id)  # noqa: F841
        tag_id = make_tag('storage')
        client.patch(f'/v1/nodes/{child_id}', json={'tag_ids': [tag_id]}, headers=authed_headers)

        resp = client.get(f'/v1/nodes/{child_id}', headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['id'] == child_id
        assert body['parent_id'] == container_id
        assert len(body['children']) == 1
        assert body['children'][0]['id'] == grandchild_id
        assert body['children'][0]['parent_id'] == child_id
        assert body['tags'][0]['name'] == 'storage'

    def test_get_not_found(self, client, authed_headers):
        resp = client.get('/v1/nodes/99999', headers=authed_headers)
        assert resp.status_code == 404


class TestNodeList:
    def test_list_empty(self, client, authed_headers):
        resp = client.get('/v1/nodes', headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == 0
        assert body['items'] == []

    def test_list_pagination(self, client, make_node, authed_headers):
        make_node('a')
        make_node('b')
        make_node('c')
        resp = client.get('/v1/nodes', params={'limit': 2, 'offset': 1}, headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == 3
        assert len(body['items']) == 2

    def test_list_invalid_limit(self, client, authed_headers):
        resp = client.get('/v1/nodes', params={'limit': 0}, headers=authed_headers)
        assert resp.status_code == 400

    def test_list_total_matches_items_count(self, client, make_node, authed_headers):
        """total must equal len(items) when all nodes fit within limit."""
        make_node('x')
        make_node('y')
        resp = client.get('/v1/nodes', params={'limit': 100}, headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == len(body['items'])

    def test_list_includes_parent_id(self, client, make_node, authed_headers):
        """Items in the node list must include parent_id."""
        container_id = make_node('container', is_container=True)
        child_id = make_node('child', parent_id=container_id)
        resp = client.get('/v1/nodes', params={'limit': 100}, headers=authed_headers)
        assert resp.status_code == 200
        items = {item['id']: item for item in resp.json()['items']}
        assert items[container_id]['parent_id'] is None
        assert items[child_id]['parent_id'] == container_id


class TestNodeDeleteUnauthenticated:
    def test_delete_requires_auth(self, client):
        resp = client.delete('/v1/nodes/1')
        assert resp.status_code == 401


class TestNodePatch:
    def test_patch_empty_description(self, client, make_node, authed_headers):
        node_id = make_node('item')
        resp = client.patch(f'/v1/nodes/{node_id}', json={'description': ''}, headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['description'] == ''

    def test_patch_with_integer_parent_id(self, client, make_node, authed_headers):
        node_id = make_node('item')
        resp = client.patch(f'/v1/nodes/{node_id}', json={'parent_id': 123}, headers=authed_headers)
        assert resp.status_code == 400

    def test_patch_with_null_tag_id(self, client, make_node, authed_headers):
        node_id = make_node('item')
        resp = client.patch(f'/v1/nodes/{node_id}', json={'tag_ids': [None]}, headers=authed_headers)
        assert resp.status_code == 400


class TestNodeDelete:
    def test_delete_success(self, client, make_node, make_tag, authed_headers):
        container_id = make_node('container', is_container=True)
        child_id = make_node('child', parent_id=container_id)
        tag_id = make_tag('tag')
        # Add tag to child
        client.patch(f'/v1/nodes/{child_id}', json={'tag_ids': [tag_id]}, headers=authed_headers)

        # Delete the child
        resp = client.delete(f'/v1/nodes/{child_id}', headers=authed_headers)
        assert resp.status_code == 200

        # Verify child is gone
        resp = client.get(f'/v1/nodes/{child_id}', headers=authed_headers)
        assert resp.status_code == 404

        # Verify container still exists and doesn't have the child anymore
        resp = client.get(f'/v1/nodes/{container_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert len(resp.json()['children']) == 0

        # Verify tag association is gone (optional, but good for thoroughness)
        resp = client.get(f'/v1/tags/{tag_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert len(resp.json()['nodes']) == 0

    def test_delete_not_found(self, client, authed_headers):
        resp = client.delete('/v1/nodes/99999', headers=authed_headers)
        assert resp.status_code == 404

    def test_delete_container_orphans_children_when_no_orphan_location(self, client, app, make_node, authed_headers, monkeypatch):
        monkeypatch.setitem(app.app.config, 'ORPHAN_LOCATION', None)
        container_id = make_node('container', is_container=True)
        child_id = make_node('child', parent_id=container_id)

        resp = client.delete(f'/v1/nodes/{container_id}', headers=authed_headers)
        assert resp.status_code == 200

        resp = client.get(f'/v1/nodes/{child_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] is None

    def test_delete_container_reassigns_children_to_existing_configured_container(self, client, app, make_node, authed_headers, monkeypatch):
        monkeypatch.setitem(app.app.config, 'ORPHAN_LOCATION', 'Lost and Found')
        source_id = make_node('source', is_container=True)
        target_id = make_node('Lost and Found', is_container=True)
        child_id = make_node('child', parent_id=source_id)

        resp = client.delete(f'/v1/nodes/{source_id}', headers=authed_headers)
        assert resp.status_code == 200

        resp = client.get(f'/v1/nodes/{child_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] == target_id

    def test_delete_container_creates_configured_reassignment_container_when_missing(self, client, engine, app, make_node, authed_headers, monkeypatch):
        monkeypatch.setitem(app.app.config, 'ORPHAN_LOCATION', 'Lost and Found')
        source_id = make_node('source', is_container=True)
        child_id = make_node('child', parent_id=source_id)

        resp = client.delete(f'/v1/nodes/{source_id}', headers=authed_headers)
        assert resp.status_code == 200

        with engine.connect() as conn:
            row = (
                conn.execute(
                    text('SELECT id FROM nodes WHERE label = :label AND is_container = 1'),
                    {'label': 'Lost and Found'},
                )
                .mappings()
                .first()
            )
        assert row is not None

        resp = client.get(f'/v1/nodes/{child_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] == base62.encode(row['id'])

        resp = client.get(f'/v1/nodes/{base62.encode(row["id"])}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] is None

    def test_delete_configured_container_orphans_its_own_children(self, client, app, make_node, authed_headers, monkeypatch):
        monkeypatch.setitem(app.app.config, 'ORPHAN_LOCATION', 'Lost and Found')
        source_id = make_node('Lost and Found', is_container=True)
        child_id = make_node('child', parent_id=source_id)

        resp = client.delete(f'/v1/nodes/{source_id}', headers=authed_headers)
        assert resp.status_code == 200

        resp = client.get(f'/v1/nodes/{child_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] is None


def test_count_nodes_returns_int(app):
    with app.app.app_context():
        from binctl_server.db.flask import count_nodes

        result = count_nodes()
        assert isinstance(result, int)
