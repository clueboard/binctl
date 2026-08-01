def test_server_system_config_and_environment_precedence(tmp_path, monkeypatch):
    import binctl_server.web as web

    config_file = tmp_path / 'binctl.conf'
    config_file.write_text('[general]\ncors_max_age = 120\norphan_location = System Bin\n')
    monkeypatch.setattr(web, '_SYSTEM_CONFIG_FILE', config_file)
    for name in web._CONFIG_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('CORS_MAX_AGE', '300')

    config = web._load_config()

    assert config['cors_max_age'] == '300'
    assert config['orphan_location'] == 'System Bin'


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
