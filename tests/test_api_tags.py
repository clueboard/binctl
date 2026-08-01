class TestTagCreate:
    def test_create_tag(self, client, authed_headers):
        resp = client.post('/v1/tags', json={'name': 'electronics'}, headers=authed_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body['name'] == 'electronics'
        assert body['id'] is not None
        assert body['created_at'] is not None
        assert body['updated_at'] is not None

    def test_create_duplicate(self, client, authed_headers):
        client.post('/v1/tags', json={'name': 'unique'}, headers=authed_headers)
        resp = client.post('/v1/tags', json={'name': 'unique'}, headers=authed_headers)
        assert resp.status_code == 409

    def test_create_missing_name(self, client, authed_headers):
        resp = client.post('/v1/tags', json={}, headers=authed_headers)
        assert resp.status_code == 400


class TestTagGet:
    def test_get_detail_no_nodes(self, client, make_tag, authed_headers):
        tag_id = make_tag('lonely')
        resp = client.get(f'/v1/tags/{tag_id}', headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['name'] == 'lonely'
        assert body['nodes'] == []

    def test_get_detail_with_nodes(self, client, make_node, make_tag, authed_headers):
        tag_id = make_tag('used')
        node_id = make_node('item', tag_ids=[tag_id])
        resp = client.get(f'/v1/tags/{tag_id}', headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body['nodes']) == 1
        assert body['nodes'][0]['id'] == node_id

    def test_get_not_found(self, client, authed_headers):
        resp = client.get('/v1/tags/99999', headers=authed_headers)
        assert resp.status_code == 404


class TestTagList:
    def test_list_empty(self, client, authed_headers):
        resp = client.get('/v1/tags', headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == 0
        assert body['items'] == []

    def test_list_pagination(self, client, make_tag, authed_headers):
        make_tag('alpha')
        make_tag('beta')
        make_tag('gamma')
        resp = client.get('/v1/tags', params={'limit': 2, 'offset': 0}, headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == 3
        assert len(body['items']) == 2
        assert body['limit'] == 2
        assert body['offset'] == 0

    def test_list_total_matches_items_count(self, client, make_tag, authed_headers):
        make_tag('alpha')
        make_tag('beta')
        resp = client.get('/v1/tags', params={'limit': 100}, headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == len(body['items'])


class TestTagPatch:
    def test_patch_rename(self, client, make_tag, authed_headers):
        tag_id = make_tag('oldname')
        resp = client.patch(f'/v1/tags/{tag_id}', json={'name': 'newname'}, headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['name'] == 'newname'

    def test_patch_rename_conflict(self, client, make_tag, authed_headers):
        make_tag('taken')
        tag_id = make_tag('other')
        resp = client.patch(f'/v1/tags/{tag_id}', json={'name': 'taken'}, headers=authed_headers)
        assert resp.status_code == 409

    def test_patch_missing_name(self, client, make_tag, authed_headers):
        tag_id = make_tag('sometag')
        resp = client.patch(f'/v1/tags/{tag_id}', json={}, headers=authed_headers)
        assert resp.status_code == 400

    def test_patch_empty_name(self, client, make_tag, authed_headers):
        tag_id = make_tag('sometag')
        resp = client.patch(f'/v1/tags/{tag_id}', json={'name': ''}, headers=authed_headers)
        assert resp.status_code == 400

    def test_patch_not_found(self, client, authed_headers):
        resp = client.patch('/v1/tags/99999', json={'name': 'x'}, headers=authed_headers)
        assert resp.status_code == 404


class TestTagDeleteUnauthenticated:
    def test_delete_requires_auth(self, client):
        resp = client.delete('/v1/tags/1')
        assert resp.status_code == 401


class TestTagDelete:
    def test_delete_success(self, client, make_tag, make_node, authed_headers):
        tag_id = make_tag('disposable')
        node_id = make_node('item', tag_ids=[tag_id])

        resp = client.delete(f'/v1/tags/{tag_id}', headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['deleted']['total'] == 2  # 1 tag + 1 association
        assert body['deleted']['associations'] == 1

        # Tag is gone
        resp = client.get(f'/v1/tags/{tag_id}', headers=authed_headers)
        assert resp.status_code == 404

        # Node still exists, tag association removed
        resp = client.get(f'/v1/nodes/{node_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['tags'] == []

    def test_delete_tag_no_associations(self, client, make_tag, authed_headers):
        tag_id = make_tag('unused')
        resp = client.delete(f'/v1/tags/{tag_id}', headers=authed_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body['deleted']['total'] == 1
        assert body['deleted']['associations'] == 0

    def test_delete_not_found(self, client, authed_headers):
        resp = client.delete('/v1/tags/99999', headers=authed_headers)
        assert resp.status_code == 404


def test_count_tags_returns_int(app):
    with app.app.app_context():
        from binctl_server.db.flask import count_tags

        result = count_tags()
        assert isinstance(result, int)
