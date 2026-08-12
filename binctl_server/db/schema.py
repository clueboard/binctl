"""Database schema installation."""

from importlib.resources import files

from sqlalchemy import text

from .engine import engine


def initialize_schema() -> None:
    sql = files('binctl_server.db').joinpath('v1.sql').read_text()
    with engine.connect() as conn:
        for statement in sql.split(';'):
            statement = statement.strip()
            if statement:
                conn.execute(text(statement))
        conn.commit()
