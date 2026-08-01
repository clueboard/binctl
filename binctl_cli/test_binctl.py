"""Tests for binctl CLI — verifies correct parameter names passed to generated client."""

import types
import unittest
from http import HTTPStatus
from unittest.mock import MagicMock, patch


def _make_cli_args(**kwargs):
    """Build a minimal args namespace."""
    defaults = {
        'base_url': 'http://localhost:5000',
        'label': None,
        'description': None,
        'is_container': None,
        'parent_id': None,
        'no_parent': False,
        'tag_id': None,
        'name': None,
        'node_id': None,
        'output': 'json',
        'verbose': False,
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_cli(args):
    mock_cli = MagicMock()
    mock_cli.args = args
    mock_cli.config.general.base_url = args.base_url
    mock_cli.config.general.token = 'test-token'
    mock_cli.config.general.username = None
    mock_cli.config.general.password = None
    return mock_cli


def _mock_response(parsed=None):
    """Build a mock Response with a successful status and the given parsed value."""
    response = MagicMock()
    response.status_code = HTTPStatus.OK
    response.parsed = parsed if parsed is not None else MagicMock(**{'to_dict.return_value': {}})
    return response


class TestNodeCreate(unittest.TestCase):
    def test_body_kwarg_not_json_body(self):
        """post_node_create.sync_detailed must be called with body=, not json_body=."""
        with patch('binctl_client.api.nodes.post_node_create.sync_detailed') as mock_sync:
            with patch('binctl_cli.cli.Client'):
                mock_sync.return_value = _mock_response()
                import binctl_cli.cli as bc

                with patch.object(bc, 'cli', _make_cli(_make_cli_args(label='test', tag_id=[]))):
                    bc._node_create()

                _, kwargs = mock_sync.call_args
                self.assertIn('body', kwargs, "Expected 'body' kwarg")
                self.assertNotIn('json_body', kwargs, "Found unexpected 'json_body' kwarg")


class TestNodeUpdate(unittest.TestCase):
    def test_body_kwarg_not_json_body(self):
        with patch('binctl_client.api.nodes.patch_node_update.sync_detailed') as mock_sync:
            with patch('binctl_cli.cli.Client'):
                mock_sync.return_value = _mock_response()
                import binctl_cli.cli as bc

                with patch.object(bc, 'cli', _make_cli(_make_cli_args(label='updated', node_id='1'))):
                    bc._node_update()

                _, kwargs = mock_sync.call_args
                self.assertIn('body', kwargs)
                self.assertNotIn('json_body', kwargs)


class TestTagCreate(unittest.TestCase):
    def test_body_kwarg_not_json_body(self):
        with patch('binctl_client.api.tags.post_tag_create.sync_detailed') as mock_sync:
            with patch('binctl_cli.cli.Client'):
                mock_sync.return_value = _mock_response()
                import binctl_cli.cli as bc

                with patch.object(bc, 'cli', _make_cli(_make_cli_args(name='mytag'))):
                    bc._tag_create()

                _, kwargs = mock_sync.call_args
                self.assertIn('body', kwargs)
                self.assertNotIn('json_body', kwargs)


class TestTagUpdate(unittest.TestCase):
    def test_body_kwarg_not_json_body(self):
        with patch('binctl_client.api.tags.patch_tag_update.sync_detailed') as mock_sync:
            mock_sync.return_value = _mock_response()
            import binctl_cli.cli as bc

            with patch.object(bc, 'cli', _make_cli(_make_cli_args(name='renamed', tag_id='1'))):
                bc._tag_update()

            _, kwargs = mock_sync.call_args
            self.assertIn('body', kwargs)
            self.assertNotIn('json_body', kwargs)


class TestNodeDetach(unittest.TestCase):
    def test_no_parent_sends_null_parent_id(self):
        """--no-parent must include parent_id=None in the body, not omit it."""
        with patch('binctl_client.api.nodes.patch_node_update.sync_detailed') as mock_sync:
            mock_sync.return_value = _mock_response()
            import binctl_cli.cli as bc

            with patch.object(bc, 'cli', _make_cli(_make_cli_args(node_id='1', no_parent=True))):
                bc._node_update()

            _, kwargs = mock_sync.call_args
            body = kwargs['body']
            assert hasattr(body, 'parent_id'), 'body missing parent_id attribute'
            assert body.parent_id is None, f'Expected parent_id=None, got {body.parent_id!r}'


if __name__ == '__main__':
    unittest.main()
