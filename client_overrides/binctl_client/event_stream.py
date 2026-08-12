"""Synchronous and asynchronous consumers for binctl's SSE event stream."""

import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias, cast

import httpx

from .client import Client

InventoryEventType: TypeAlias = Literal[
    'node.created',
    'node.updated',
    'node.deleted',
    'tag.created',
    'tag.updated',
    'tag.deleted',
]


@dataclass(frozen=True)
class InventoryEvent:
    id: int
    event: InventoryEventType
    data: dict[str, Any]


@dataclass(frozen=True)
class ResetRequired:
    reason: str
    current_cursor: int


StreamEvent: TypeAlias = InventoryEvent | ResetRequired


def _decode_event(lines: list[str]) -> StreamEvent | None:
    event_type = 'message'
    event_id: str | None = None
    data_lines: list[str] = []
    for line in lines:
        if not line or line.startswith(':'):
            continue
        field, separator, value = line.partition(':')
        if separator and value.startswith(' '):
            value = value[1:]
        if field == 'event':
            event_type = value
        elif field == 'id':
            event_id = value
        elif field == 'data':
            data_lines.append(value)
    if not data_lines:
        return None
    payload = json.loads('\n'.join(data_lines))
    if not isinstance(payload, dict):
        raise ValueError('SSE event data must be a JSON object')
    if event_type == 'reset-required':
        return ResetRequired(reason=str(payload['reason']), current_cursor=int(payload['current_cursor']))
    if event_type not in {'node.created', 'node.updated', 'node.deleted', 'tag.created', 'tag.updated', 'tag.deleted'}:
        raise ValueError(f'Unsupported inventory event type: {event_type!r}')
    if event_id is None:
        raise ValueError(f'{event_type} event is missing an id')
    return InventoryEvent(id=int(event_id), event=cast(InventoryEventType, event_type), data=payload)


def _events_from_lines(lines: Iterator[str]) -> Iterator[StreamEvent]:
    pending: list[str] = []
    for line in lines:
        if line == '':
            event = _decode_event(pending)
            pending = []
            if event is not None:
                yield event
        else:
            pending.append(line)
    if pending:
        event = _decode_event(pending)
        if event is not None:
            yield event


def stream_events(client: Client, cursor: int) -> Iterator[StreamEvent]:
    """Replay events after *cursor*, then yield live events until disconnected."""
    if cursor < 0:
        raise ValueError('cursor must be non-negative')
    with client.get_httpx_client().stream('GET', '/v1/events', headers={'Last-Event-ID': str(cursor), 'Accept': 'text/event-stream'}, timeout=None) as response:
        response.raise_for_status()
        yield from _events_from_lines(response.iter_lines())


async def astream_events(client: Client, cursor: int) -> AsyncIterator[StreamEvent]:
    """Asynchronously replay events after *cursor*, then yield live events."""
    if cursor < 0:
        raise ValueError('cursor must be non-negative')
    async with client.get_async_httpx_client().stream(
        'GET', '/v1/events', headers={'Last-Event-ID': str(cursor), 'Accept': 'text/event-stream'}, timeout=None
    ) as response:
        response.raise_for_status()
        pending: list[str] = []
        async for line in response.aiter_lines():
            if line == '':
                event = _decode_event(pending)
                pending = []
                if event is not None:
                    yield event
            else:
                pending.append(line)
        if pending:
            event = _decode_event(pending)
            if event is not None:
                yield event
