"""ASGI implementation of the authenticated inventory SSE endpoint."""

import asyncio
import json

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from .db.engine import engine
from .db.events import event_bounds, fetch_events_after
from .sse import sse_event

_POLL_SECONDS = 1.0
_HEARTBEAT_SECONDS = 15.0


class EventStreamMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or scope.get('method') != 'GET' or scope.get('path') != '/v1/events':
            await self.app(scope, receive, send)
            return

        raw_cursor = Headers(scope=scope).get('last-event-id')
        try:
            if raw_cursor is None:
                raise ValueError
            cursor = int(raw_cursor)
            if cursor < 0:
                raise ValueError
        except ValueError:
            await self._json_error(send, 400, 'Last-Event-ID must be a non-negative integer')
            return

        with engine.connect() as conn:
            minimum, maximum = event_bounds(conn)
        if cursor > maximum:
            await self._json_error(send, 400, 'Last-Event-ID is newer than the server cursor')
            return

        await send(
            {
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    (b'content-type', b'text/event-stream; charset=utf-8'),
                    (b'cache-control', b'no-cache'),
                    (b'x-accel-buffering', b'no'),
                ],
            }
        )

        if minimum is not None and cursor < minimum - 1:
            body = sse_event(None, 'reset-required', {'reason': 'event-history-expired', 'current_cursor': maximum})
            await send({'type': 'http.response.body', 'body': body, 'more_body': False})
            return

        last_heartbeat = asyncio.get_running_loop().time()
        while True:
            with engine.connect() as conn:
                minimum, maximum = event_bounds(conn)
                rows = fetch_events_after(conn, cursor)
            if minimum is not None and cursor < minimum - 1:
                body = sse_event(None, 'reset-required', {'reason': 'event-history-expired', 'current_cursor': maximum})
                await send({'type': 'http.response.body', 'body': body, 'more_body': False})
                return
            for row in rows:
                data = json.loads(row['data'])
                await send({'type': 'http.response.body', 'body': sse_event(row['id'], row['event_type'], data), 'more_body': True})
                cursor = int(row['id'])
            if rows:
                continue

            now = asyncio.get_running_loop().time()
            if now - last_heartbeat >= _HEARTBEAT_SECONDS:
                await send({'type': 'http.response.body', 'body': b': heartbeat\n\n', 'more_body': True})
                last_heartbeat = now

            try:
                message = await asyncio.wait_for(receive(), timeout=_POLL_SECONDS)
                if message['type'] == 'http.disconnect':
                    return
            except TimeoutError:
                pass

    @staticmethod
    async def _json_error(send: Send, status: int, message: str) -> None:
        body = json.dumps({'error': message}).encode()
        await send(
            {
                'type': 'http.response.start',
                'status': status,
                'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())],
            }
        )
        await send({'type': 'http.response.body', 'body': body, 'more_body': False})
