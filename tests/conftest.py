import os
from pathlib import Path

# Must be set before any application import — db reads DATABASE_URL at module level
os.environ['DATABASE_URL'] = 'sqlite://'

import pytest  # noqa: E402
from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from binctl_server import db as _db  # noqa: E402
from binctl_server.web import create_app  # noqa: E402

# Absolute path to schema file
_SCHEMA = Path(__file__).parent.parent / 'binctl_server' / 'db' / 'v1.sql'

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


# Load production schema
with open(_SCHEMA, 'r') as f:
    _schema_sql = f.read()

# Apply schema once at import time
with _sqlite_engine.connect() as _conn:
    for _stmt in _schema_sql.split(';'):
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
def auth_token(clean_db):
    from binctl_server.db.direct import create_token, create_user

    user_id = create_user('testuser', 'testpass')
    return create_token(user_id)


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
