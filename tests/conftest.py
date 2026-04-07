from __future__ import annotations

import os

# Must be set before any application import — db.py reads DATABASE_URL at module level
os.environ['DATABASE_URL'] = 'sqlite://'

import pytest  # noqa: E402
from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import db as _db  # noqa: E402
from web import create_app  # noqa: E402

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    label        TEXT NOT NULL,
    description  TEXT,
    is_container INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS edges (
    parent_id  INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    child_id   INTEGER NOT NULL UNIQUE REFERENCES nodes(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (parent_id, child_id),
    CHECK (parent_id <> child_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tag_node (
    tag_id     INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    node_id    INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (tag_id, node_id)
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tokens (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token        TEXT UNIQUE NOT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    expires_at   TIMESTAMP
);
"""

# Shared in-memory SQLite engine (StaticPool so all connections share one DB)
_sqlite_engine = create_engine(
    'sqlite://',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
    future=True,
)


@event.listens_for(_sqlite_engine, 'connect')
def _enable_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON')
    cursor.close()


# Apply schema once at import time
with _sqlite_engine.connect() as _conn:
    for _stmt in _SQLITE_SCHEMA.strip().split(';'):
        _stmt = _stmt.strip()
        if _stmt:
            _conn.execute(text(_stmt))
    _conn.commit()

# Redirect db module to use our SQLite engine
_db.engine = _sqlite_engine


@pytest.fixture(scope='session')
def app():
    return create_app()


@pytest.fixture(scope='session')
def engine():
    return _sqlite_engine


@pytest.fixture()
def clean_db(engine):
    with engine.connect() as conn:
        # Delete in dependency order so FK constraints are satisfied
        conn.execute(text('DELETE FROM tokens'))
        conn.execute(text('DELETE FROM users'))
        conn.execute(text('DELETE FROM tag_node'))
        conn.execute(text('DELETE FROM edges'))
        conn.execute(text('DELETE FROM nodes'))
        conn.execute(text('DELETE FROM tags'))
        conn.commit()


@pytest.fixture()
def client(app, clean_db):
    return app.test_client()


@pytest.fixture()
def auth_token(engine, clean_db):
    import secrets

    from auth import hash_password

    token = secrets.token_urlsafe(32)
    pw_hash = hash_password('testpass')
    with engine.connect() as conn:
        result = conn.execute(
            text("INSERT INTO users (username, password_hash) VALUES ('testuser', :h)"),
            {'h': pw_hash},
        )
        user_id = result.lastrowid
        conn.execute(
            text('INSERT INTO tokens (user_id, token) VALUES (:uid, :tok)'),
            {'uid': user_id, 'tok': token},
        )
        conn.commit()
    return token


@pytest.fixture()
def authed_headers(auth_token):
    return {'Authorization': f'Bearer {auth_token}'}


@pytest.fixture()
def make_node(client, authed_headers):
    def _inner(label='test node', **kwargs):
        resp = client.post('/v1/nodes', json={'label': label, **kwargs}, headers=authed_headers)
        assert resp.status_code == 201, resp.json()
        return resp.json()['id']

    return _inner


@pytest.fixture()
def make_tag(client, authed_headers):
    def _inner(name='test tag'):
        resp = client.post('/v1/tags', json={'name': name}, headers=authed_headers)
        assert resp.status_code == 201, resp.json()
        return resp.json()['id']

    return _inner
