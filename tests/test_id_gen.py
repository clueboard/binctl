from __future__ import annotations

import time

from db.id_gen import new_id


def test_returns_positive_int():
    assert isinstance(new_id(), int)
    assert new_id() > 0


def test_fits_in_signed_bigint():
    max_signed_bigint = (1 << 63) - 1
    for _ in range(10):
        assert new_id() <= max_signed_bigint


def test_encodes_current_time():
    before = int(time.time() * 1_000_000) << 12
    result = new_id()
    after = (int(time.time() * 1_000_000) + 1) << 12
    assert before <= result <= after


def test_repeated_calls_are_unique():
    ids = [new_id() for _ in range(1000)]
    assert len(set(ids)) == len(ids)


def test_calls_separated_in_time_are_ordered():
    # IDs from calls that are at least 1 microsecond apart are guaranteed ordered.
    # Within the same microsecond the 12 random bits may produce any order — that
    # is acceptable because real API requests are always milliseconds apart.
    a = new_id()
    time.sleep(0.001)  # 1 ms >> 1 µs
    b = new_id()
    assert a < b
