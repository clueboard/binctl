import pytest


@pytest.fixture()
def session_client(monkeypatch):
    """Return a factory that creates a test client with SESSION_LIFETIME_DAYS set."""

    def _make(days: str):
        monkeypatch.setenv('SESSION_LIFETIME_DAYS', days)
        from binctl_server.web import create_app

        return create_app()

    return _make


def test_invalid_session_lifetime_non_integer(monkeypatch):
    monkeypatch.setenv('SESSION_LIFETIME_DAYS', 'forever')
    import binctl_server.web as web

    with pytest.raises(ValueError, match='SESSION_LIFETIME_DAYS'):
        web.create_app()


def test_invalid_session_lifetime_zero(monkeypatch):
    monkeypatch.setenv('SESSION_LIFETIME_DAYS', '0')
    import binctl_server.web as web

    with pytest.raises(ValueError, match='SESSION_LIFETIME_DAYS'):
        web.create_app()


def test_invalid_session_lifetime_negative(monkeypatch):
    monkeypatch.setenv('SESSION_LIFETIME_DAYS', '-1')
    import binctl_server.web as web

    with pytest.raises(ValueError, match='SESSION_LIFETIME_DAYS'):
        web.create_app()


def test_session_lifetime_override(session_client, clean_db, engine):
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import text

    from binctl_server.db.direct import create_user

    app = session_client('7')
    client = app.test_client()

    before = datetime.now(timezone.utc)
    create_user('dave', 'pass')
    resp = client.post('/v1/auth/login', json={'username': 'dave', 'password': 'pass'})
    assert resp.status_code == 200

    with engine.connect() as conn:
        row = conn.execute(text('SELECT expires_at FROM tokens')).mappings().first()
    assert row is not None
    expires_at = row['expires_at']
    assert expires_at is not None
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    expected = before + timedelta(days=app.app.config['SESSION_LIFETIME_DAYS'])
    assert abs((expires_at - expected).total_seconds()) < 5
