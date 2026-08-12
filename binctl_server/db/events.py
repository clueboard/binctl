"""Durable inventory event persistence."""

import json
import os
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping

DEFAULT_RETENTION_LIMIT = 10_000


def retention_limit() -> int:
    raw = os.environ.get('EVENT_RETENTION_LIMIT', str(DEFAULT_RETENTION_LIMIT))
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f'EVENT_RETENTION_LIMIT must be an integer (got {raw!r})')
    if value < 1:
        raise ValueError(f'EVENT_RETENTION_LIMIT must be positive (got {raw!r})')
    return value


def append_event(conn: Connection, event_type: str, data: dict) -> int:
    """Append an event using the caller's transaction and prune old history."""
    conn.execute(text('UPDATE event_sequence SET value = value + 1 WHERE id = 1'))
    event_id = int(conn.execute(text('SELECT value FROM event_sequence WHERE id = 1')).scalar_one())
    payload = {'occurred_at': datetime.now(timezone.utc).isoformat(), **data}
    conn.execute(
        text('INSERT INTO inventory_events (id, event_type, data) VALUES (:id, :event_type, :data)'),
        {'id': event_id, 'event_type': event_type, 'data': json.dumps(payload, separators=(',', ':'), ensure_ascii=False)},
    )
    cutoff = event_id - retention_limit()
    if cutoff > 0:
        conn.execute(text('DELETE FROM inventory_events WHERE id <= :cutoff'), {'cutoff': cutoff})
    return event_id


def current_cursor(conn: Connection) -> int:
    return int(conn.execute(text('SELECT value FROM event_sequence WHERE id = 1')).scalar_one())


def event_bounds(conn: Connection) -> tuple[int | None, int]:
    row = conn.execute(text('SELECT MIN(id) AS minimum, MAX(id) AS maximum FROM inventory_events')).mappings().one()
    return (int(row['minimum']) if row['minimum'] is not None else None, current_cursor(conn))


def fetch_events_after(conn: Connection, cursor: int, limit: int = 100) -> Sequence[RowMapping]:
    return (
        conn.execute(
            text('SELECT id, event_type, data, created_at FROM inventory_events WHERE id > :cursor ORDER BY id LIMIT :limit'),
            {'cursor': cursor, 'limit': limit},
        )
        .mappings()
        .all()
    )
