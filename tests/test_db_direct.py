import pytest

from db.direct import (
    create_token,
    create_user,
    fetch_all_users,
    fetch_tokens_for_username,
    revoke_tokens_for_username,
)


class TestCreateUser:
    def test_inserts_row(self, clean_db):
        create_user('alice', 'secret')
        rows = fetch_all_users()
        assert any(r['username'] == 'alice' for r in rows)

    def test_duplicate_username_raises(self, clean_db):
        create_user('bob', 'pass')
        with pytest.raises(Exception):
            create_user('bob', 'other')


class TestFetchAllUsers:
    def test_empty(self, clean_db):
        assert list(fetch_all_users()) == []

    def test_returns_all_users_in_id_order(self, clean_db):
        create_user('alice', 'pass')
        create_user('bob', 'pass')
        rows = fetch_all_users()
        assert [r['username'] for r in rows] == ['alice', 'bob']

    def test_row_contains_expected_fields(self, clean_db):
        create_user('carol', 'pass')
        row = fetch_all_users()[0]
        assert {'id', 'username', 'created_at', 'last_login_at'} <= set(row.keys())


class TestFetchTokensForUsername:
    def test_unknown_user_returns_none(self, clean_db):
        assert fetch_tokens_for_username('nobody') is None

    def test_user_with_no_tokens_returns_empty_list(self, clean_db):
        create_user('alice', 'pass')
        result = fetch_tokens_for_username('alice')
        assert result is not None
        assert list(result) == []

    def test_returns_tokens_for_user(self, clean_db):
        uid = create_user('alice', 'pass')
        create_token(uid)
        create_token(uid)
        rows = fetch_tokens_for_username('alice')
        assert rows is not None
        assert len(rows) == 2

    def test_does_not_return_other_users_tokens(self, clean_db):
        uid_a = create_user('alice', 'pass')
        create_user('bob', 'pass')
        create_token(uid_a)
        rows = fetch_tokens_for_username('bob')
        assert rows is not None
        assert list(rows) == []

    def test_row_contains_expected_fields(self, clean_db):
        uid = create_user('alice', 'pass')
        create_token(uid)
        tokens = fetch_tokens_for_username('alice')
        assert tokens is not None
        row = tokens[0]
        assert {'id', 'token', 'created_at', 'last_used_at', 'expires_at'} <= set(row.keys())


class TestRevokeTokensForUsername:
    def test_unknown_user_returns_none(self, clean_db):
        assert revoke_tokens_for_username('nobody') is None

    def test_user_with_no_tokens_returns_zero(self, clean_db):
        create_user('alice', 'pass')
        assert revoke_tokens_for_username('alice') == 0

    def test_revokes_all_tokens_and_returns_count(self, clean_db):
        uid = create_user('alice', 'pass')
        create_token(uid)
        create_token(uid)
        assert revoke_tokens_for_username('alice') == 2

    def test_tokens_are_deleted(self, clean_db):
        uid = create_user('alice', 'pass')
        create_token(uid)
        revoke_tokens_for_username('alice')
        assert fetch_tokens_for_username('alice') == []

    def test_does_not_revoke_other_users_tokens(self, clean_db):
        uid_a = create_user('alice', 'pass')
        uid_b = create_user('bob', 'pass')
        create_token(uid_a)
        create_token(uid_b)
        revoke_tokens_for_username('alice')
        bob_tokens = fetch_tokens_for_username('bob')
        assert bob_tokens is not None and len(bob_tokens) == 1
