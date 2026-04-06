from __future__ import annotations


class TestTagCreate:
    def test_create_tag(self, client):
        resp = client.post('/v1/tags', json={'name': 'electronics'})
        assert resp.status_code == 201
        body = resp.json()
        assert body['name'] == 'electronics'
        assert body['id'] is not None
        assert body['created_at'] is not None
        assert body['updated_at'] is not None

    def test_create_duplicate(self, client):
        client.post('/v1/tags', json={'name': 'unique'})
        resp = client.post('/v1/tags', json={'name': 'unique'})
        assert resp.status_code == 409

    def test_create_missing_name(self, client):
        resp = client.post('/v1/tags', json={})
        assert resp.status_code == 400


class TestTagGet:
    def test_get_detail_no_nodes(self, client, make_tag):
        tag_id = make_tag('lonely')
        resp = client.get(f'/v1/tags/{tag_id}')
        assert resp.status_code == 200
        body = resp.json()
        assert body['name'] == 'lonely'
        assert body['nodes'] == []

    def test_get_detail_with_nodes(self, client, make_node, make_tag):
        tag_id = make_tag('used')
        node_id = make_node('item', tag_ids=[tag_id])
        resp = client.get(f'/v1/tags/{tag_id}')
        assert resp.status_code == 200
        body = resp.json()
        assert len(body['nodes']) == 1
        assert body['nodes'][0]['id'] == node_id

    def test_get_not_found(self, client):
        resp = client.get('/v1/tags/99999')
        assert resp.status_code == 404


class TestTagList:
    def test_list_empty(self, client):
        resp = client.get('/v1/tags')
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == 0
        assert body['items'] == []

    def test_list_pagination(self, client, make_tag):
        make_tag('alpha')
        make_tag('beta')
        make_tag('gamma')
        resp = client.get('/v1/tags', params={'limit': 2, 'offset': 0})
        assert resp.status_code == 200
        body = resp.json()
        assert body['total'] == 3
        assert len(body['items']) == 2
        assert body['limit'] == 2
        assert body['offset'] == 0


class TestTagPatch:
    def test_patch_rename(self, client, make_tag):
        tag_id = make_tag('oldname')
        resp = client.patch(f'/v1/tags/{tag_id}', json={'name': 'newname'})
        assert resp.status_code == 200
        assert resp.json()['name'] == 'newname'

    def test_patch_rename_conflict(self, client, make_tag):
        make_tag('taken')
        tag_id = make_tag('other')
        resp = client.patch(f'/v1/tags/{tag_id}', json={'name': 'taken'})
        assert resp.status_code == 409

    def test_patch_not_found(self, client):
        resp = client.patch('/v1/tags/99999', json={'name': 'x'})
        assert resp.status_code == 404
