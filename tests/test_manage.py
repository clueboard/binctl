import os
import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

import binctl_server.manage as manage


def _mock_cli(**args):
    """Build a mock milc cli object with cli.args populated."""
    mock = MagicMock()
    for key, val in args.items():
        setattr(mock.args, key, val)
    return mock


class TestConfiguration:
    def test_no_arguments_does_not_require_database_url(self, tmp_path):
        env = os.environ.copy()
        env.pop('DATABASE_URL', None)
        env['PYTHON_DOTENV_DISABLED'] = '1'

        result = subprocess.run(
            [sys.executable, '-m', 'binctl_server.manage'],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert 'usage: manage.py' in result.stdout

    def test_help_does_not_require_database_url(self, tmp_path):
        env = os.environ.copy()
        env.pop('DATABASE_URL', None)
        env['PYTHON_DOTENV_DISABLED'] = '1'

        result = subprocess.run(
            [sys.executable, '-m', 'binctl_server.manage', '-h'],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert 'usage: manage.py' in result.stdout

    def test_explicit_config_file_supplies_database_url(self, tmp_path):
        config_file = tmp_path / 'binctl.conf'
        database_file = tmp_path / 'binctl.db'
        config_file.write_text(f'[general]\ndatabase_url = sqlite:///{database_file}\n')
        env = os.environ.copy()
        env.pop('DATABASE_URL', None)
        env['PYTHON_DOTENV_DISABLED'] = '1'

        result = subprocess.run(
            [sys.executable, '-m', 'binctl_server.manage', '--config-file', str(config_file), 'init-db'],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
        assert database_file.exists()


class TestListUsers:
    def test_empty(self):
        mock_cli = _mock_cli()
        with patch.object(manage.db.direct, 'fetch_all_users', return_value=[]):
            manage.list_users(mock_cli)
        mock_cli.log.info.assert_called_once_with('No users.')

    def test_with_users(self):
        mock_cli = _mock_cli()
        rows = [{'id': 1, 'username': 'alice', 'created_at': '2024-01-01', 'last_login_at': None}]
        with patch.object(manage.db.direct, 'fetch_all_users', return_value=rows):
            manage.list_users(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert 'alice' in output


class TestListTokens:
    def test_user_not_found(self):
        mock_cli = _mock_cli(username='nobody')
        with patch.object(manage.db.direct, 'fetch_tokens_for_username', return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                manage.list_tokens(mock_cli)
        assert exc_info.value.code == 1
        mock_cli.log.error.assert_called_once()

    def test_no_tokens(self):
        mock_cli = _mock_cli(username='alice')
        with patch.object(manage.db.direct, 'fetch_tokens_for_username', return_value=[]):
            manage.list_tokens(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert 'No tokens' in output

    def test_with_tokens(self):
        mock_cli = _mock_cli(username='alice')
        rows = [{'id': 1, 'token': '****abcd', 'created_at': '2024-01-01', 'last_used_at': None, 'expires_at': None}]
        with patch.object(manage.db.direct, 'fetch_tokens_for_username', return_value=rows):
            manage.list_tokens(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert 'abcd' in output


class TestRevokeTokens:
    def test_user_not_found(self):
        mock_cli = _mock_cli(username='nobody')
        with patch.object(manage.db.direct, 'revoke_tokens_for_username', return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                manage.revoke_tokens(mock_cli)
        assert exc_info.value.code == 1
        mock_cli.log.error.assert_called_once()

    def test_revoke(self):
        mock_cli = _mock_cli(username='alice')
        with patch.object(manage.db.direct, 'revoke_tokens_for_username', return_value=3):
            manage.revoke_tokens(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert '3' in output


class TestCreateUser:
    def test_success(self):
        mock_cli = _mock_cli(username='newuser', password='secret', token=False)
        with patch.object(manage.db.direct, 'create_user', return_value=42):
            manage.create_user(mock_cli)
        output = mock_cli.log.info.call_args[0][0]
        assert 'newuser' in output

    def test_empty_username(self):
        mock_cli = _mock_cli(username='', password='secret', token=False)
        with pytest.raises(SystemExit) as exc_info:
            manage.create_user(mock_cli)
        assert exc_info.value.code == 1

    def test_short_password_warns(self):
        mock_cli = _mock_cli(username='alice', password='abc', token=False)
        with patch.object(manage.db.direct, 'create_user', return_value=42):
            manage.create_user(mock_cli)
        mock_cli.log.warning.assert_called_once()
        assert 'short' in mock_cli.log.warning.call_args[0][0]

    def test_db_error(self):
        mock_cli = _mock_cli(username='alice', password='secret', token=False)
        with patch.object(manage.db.direct, 'create_user', side_effect=Exception('duplicate')):
            with pytest.raises(SystemExit) as exc_info:
                manage.create_user(mock_cli)
        assert exc_info.value.code == 1

    def test_token_flag_creates_token(self):
        mock_cli = _mock_cli(username='alice', password=None, token=True)
        with (
            patch.object(manage.db.direct, 'create_user', return_value=7) as mock_create,
            patch.object(manage.db.direct, 'create_token', return_value='rawtoken123') as mock_token,
        ):
            manage.create_user(mock_cli)
        mock_create.assert_called_once_with('alice', password=None)
        mock_token.assert_called_once_with(7)
        output = mock_cli.log.info.call_args[0][0]
        assert 'rawtoken123' in output

    def test_token_and_password_is_error(self):
        mock_cli = _mock_cli(username='alice', password='alsoset', token=True)
        with pytest.raises(SystemExit) as exc_info:
            manage.create_user(mock_cli)
        assert exc_info.value.code == 1
        mock_cli.log.error.assert_called_once()

    def test_no_token_flag_requires_password(self):
        mock_cli = _mock_cli(username='alice', password=None, token=False)
        with pytest.raises(SystemExit) as exc_info:
            manage.create_user(mock_cli)
        assert exc_info.value.code == 1
        mock_cli.log.error.assert_called_once()


class TestSetPassword:
    def test_success(self):
        mock_cli = _mock_cli(username='alice')
        with (
            patch('getpass.getpass', return_value='newpass123'),
            patch.object(manage.db.direct, 'update_password', return_value=True),
        ):
            manage.set_password(mock_cli)
        mock_cli.log.info.assert_called_once()

    def test_password_too_short(self):
        mock_cli = _mock_cli(username='alice')
        with patch('getpass.getpass', return_value='abc'):
            with pytest.raises(SystemExit) as exc_info:
                manage.set_password(mock_cli)
        assert exc_info.value.code == 1
        mock_cli.log.error.assert_called_once()

    def test_password_mismatch(self):
        mock_cli = _mock_cli(username='alice')
        with patch('getpass.getpass', side_effect=['longpass1', 'longpass2']):
            with pytest.raises(SystemExit) as exc_info:
                manage.set_password(mock_cli)
        assert exc_info.value.code == 1
        assert 'match' in mock_cli.log.error.call_args[0][0]

    def test_user_not_found(self):
        mock_cli = _mock_cli(username='nobody')
        with (
            patch('getpass.getpass', return_value='validpass'),
            patch.object(manage.db.direct, 'update_password', return_value=False),
        ):
            with pytest.raises(SystemExit) as exc_info:
                manage.set_password(mock_cli)
        assert exc_info.value.code == 1
        mock_cli.log.error.assert_called_once()
