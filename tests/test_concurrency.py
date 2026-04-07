"""
Tests for correctness under multiple sequential clients.
SQLite has write-level locking, so truly parallel writes would deadlock.
Instead these tests use two separate test_client() instances in sequence
to verify last-write-wins semantics and idempotency.
"""

from __future__ import annotations


class TestMultiClientWrites:
    def test_sequential_writes_no_corruption(self, app, auth_token, clean_db):
        headers = {'Authorization': f'Bearer {auth_token}'}
        client1 = app.test_client()
        client2 = app.test_client()

        # Both clients create the same node
        resp = client1.post('/v1/nodes', json={'label': 'original'}, headers=headers)
        assert resp.status_code == 201
        node_id = resp.json()['id']

        # client1 updates first
        r1 = client1.patch(f'/v1/nodes/{node_id}', json={'label': 'from_client1'}, headers=headers)
        assert r1.status_code == 200

        # client2 updates after
        r2 = client2.patch(f'/v1/nodes/{node_id}', json={'label': 'from_client2'}, headers=headers)
        assert r2.status_code == 200

        # Final state is last write wins
        final = client1.get(f'/v1/nodes/{node_id}', headers=headers).json()
        assert final['label'] == 'from_client2'

    def test_patch_idempotency(self, app, auth_token, clean_db):
        headers = {'Authorization': f'Bearer {auth_token}'}
        client1 = app.test_client()
        resp = client1.post('/v1/nodes', json={'label': 'node'}, headers=headers)
        node_id = resp.json()['id']

        r1 = client1.patch(f'/v1/nodes/{node_id}', json={'label': 'stable'}, headers=headers)
        r2 = client1.patch(f'/v1/nodes/{node_id}', json={'label': 'stable'}, headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()['label'] == r2.json()['label'] == 'stable'

    def test_create_idempotency_tags(self, app, auth_token, clean_db):
        """Applying the same tag set twice yields the same result."""
        headers = {'Authorization': f'Bearer {auth_token}'}
        client1 = app.test_client()

        tag_resp = client1.post('/v1/tags', json={'name': 'durable'}, headers=headers)
        tag_id = tag_resp.json()['id']

        node_resp = client1.post('/v1/nodes', json={'label': 'item'}, headers=headers)
        node_id = node_resp.json()['id']

        r1 = client1.patch(f'/v1/nodes/{node_id}', json={'tag_ids': [tag_id]}, headers=headers)
        r2 = client1.patch(f'/v1/nodes/{node_id}', json={'tag_ids': [tag_id]}, headers=headers)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()['tags'] == r2.json()['tags']
