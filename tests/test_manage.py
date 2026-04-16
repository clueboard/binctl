from unittest.mock import MagicMock, patch

import pytest

import manage


def _mock_cli(**args):
    """Build a mock milc cli object with cli.args populated."""
    mock = MagicMock()
    for key, val in args.items():
        setattr(mock.args, key, val)
    return mock


class TestListUsers:
    def test_empty(self):
        mock_cli = _mock_cli()
        with patch.object(manage._db, 'fetch_all_users', return_value=[]):
            manage.list_users(mock_cli)
        mock_cli.log.info.assert_called_once_with('No users.')

    def test_with_users(self):
        mock_cli = _mock_cli()
        rows = [{'id': 1, 'username': 'alice', 'created_at': '2024-01-01', 'last_login_at': None}]
        with patch.object(manage._db, 'fetch_all_users', return_value=rows):
            manage.list_users(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert 'alice' in output


class TestListTokens:
    def test_user_not_found(self):
        mock_cli = _mock_cli(username='nobody')
        with patch.object(manage._db, 'fetch_tokens_for_username', return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                manage.list_tokens(mock_cli)
        assert exc_info.value.code == 1
        mock_cli.log.error.assert_called_once()

    def test_no_tokens(self):
        mock_cli = _mock_cli(username='alice')
        with patch.object(manage._db, 'fetch_tokens_for_username', return_value=[]):
            manage.list_tokens(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert 'No tokens' in output

    def test_with_tokens(self):
        mock_cli = _mock_cli(username='alice')
        rows = [{'id': 1, 'token': '****abcd', 'created_at': '2024-01-01', 'last_used_at': None, 'expires_at': None}]
        with patch.object(manage._db, 'fetch_tokens_for_username', return_value=rows):
            manage.list_tokens(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert 'abcd' in output


class TestRevokeTokens:
    def test_user_not_found(self):
        mock_cli = _mock_cli(username='nobody')
        with patch.object(manage._db, 'revoke_tokens_for_username', return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                manage.revoke_tokens(mock_cli)
        assert exc_info.value.code == 1
        mock_cli.log.error.assert_called_once()

    def test_revoke(self):
        mock_cli = _mock_cli(username='alice')
        with patch.object(manage._db, 'revoke_tokens_for_username', return_value=3):
            manage.revoke_tokens(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert '3' in output


class TestCreateUser:
    def test_success(self):
        mock_cli = _mock_cli()
        with (
            patch('builtins.input', return_value='newuser'),
            patch('getpass.getpass', return_value='secret'),
            patch.object(manage._db, 'create_user', return_value=42),
        ):
            manage.create_user(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert 'newuser' in output

    def test_empty_username(self):
        mock_cli = _mock_cli()
        with patch('builtins.input', return_value=''):
            with pytest.raises(SystemExit) as exc_info:
                manage.create_user(mock_cli)
        assert exc_info.value.code == 1

    def test_password_mismatch(self):
        mock_cli = _mock_cli()
        with patch('builtins.input', return_value='alice'), patch('getpass.getpass', side_effect=['pass1', 'pass2']):
            with pytest.raises(SystemExit) as exc_info:
                manage.create_user(mock_cli)
        assert exc_info.value.code == 1
        error_msg = mock_cli.log.error.call_args[0][0]
        assert 'match' in error_msg

    def test_short_password_warns(self):
        mock_cli = _mock_cli()
        with (
            patch('builtins.input', return_value='alice'),
            patch('getpass.getpass', return_value='abc'),
            patch.object(manage._db, 'create_user', return_value=42),
        ):
            manage.create_user(mock_cli)
        mock_cli.log.warning.assert_called_once()
        assert 'short' in mock_cli.log.warning.call_args[0][0]

    def test_db_error(self):
        mock_cli = _mock_cli()
        with (
            patch('builtins.input', return_value='alice'),
            patch('getpass.getpass', return_value='secret'),
            patch.object(manage._db, 'create_user', side_effect=Exception('duplicate')),
        ):
            with pytest.raises(SystemExit) as exc_info:
                manage.create_user(mock_cli)
        assert exc_info.value.code == 1
