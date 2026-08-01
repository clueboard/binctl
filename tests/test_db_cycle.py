"""
Tests for cycle detection in ensure_parent_is_valid.

Calls db.flask functions directly inside a Flask app context.
"""

import pytest

from binctl_server.db.flask import create_node, ensure_parent_is_valid, set_parent


class TestNoCycle:
    def test_root_assignment(self, app, clean_db):
        with app.app.app_context():
            a = create_node('A', None, True)
            ensure_parent_is_valid(a, child_id=None)

    def test_chain_extension(self, app, clean_db):
        with app.app.app_context():
            a = create_node('A', None, True)
            b = create_node('B', None, True)
            c = create_node('C', None, True)
            set_parent(b, a)  # A → B
            # Adding C as a child of A is not a cycle
            ensure_parent_is_valid(a, child_id=c)

    def test_sibling_no_false_positive(self, app, clean_db):
        with app.app.app_context():
            a = create_node('A', None, True)
            b = create_node('B', None, True)
            c = create_node('C', None, True)
            set_parent(b, a)
            set_parent(c, a)
            # B and C are siblings; making C a child of B is valid
            ensure_parent_is_valid(b, child_id=c)


class TestCycleDetection:
    def test_direct_cycle(self, app, clean_db):
        with app.app.app_context():
            a = create_node('A', None, True)
            b = create_node('B', None, True)
            set_parent(b, a)  # A → B
            # Trying to make A a child of B would create A→B→A
            with pytest.raises(ValueError, match='cycle'):
                ensure_parent_is_valid(b, child_id=a)

    def test_indirect_cycle(self, app, clean_db):
        with app.app.app_context():
            a = create_node('A', None, True)
            b = create_node('B', None, True)
            c = create_node('C', None, True)
            set_parent(b, a)  # A → B → C
            set_parent(c, b)
            # Making A a child of C would create A→B→C→A
            with pytest.raises(ValueError, match='cycle'):
                ensure_parent_is_valid(c, child_id=a)

    def test_deep_chain_cycle(self, app, clean_db):
        with app.app.app_context():
            ids = [create_node(f'N{i}', None, True) for i in range(5)]
            for i in range(4):
                set_parent(ids[i + 1], ids[i])
            # Making N0 a child of N4 would create a 5-node cycle
            with pytest.raises(ValueError, match='cycle'):
                ensure_parent_is_valid(ids[4], child_id=ids[0])


class TestExistingChecksRegression:
    def test_self_loop(self, app, clean_db):
        with app.app.app_context():
            a = create_node('A', None, True)
            with pytest.raises(ValueError, match='cannot equal'):
                ensure_parent_is_valid(a, child_id=a)

    def test_non_container(self, app, clean_db):
        with app.app.app_context():
            a = create_node('A', None, False)
            b = create_node('B', None, True)
            with pytest.raises(ValueError, match='container'):
                ensure_parent_is_valid(a, child_id=b)

    def test_nonexistent_parent(self, app, clean_db):
        with app.app.app_context():
            with pytest.raises(ValueError, match='does not exist'):
                ensure_parent_is_valid(99999, child_id=1)
