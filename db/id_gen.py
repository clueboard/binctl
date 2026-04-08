import secrets
import time
import warnings

# 2085-01-01 00:00:00 UTC as a Unix timestamp (seconds)
_WARN_AFTER_UNIX_TS: int = 3_629_145_600

# Custom epoch: 2020-03-11 00:00:00 UTC (in microseconds).
# Subtracting this from the wall-clock timestamp keeps the upper 51 bits small
# enough that (ts << 12) fits in a signed 64-bit integer until 2091.
EPOCH_US: int = 1_583_884_800_000_000


if time.time() >= _WARN_AFTER_UNIX_TS:
    warnings.warn(
        'new_id() will overflow signed 64-bit integers on 2091-07-19. '
        'Update EPOCH_US in db/id_gen.py before that date.',
        UserWarning,
        stacklevel=2,
    )


def new_id() -> int:
    """Return a time-ordered 63-bit integer ID.

    Bits 63–12: microseconds since EPOCH_US (~47 bits at time of writing).
    Bits 11–0:  12 random bits to avoid collisions within the same microsecond.
    """
    ts = int(time.time() * 1_000_000) - EPOCH_US  # ~47 bits at time of writing
    return (ts << 12) | secrets.randbits(12)
