from __future__ import annotations

import pytest
from sqlalchemy import text

from auth import hash_password, hash_token
from db.direct import (
    create_user,
    fetch_all_users,
    fetch_tokens_for_username,
    revoke_tokens_for_username,
)


def _insert_user(engine, username: str, password: str = 'pass') -> int:
    with engine.connect() as conn:
        result = conn.execute(
            text('INSERT INTO users (username, password_hash) VALUES (:u, :h)'),
            {'u': username, 'h': hash_password(password)},
        )
        conn.commit()
    return result.lastrowid


def _insert_token(engine, user_id: int, token: str = 'sometoken') -> None:
    with engine.connect() as conn:
        conn.execute(
            text('INSERT INTO tokens (user_id, token_hash, token_suffix) VALUES (:uid, :th, :ts)'),
            {'uid': user_id, 'th': hash_token(token), 'ts': token[-4:]},
        )
        conn.commit()


class TestCreateUser:
    def test_inserts_row(self, engine, clean_db):
        create_user('alice', hash_password('secret'))
        with engine.connect() as conn:
            row = conn.execute(
                text('SELECT username FROM users WHERE username = :u'),
                {'u': 'alice'},
            ).first()
        assert row is not None

    def test_duplicate_username_raises(self, engine, clean_db):
        create_user('bob', hash_password('pass'))
        with pytest.raises(Exception):
            create_user('bob', hash_password('other'))


class TestFetchAllUsers:
    def test_empty(self, clean_db):
        assert list(fetch_all_users()) == []

    def test_returns_all_users_in_id_order(self, engine, clean_db):
        _insert_user(engine, 'alice')
        _insert_user(engine, 'bob')
        rows = fetch_all_users()
        assert [r['username'] for r in rows] == ['alice', 'bob']

    def test_row_contains_expected_fields(self, engine, clean_db):
        _insert_user(engine, 'carol')
        row = fetch_all_users()[0]
        assert {'id', 'username', 'created_at', 'last_login_at'} <= set(row.keys())


class TestFetchTokensForUsername:
    def test_unknown_user_returns_none(self, clean_db):
        assert fetch_tokens_for_username('nobody') is None

    def test_user_with_no_tokens_returns_empty_list(self, engine, clean_db):
        _insert_user(engine, 'alice')
        result = fetch_tokens_for_username('alice')
        assert result is not None
        assert list(result) == []

    def test_returns_tokens_for_user(self, engine, clean_db):
        uid = _insert_user(engine, 'alice')
        _insert_token(engine, uid, 'token_one')
        _insert_token(engine, uid, 'token_two')
        rows = fetch_tokens_for_username('alice')
        assert rows is not None
        assert len(rows) == 2

    def test_does_not_return_other_users_tokens(self, engine, clean_db):
        uid_a = _insert_user(engine, 'alice')
        _insert_user(engine, 'bob')
        _insert_token(engine, uid_a, 'alicetoken')
        rows = fetch_tokens_for_username('bob')
        assert rows is not None
        assert list(rows) == []

    def test_row_contains_expected_fields(self, engine, clean_db):
        uid = _insert_user(engine, 'alice')
        _insert_token(engine, uid)
        tokens = fetch_tokens_for_username('alice')
        assert tokens is not None
        row = tokens[0]
        assert {'id', 'token_suffix', 'created_at', 'last_used_at', 'expires_at'} <= set(row.keys())


class TestRevokeTokensForUsername:
    def test_unknown_user_returns_none(self, clean_db):
        assert revoke_tokens_for_username('nobody') is None

    def test_user_with_no_tokens_returns_zero(self, engine, clean_db):
        _insert_user(engine, 'alice')
        assert revoke_tokens_for_username('alice') == 0

    def test_revokes_all_tokens_and_returns_count(self, engine, clean_db):
        uid = _insert_user(engine, 'alice')
        _insert_token(engine, uid, 'tok1')
        _insert_token(engine, uid, 'tok2')
        assert revoke_tokens_for_username('alice') == 2

    def test_tokens_are_deleted(self, engine, clean_db):
        uid = _insert_user(engine, 'alice')
        _insert_token(engine, uid)
        revoke_tokens_for_username('alice')
        with engine.connect() as conn:
            count = conn.execute(
                text('SELECT COUNT(*) FROM tokens WHERE user_id = :uid'), {'uid': uid}
            ).scalar()
        assert count == 0

    def test_does_not_revoke_other_users_tokens(self, engine, clean_db):
        uid_a = _insert_user(engine, 'alice')
        uid_b = _insert_user(engine, 'bob')
        _insert_token(engine, uid_a, 'alicetok')
        _insert_token(engine, uid_b, 'bobtok__')
        revoke_tokens_for_username('alice')
        with engine.connect() as conn:
            count = conn.execute(
                text('SELECT COUNT(*) FROM tokens WHERE user_id = :uid'), {'uid': uid_b}
            ).scalar()
        assert count == 1
