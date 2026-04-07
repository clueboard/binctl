from __future__ import annotations

from datetime import datetime, timezone

from db import _as_utc


class TestAsUtc:
    def test_none_returns_none(self):
        assert _as_utc(None) is None

    def test_naive_datetime_stamped_as_utc(self):
        naive = datetime(2024, 1, 1, 12, 0, 0)
        result = _as_utc(naive)
        assert result is not None
        assert result == datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert result.tzinfo is timezone.utc

    def test_aware_datetime_returned_unchanged(self):
        aware = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _as_utc(aware) is aware

    def test_string_parsed_and_stamped_as_utc(self):
        result = _as_utc('2000-01-01 00:00:00')
        assert result == datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
