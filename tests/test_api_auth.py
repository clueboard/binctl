from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from db.direct import create_token, create_user


class TestLogin:
    def test_login_success(self, client, clean_db):
        create_user('alice', 'secret')
        resp = client.post('/v1/auth/login', json={'username': 'alice', 'password': 'secret'})
        assert resp.status_code == 200
        body = resp.json()
        assert 'token' in body
        assert isinstance(body['token'], str)
        assert len(body['token']) > 10

    def test_login_wrong_password(self, client, clean_db):
        create_user('bob', 'correct')
        resp = client.post('/v1/auth/login', json={'username': 'bob', 'password': 'wrong'})
        assert resp.status_code == 401

    def test_login_unknown_user(self, client, clean_db):
        resp = client.post('/v1/auth/login', json={'username': 'nobody', 'password': 'x'})
        assert resp.status_code == 401

    def test_login_token_works_on_protected_endpoint(self, client, clean_db):
        create_user('carol', 'pass')
        login_resp = client.post('/v1/auth/login', json={'username': 'carol', 'password': 'pass'})
        token = login_resp.json()['token']
        resp = client.get('/v1/nodes', headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 200

    def test_login_token_has_expiry(self, app, client, clean_db, engine):
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
        lifetime_days = app.app.config['SESSION_LIFETIME_DAYS']
        expected = before + timedelta(days=lifetime_days)
        assert abs((expires_at - expected).total_seconds()) < 5


class TestExpiry:
    def test_null_expiry_is_accepted(self, client, clean_db):
        uid = create_user('noexpiry_user', 'pass')
        token = create_token(uid)
        resp = client.get('/v1/nodes', headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 200

    def test_expired_token_returns_401(self, client, clean_db):
        uid = create_user('expiry_user', 'pass')
        token = create_token(uid, expires_at='2000-01-01 00:00:00')
        resp = client.get('/v1/nodes', headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 401


class TestProtection:
    def test_no_token_returns_401(self, client, clean_db):
        resp = client.get('/v1/nodes')
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client, clean_db):
        resp = client.get('/v1/nodes', headers={'Authorization': 'Bearer badtoken'})
        assert resp.status_code == 401

    def test_malformed_header_returns_401(self, client, clean_db):
        resp = client.get('/v1/nodes', headers={'Authorization': 'notbearer token'})
        assert resp.status_code == 401


class TestLogout:
    def test_logout_success(self, client, authed_headers):
        resp = client.post('/v1/auth/logout', headers=authed_headers)
        assert resp.status_code == 204

    def test_token_invalid_after_logout(self, client, authed_headers):
        client.post('/v1/auth/logout', headers=authed_headers)
        resp = client.get('/v1/nodes', headers=authed_headers)
        assert resp.status_code == 401

    def test_logout_requires_auth(self, client, clean_db):
        resp = client.post('/v1/auth/logout')
        assert resp.status_code == 401
