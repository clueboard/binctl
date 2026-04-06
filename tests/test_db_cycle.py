"""
Tests for cycle detection in ensure_parent_is_valid.

Calls the db function directly inside a Flask app context to avoid HTTP overhead.
Tree structures are set up via raw SQL against the shared SQLite engine.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from db import ensure_parent_is_valid


def _insert_node(conn, label, is_container=True):
    r = conn.execute(
        text('INSERT INTO nodes (label, is_container) VALUES (:l, :c)'),
        {'l': label, 'c': 1 if is_container else 0},
    )
    return r.lastrowid


def _insert_edge(conn, parent_id, child_id):
    conn.execute(
        text('INSERT INTO edges (parent_id, child_id) VALUES (:p, :c)'),
        {'p': parent_id, 'c': child_id},
    )


class TestNoCycle:
    def test_root_assignment(self, app, engine, clean_db):
        with engine.connect() as conn:
            a = _insert_node(conn, 'A')
            conn.commit()

        with app.app.app_context():
            # No error: A is a valid container
            ensure_parent_is_valid(a, child_id=None)

    def test_chain_extension(self, app, engine, clean_db):
        with engine.connect() as conn:
            a = _insert_node(conn, 'A')
            b = _insert_node(conn, 'B')
            _insert_edge(conn, a, b)
            conn.commit()

        with app.app.app_context():
            # Adding a new child to A is not a cycle
            ensure_parent_is_valid(a, child_id=b + 1000)

    def test_sibling_no_false_positive(self, app, engine, clean_db):
        with engine.connect() as conn:
            a = _insert_node(conn, 'A')
            b = _insert_node(conn, 'B')
            c = _insert_node(conn, 'C')
            _insert_edge(conn, a, b)
            _insert_edge(conn, a, c)
            conn.commit()

        with app.app.app_context():
            # B and C are siblings; making C a child of B is valid (B is a container)
            ensure_parent_is_valid(b, child_id=c)


class TestCycleDetection:
    def test_direct_cycle(self, app, engine, clean_db):
        with engine.connect() as conn:
            a = _insert_node(conn, 'A')
            b = _insert_node(conn, 'B')
            _insert_edge(conn, a, b)  # A → B
            conn.commit()

        with app.app.app_context():
            # Trying to make A a child of B would create A→B→A
            with pytest.raises(ValueError, match='cycle'):
                ensure_parent_is_valid(b, child_id=a)

    def test_indirect_cycle(self, app, engine, clean_db):
        with engine.connect() as conn:
            a = _insert_node(conn, 'A')
            b = _insert_node(conn, 'B')
            c = _insert_node(conn, 'C')
            _insert_edge(conn, a, b)  # A → B → C
            _insert_edge(conn, b, c)
            conn.commit()

        with app.app.app_context():
            # Making A a child of C would create A→B→C→A
            with pytest.raises(ValueError, match='cycle'):
                ensure_parent_is_valid(c, child_id=a)

    def test_deep_chain_cycle(self, app, engine, clean_db):
        with engine.connect() as conn:
            ids = [_insert_node(conn, f'N{i}') for i in range(5)]
            for i in range(4):
                _insert_edge(conn, ids[i], ids[i + 1])
            conn.commit()

        with app.app.app_context():
            # Making N0 a child of N4 would create a 5-node cycle
            with pytest.raises(ValueError, match='cycle'):
                ensure_parent_is_valid(ids[4], child_id=ids[0])


class TestExistingChecksRegression:
    def test_self_loop(self, app, engine, clean_db):
        with engine.connect() as conn:
            a = _insert_node(conn, 'A')
            conn.commit()

        with app.app.app_context():
            with pytest.raises(ValueError, match='cannot equal'):
                ensure_parent_is_valid(a, child_id=a)

    def test_non_container(self, app, engine, clean_db):
        with engine.connect() as conn:
            a = _insert_node(conn, 'A', is_container=False)
            b = _insert_node(conn, 'B')
            conn.commit()

        with app.app.app_context():
            with pytest.raises(ValueError, match='container'):
                ensure_parent_is_valid(a, child_id=b)

    def test_nonexistent_parent(self, app, engine, clean_db):
        with app.app.app_context():
            with pytest.raises(ValueError, match='does not exist'):
                ensure_parent_is_valid(99999, child_id=1)
