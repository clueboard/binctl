from __future__ import annotations

from sqlalchemy import text

from auth import hash_password


def _create_user(engine, username: str, password: str) -> None:
    with engine.connect() as conn:
        conn.execute(
            text('INSERT INTO users (username, password_hash) VALUES (:u, :h)'),
            {'u': username, 'h': hash_password(password)},
        )
        conn.commit()


class TestLogin:
    def test_login_success(self, client, engine, clean_db):
        _create_user(engine, 'alice', 'secret')
        resp = client.post('/v1/auth/login', json={'username': 'alice', 'password': 'secret'})
        assert resp.status_code == 200
        body = resp.json()
        assert 'token' in body
        assert isinstance(body['token'], str)
        assert len(body['token']) > 10

    def test_login_wrong_password(self, client, engine, clean_db):
        _create_user(engine, 'bob', 'correct')
        resp = client.post('/v1/auth/login', json={'username': 'bob', 'password': 'wrong'})
        assert resp.status_code == 401

    def test_login_unknown_user(self, client, clean_db):
        resp = client.post('/v1/auth/login', json={'username': 'nobody', 'password': 'x'})
        assert resp.status_code == 401

    def test_login_token_works_on_protected_endpoint(self, client, engine, clean_db):
        _create_user(engine, 'carol', 'pass')
        login_resp = client.post('/v1/auth/login', json={'username': 'carol', 'password': 'pass'})
        token = login_resp.json()['token']
        resp = client.get('/v1/nodes', headers={'Authorization': f'Bearer {token}'})
        assert resp.status_code == 200


class TestExpiry:
    def test_null_expiry_is_accepted(self, client, engine, clean_db):
        with engine.connect() as conn:
            result = conn.execute(
                text('INSERT INTO users (username, password_hash) VALUES (:u, :h)'),
                {'u': 'noexpiry_user', 'h': hash_password('pass')},
            )
            conn.execute(
                text('INSERT INTO tokens (user_id, token, expires_at) VALUES (:uid, :tok, NULL)'),
                {'uid': result.lastrowid, 'tok': 'noexpirytoken123'},
            )
            conn.commit()
        resp = client.get('/v1/nodes', headers={'Authorization': 'Bearer noexpirytoken123'})
        assert resp.status_code == 200

    def test_expired_token_returns_401(self, client, engine, clean_db):
        with engine.connect() as conn:
            result = conn.execute(
                text('INSERT INTO users (username, password_hash) VALUES (:u, :h)'),
                {'u': 'expiry_user', 'h': hash_password('pass')},
            )
            conn.execute(
                text('INSERT INTO tokens (user_id, token, expires_at) VALUES (:uid, :tok, :exp)'),
                {'uid': result.lastrowid, 'tok': 'expiredtoken123', 'exp': '2000-01-01 00:00:00'},
            )
            conn.commit()
        resp = client.get('/v1/nodes', headers={'Authorization': 'Bearer expiredtoken123'})
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
