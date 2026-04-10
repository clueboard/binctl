import importlib

import pytest


@pytest.fixture()
def cors_client(monkeypatch):
    """Return a factory that creates a test client with given env vars set."""

    def _make(**env):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        from web import create_app

        app = create_app()
        return app.test_client()

    return _make


def test_wildcard_rejected(monkeypatch):
    monkeypatch.setenv('CORS_ORIGINS', '*')
    from web import create_app

    with pytest.raises(ValueError, match="CORS_ORIGINS='\\*' is not allowed"):
        create_app()


def test_credentials_header_present(cors_client):
    client = cors_client(CORS_ORIGINS='http://localhost:3000')
    resp = client.get(
        '/v1/nodes',
        headers={
            'Origin': 'http://localhost:3000',
            'Authorization': 'Bearer fake',
        },
    )
    assert resp.headers.get('Access-Control-Allow-Credentials') == 'true'


def test_origin_reflected(cors_client):
    client = cors_client(CORS_ORIGINS='http://localhost:3000')
    resp = client.get(
        '/v1/nodes',
        headers={
            'Origin': 'http://localhost:3000',
            'Authorization': 'Bearer fake',
        },
    )
    assert resp.headers.get('Access-Control-Allow-Origin') == 'http://localhost:3000'


def test_max_age_header(cors_client):
    client = cors_client(CORS_ORIGINS='http://localhost:3000', CORS_MAX_AGE='300')
    resp = client.options(
        '/v1/nodes',
        headers={
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get('Access-Control-Max-Age') == '300'


def test_default_max_age(cors_client):
    client = cors_client(CORS_ORIGINS='http://localhost:3000')
    resp = client.options(
        '/v1/nodes',
        headers={
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get('Access-Control-Max-Age') == '600'


def test_cors_max_age_invalid_env_raises_helpful_error(monkeypatch):
    """CORS_MAX_AGE with a non-integer value must raise ValueError naming the env var."""
    import web
    monkeypatch.setenv('CORS_MAX_AGE', 'auto')
    importlib.reload(web)
    with pytest.raises(ValueError, match='CORS_MAX_AGE'):
        web.create_app()
