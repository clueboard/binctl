"""Tests for binctl CLI — verifies correct parameter names passed to generated client."""

import sys
import types
import unittest
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
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_cli(args):
    cli = MagicMock()
    cli.args = args
    cli.config.general.base_url = args.base_url
    return cli


class TestNodeCreate(unittest.TestCase):
    def test_body_kwarg_not_json_body(self):
        """post_node_create.sync must be called with body=, not json_body=."""
        with patch('binctl_client.api.nodes.post_node_create.sync') as mock_sync:
            mock_sync.return_value = MagicMock(**{'to_dict.return_value': {}})
            # Import here so patches are in place
            import binctl as bc

            cli = _make_cli(_make_cli_args(label='test', tag_id=[]))
            bc._node_create(cli)

            _, kwargs = mock_sync.call_args
            self.assertIn('body', kwargs, "Expected 'body' kwarg")
            self.assertNotIn('json_body', kwargs, "Found unexpected 'json_body' kwarg")


class TestNodeUpdate(unittest.TestCase):
    def test_body_kwarg_not_json_body(self):
        with patch('binctl_client.api.nodes.patch_node_update.sync') as mock_sync:
            mock_sync.return_value = MagicMock(**{'to_dict.return_value': {}})
            import binctl as bc

            cli = _make_cli(_make_cli_args(label='updated', node_id=1))
            bc._node_update(cli, node_id=1)

            _, kwargs = mock_sync.call_args
            self.assertIn('body', kwargs)
            self.assertNotIn('json_body', kwargs)


class TestTagCreate(unittest.TestCase):
    def test_body_kwarg_not_json_body(self):
        with patch('binctl_client.api.tags.post_tag_create.sync') as mock_sync:
            mock_sync.return_value = MagicMock(**{'to_dict.return_value': {}})
            import binctl as bc

            cli = _make_cli(_make_cli_args(name='mytag'))
            bc._tag_create(cli)

            _, kwargs = mock_sync.call_args
            self.assertIn('body', kwargs)
            self.assertNotIn('json_body', kwargs)


class TestTagUpdate(unittest.TestCase):
    def test_body_kwarg_not_json_body(self):
        with patch('binctl_client.api.tags.patch_tag_update.sync') as mock_sync:
            mock_sync.return_value = MagicMock(**{'to_dict.return_value': {}})
            import binctl as bc

            cli = _make_cli(_make_cli_args(name='renamed'))
            bc._tag_update(cli, tag_id=1)

            _, kwargs = mock_sync.call_args
            self.assertIn('body', kwargs)
            self.assertNotIn('json_body', kwargs)


class TestNodeDetach(unittest.TestCase):
    def test_no_parent_sends_null_parent_id(self):
        """--no-parent must include parent_id=None in the body, not omit it."""
        with patch('binctl_client.api.nodes.patch_node_update.sync') as mock_sync:
            mock_sync.return_value = MagicMock(**{'to_dict.return_value': {}})
            import binctl as bc

            cli = _make_cli(_make_cli_args(node_id=1, no_parent=True))
            bc._node_update(cli, node_id=1)

            _, kwargs = mock_sync.call_args
            body = kwargs['body']
            assert hasattr(body, 'parent_id'), 'body missing parent_id attribute'
            assert body.parent_id is None, f'Expected parent_id=None, got {body.parent_id!r}'


if __name__ == '__main__':
    unittest.main()
