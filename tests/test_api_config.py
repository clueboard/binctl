class TestGetConfig:
    def test_returns_orphan_location_when_set(self, client, app, authed_headers, monkeypatch):
        monkeypatch.setitem(app.app.config, 'ORPHAN_LOCATION', 'Lost and Found')
        resp = client.get('/v1/config', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json() == {'orphan_location': 'Lost and Found'}

    def test_returns_null_when_not_set(self, client, app, authed_headers, monkeypatch):
        monkeypatch.setitem(app.app.config, 'ORPHAN_LOCATION', None)
        resp = client.get('/v1/config', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json() == {'orphan_location': None}

    def test_requires_authentication(self, client):
        resp = client.get('/v1/config')
        assert resp.status_code == 401
