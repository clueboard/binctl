import pytest
from sqlalchemy import text

from binctl_server import db
from binctl_server.db.engine import engine


class TestCreateUser:
    def test_inserts_row(self, clean_db):
        db.direct.create_user('alice', 'secret')
        rows = db.direct.fetch_all_users()
        assert any(r['username'] == 'alice' for r in rows)

    def test_duplicate_username_raises(self, clean_db):
        db.direct.create_user('bob', 'pass')
        with pytest.raises(Exception):
            db.direct.create_user('bob', 'other')

    def test_no_password_stores_sentinel(self, clean_db):
        user_id = db.direct.create_user('tokenonly', password=None)
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text('SELECT password_hash FROM users WHERE id = :id'),
                    {'id': user_id},
                )
                .mappings()
                .first()
            )
        assert row is not None
        assert row['password_hash'] == '!'


class TestFetchAllUsers:
    def test_empty(self, clean_db):
        assert list(db.direct.fetch_all_users()) == []

    def test_returns_all_users_in_id_order(self, clean_db):
        db.direct.create_user('alice', 'pass')
        db.direct.create_user('bob', 'pass')
        rows = db.direct.fetch_all_users()
        assert [r['username'] for r in rows] == ['alice', 'bob']

    def test_row_contains_expected_fields(self, clean_db):
        db.direct.create_user('carol', 'pass')
        row = db.direct.fetch_all_users()[0]
        assert {'id', 'username', 'created_at', 'last_login_at'} <= set(row.keys())


class TestFetchTokensForUsername:
    def test_unknown_user_returns_none(self, clean_db):
        assert db.direct.fetch_tokens_for_username('nobody') is None

    def test_user_with_no_tokens_returns_empty_list(self, clean_db):
        db.direct.create_user('alice', 'pass')
        result = db.direct.fetch_tokens_for_username('alice')
        assert result is not None
        assert list(result) == []

    def test_returns_tokens_for_user(self, clean_db):
        uid = db.direct.create_user('alice', 'pass')
        db.direct.create_token(uid)
        db.direct.create_token(uid)
        rows = db.direct.fetch_tokens_for_username('alice')
        assert rows is not None
        assert len(rows) == 2

    def test_does_not_return_other_users_tokens(self, clean_db):
        uid_a = db.direct.create_user('alice', 'pass')
        db.direct.create_user('bob', 'pass')
        db.direct.create_token(uid_a)
        rows = db.direct.fetch_tokens_for_username('bob')
        assert rows is not None
        assert list(rows) == []

    def test_row_contains_expected_fields(self, clean_db):
        uid = db.direct.create_user('alice', 'pass')
        db.direct.create_token(uid)
        tokens = db.direct.fetch_tokens_for_username('alice')
        assert tokens is not None
        row = tokens[0]
        assert {'id', 'token', 'created_at', 'last_used_at', 'expires_at'} <= set(row.keys())


class TestRevokeTokensForUsername:
    def test_unknown_user_returns_none(self, clean_db):
        assert db.direct.revoke_tokens_for_username('nobody') is None

    def test_user_with_no_tokens_returns_zero(self, clean_db):
        db.direct.create_user('alice', 'pass')
        assert db.direct.revoke_tokens_for_username('alice') == 0

    def test_revokes_all_tokens_and_returns_count(self, clean_db):
        uid = db.direct.create_user('alice', 'pass')
        db.direct.create_token(uid)
        db.direct.create_token(uid)
        assert db.direct.revoke_tokens_for_username('alice') == 2

    def test_tokens_are_deleted(self, clean_db):
        uid = db.direct.create_user('alice', 'pass')
        db.direct.create_token(uid)
        db.direct.revoke_tokens_for_username('alice')
        assert db.direct.fetch_tokens_for_username('alice') == []

    def test_does_not_revoke_other_users_tokens(self, clean_db):
        uid_a = db.direct.create_user('alice', 'pass')
        uid_b = db.direct.create_user('bob', 'pass')
        db.direct.create_token(uid_a)
        db.direct.create_token(uid_b)
        db.direct.revoke_tokens_for_username('alice')
        bob_tokens = db.direct.fetch_tokens_for_username('bob')
        assert bob_tokens is not None and len(bob_tokens) == 1


class TestUpdatePassword:
    def test_updates_password(self, clean_db):
        db.direct.create_user('alice', 'oldpass')
        result = db.direct.update_password('alice', 'newpass')
        assert result is True
        with engine.connect() as conn:
            row = (
                conn.execute(
                    text('SELECT password_hash FROM users WHERE username = :u'),
                    {'u': 'alice'},
                )
                .mappings()
                .first()
            )
        assert row is not None
        assert row['password_hash'] != 'oldpass'
        assert row['password_hash'].startswith('scrypt:')

    def test_unknown_user_returns_false(self, clean_db):
        result = db.direct.update_password('nobody', 'newpass')
        assert result is False
