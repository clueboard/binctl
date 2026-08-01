from binctl_server.db.flask import db_bool


def test_boolean_values_are_stored_as_integer_flags():
    # PostgreSQL does not implicitly coerce bound booleans to the INTEGER type
    # used by the schema shared with SQLite and MySQL.
    assert db_bool(True) == 1
    assert type(db_bool(True)) is int
    assert db_bool(False) == 0
    assert type(db_bool(False)) is int
    assert db_bool(1) == 1
    assert db_bool(0) == 0
