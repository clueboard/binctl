from __future__ import annotations

import secrets
import time


def new_id() -> int:
    ts = int(time.time() * 1_000_000)  # ~51 bits at current epoch
    return (ts << 12) | secrets.randbits(12)
