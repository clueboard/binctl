from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import create_engine

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise RuntimeError('DATABASE_URL environment variable is not set')

engine = create_engine(DATABASE_URL, future=True)


def _as_utc(dt: datetime | str | None) -> datetime | None:
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
