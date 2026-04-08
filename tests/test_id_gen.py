from __future__ import annotations

import datetime
import time
import warnings
from unittest.mock import patch

import pytest

from db.id_gen import EPOCH_US, new_id


def test_returns_positive_int():
    assert isinstance(new_id(), int)
    assert new_id() > 0


def test_fits_in_signed_bigint():
    max_signed_bigint = (1 << 63) - 1
    for _ in range(10):
        assert new_id() <= max_signed_bigint


def test_encodes_current_time():
    before = (int(time.time() * 1_000_000) - EPOCH_US) << 12
    result = new_id()
    after = (int(time.time() * 1_000_000) - EPOCH_US + 1) << 12
    assert before <= result <= after


def test_no_signed_overflow_before_2091():
    # Without a custom epoch the µs-since-1970 timestamp exceeds 2^51 on
    # 2041-05-10, making ts << 12 overflow signed 64-bit (SQLite's limit).
    # With a 2020-03-11 epoch the overflow doesn't occur until 2091-07-19.
    year_2090 = datetime.datetime(2090, 1, 1, tzinfo=datetime.timezone.utc)
    ts = int(year_2090.timestamp() * 1_000_000) - EPOCH_US
    max_id = (ts << 12) | 0xFFF  # all 12 random bits set
    assert max_id <= (1 << 63) - 1


def test_no_warning_before_2085():
    import importlib
    import db.id_gen as id_gen_mod

    with patch('time.time', return_value=3_629_145_599.999):  # one second before 2085
        with warnings.catch_warnings():
            warnings.simplefilter('error')
            importlib.reload(id_gen_mod)  # must not raise


def test_warning_emitted_from_2085():
    import importlib
    import db.id_gen as id_gen_mod

    with patch('time.time', return_value=3_629_145_600.0):  # 2085-01-01 00:00:00 UTC
        with pytest.warns(UserWarning, match='2091'):
            importlib.reload(id_gen_mod)


def test_calls_separated_in_time_are_ordered():
    # IDs from calls that are at least 1 microsecond apart are guaranteed ordered.
    # Within the same microsecond the 12 random bits may produce any order — that
    # is acceptable because real API requests are always milliseconds apart.
    a = new_id()
    time.sleep(0.001)  # 1 ms >> 1 µs
    b = new_id()
    assert a < b
