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


class TestNodePatch:
    def test_patch_label(self, client, make_node, authed_headers):
        node_id = make_node('old label')
        resp = client.patch(f'/v1/nodes/{node_id}', json={'label': 'new label'}, headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['label'] == 'new label'

    def test_patch_not_found(self, client, authed_headers):
        resp = client.patch('/v1/nodes/99999', json={'label': 'x'}, headers=authed_headers)
        assert resp.status_code == 404

    def test_patch_set_parent(self, client, make_node, authed_headers):
        container_id = make_node('container', is_container=True)
        node_id = make_node('node')
        resp = client.patch(f'/v1/nodes/{node_id}', json={'parent_id': container_id}, headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] == container_id

    def test_patch_clear_parent(self, client, make_node, authed_headers):
        container_id = make_node('container', is_container=True)
        node_id = make_node('node', parent_id=container_id)
        resp = client.patch(f'/v1/nodes/{node_id}', json={'parent_id': None}, headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] is None

    def test_patch_self_parent(self, client, make_node, authed_headers):
        node_id = make_node('node', is_container=True)
        resp = client.patch(f'/v1/nodes/{node_id}', json={'parent_id': node_id}, headers=authed_headers)
        assert resp.status_code == 400

    def test_patch_cycle(self, client, make_node, authed_headers):
        # A (container) → B; try to set B as parent of A
        a_id = make_node('A', is_container=True)
        b_id = make_node('B', is_container=True, parent_id=a_id)
        resp = client.patch(f'/v1/nodes/{a_id}', json={'parent_id': b_id}, headers=authed_headers)
        assert resp.status_code == 400

    def test_patch_indirect_cycle(self, client, make_node, authed_headers):
        # A → B → C; try to set C as parent of A
        a_id = make_node('A', is_container=True)
        b_id = make_node('B', is_container=True, parent_id=a_id)
        c_id = make_node('C', is_container=True, parent_id=b_id)
        resp = client.patch(f'/v1/nodes/{a_id}', json={'parent_id': c_id}, headers=authed_headers)
        assert resp.status_code == 400

    def test_patch_replace_tags(self, client, make_node, make_tag, authed_headers):
        t1 = make_tag('tag1')
        t2 = make_tag('tag2')
        t3 = make_tag('tag3')
        node_id = make_node('node', tag_ids=[t1, t2])
        resp = client.patch(f'/v1/nodes/{node_id}', json={'tag_ids': [t2, t3]}, headers=authed_headers)
        assert resp.status_code == 200
        tag_names = {t['name'] for t in resp.json()['tags']}
        assert tag_names == {'tag2', 'tag3'}

    def test_patch_clear_tags(self, client, make_node, make_tag, authed_headers):
        tag_id = make_tag('removeme')
        node_id = make_node('node', tag_ids=[tag_id])
        resp = client.patch(f'/v1/nodes/{node_id}', json={'tag_ids': []}, headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['tags'] == []

    def test_patch_nonexistent_tag(self, client, make_node, authed_headers):
        node_id = make_node('item')
        resp = client.patch(f'/v1/nodes/{node_id}', json={'tag_ids': [99999]}, headers=authed_headers)
        assert resp.status_code == 400

    def test_patch_remove_container_with_children_rejected(self, client, make_node, authed_headers):
        parent_id = make_node('box', is_container=True)
        make_node('item', parent_id=parent_id)
        resp = client.patch(f'/v1/nodes/{parent_id}', json={'is_container': False}, headers=authed_headers)
        assert resp.status_code == 400

    def test_patch_clear_description(self, client, make_node, authed_headers):
        """PATCH with description=null must clear the description to None."""
        node_id = make_node('item', description='initial description')
        resp = client.patch(
            f'/v1/nodes/{node_id}',
            json={'description': None},
            headers=authed_headers,
        )
        assert resp.status_code == 200
        assert resp.json()['description'] is None


def test_count_nodes_returns_int(app):
    with app.app.app_context():
        from db.flask import count_nodes
        result = count_nodes()
        assert isinstance(result, int)
