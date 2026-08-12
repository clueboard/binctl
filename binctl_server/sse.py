"""Server-Sent Events protocol serialization."""

import json


def sse_event(event_id: int | None, event_type: str, data: dict) -> bytes:
    lines = []
    if event_id is not None:
        lines.append(f'id: {event_id}')
    lines.append(f'event: {event_type}')
    payload = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    lines.extend(f'data: {line}' for line in payload.splitlines() or [''])
    return ('\n'.join(lines) + '\n\n').encode()
