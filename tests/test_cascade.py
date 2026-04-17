"""
Tests for FK cascade behavior via raw SQL DELETE.
No DELETE API endpoints exist, so these tests issue raw SQL deletes
and verify the expected cascade effects via the HTTP API and direct DB queries.
"""

from sqlalchemy import text

from db import base62


class TestNodeDeleteCascade:
    def test_delete_node_orphans_children(self, client, engine, make_node, authed_headers):
        parent_id = make_node('parent', is_container=True)
        child_id = make_node('child', parent_id=parent_id)

        # Delete parent via raw SQL
        with engine.connect() as conn:
            conn.execute(text('DELETE FROM nodes WHERE id = :id'), {'id': base62.decode(parent_id)})
            conn.commit()

        # Child node still exists but has no parent
        resp = client.get(f'/v1/nodes/{child_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] is None

    def test_delete_node_cascades_edge_row(self, client, engine, make_node):
        parent_id = make_node('parent', is_container=True)
        child_id = make_node('child', parent_id=parent_id)

        with engine.connect() as conn:
            conn.execute(text('DELETE FROM nodes WHERE id = :id'), {'id': base62.decode(parent_id)})
            conn.commit()

        # The edges row for this parent-child pair must be gone
        with engine.connect() as conn:
            row = conn.execute(
                text('SELECT 1 FROM edges WHERE child_id = :id'),
                {'id': base62.decode(child_id)},
            ).first()
        assert row is None

    def test_delete_node_cascades_tag_node(self, client, engine, make_node, make_tag):
        tag_id = make_tag('mytag')
        node_id = make_node('item', tag_ids=[tag_id])

        with engine.connect() as conn:
            conn.execute(text('DELETE FROM nodes WHERE id = :id'), {'id': base62.decode(node_id)})
            conn.commit()

        # tag_node row is gone but the tag itself survives
        with engine.connect() as conn:
            tn_row = conn.execute(
                text('SELECT 1 FROM tag_node WHERE node_id = :id'),
                {'id': base62.decode(node_id)},
            ).first()
            tag_row = conn.execute(
                text('SELECT 1 FROM tags WHERE id = :id'),
                {'id': base62.decode(tag_id)},
            ).first()
        assert tn_row is None
        assert tag_row is not None

    def test_delete_parent_preserves_grandchild_chain(self, client, engine, make_node, authed_headers):
        a_id = make_node('A', is_container=True)
        b_id = make_node('B', is_container=True, parent_id=a_id)
        c_id = make_node('C', parent_id=b_id)

        # Delete top-level A
        with engine.connect() as conn:
            conn.execute(text('DELETE FROM nodes WHERE id = :id'), {'id': base62.decode(a_id)})
            conn.commit()

        # B and C still exist; C's parent is still B
        resp = client.get(f'/v1/nodes/{c_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] == b_id

        # B is now a root (no parent)
        resp = client.get(f'/v1/nodes/{b_id}', headers=authed_headers)
        assert resp.status_code == 200
        assert resp.json()['parent_id'] is None


class TestTagDeleteCascade:
    def test_delete_tag_cascades_tag_node(self, client, engine, make_node, make_tag):
        tag_id = make_tag('ephemeral')
        node_id = make_node('item', tag_ids=[tag_id])

        with engine.connect() as conn:
            conn.execute(text('DELETE FROM tags WHERE id = :id'), {'id': base62.decode(tag_id)})
            conn.commit()

        # tag_node row is gone but the node survives
        with engine.connect() as conn:
            tn_row = conn.execute(
                text('SELECT 1 FROM tag_node WHERE tag_id = :id'),
                {'id': base62.decode(tag_id)},
            ).first()
            node_row = conn.execute(
                text('SELECT 1 FROM nodes WHERE id = :id'),
                {'id': base62.decode(node_id)},
            ).first()
        assert tn_row is None
        assert node_row is not None
