import asyncio

from binctl_server.db.events import append_event
from binctl_server.event_stream import EventStreamMiddleware


def test_event_stream_requires_authentication(client):
    response = client.get('/v1/events', headers={'Last-Event-ID': '0'})
    assert response.status_code == 401


def test_event_stream_requires_cursor(client, authed_headers):
    response = client.get('/v1/events', headers=authed_headers)
    assert response.status_code == 400


def test_event_stream_rejects_future_cursor(client, authed_headers):
    response = client.get('/v1/events', headers={**authed_headers, 'Last-Event-ID': '1'})
    assert response.status_code == 400


def _invoke_stream(cursor: int):
    sent = []

    async def app(scope, receive, send):  # pragma: no cover - stream path must intercept
        raise AssertionError('stream was not intercepted')

    async def receive():
        return {'type': 'http.disconnect'}

    async def send(message):
        sent.append(message)

    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/v1/events',
        'headers': [(b'last-event-id', str(cursor).encode())],
    }
    asyncio.run(EventStreamMiddleware(app)(scope, receive, send))
    return sent


def test_event_stream_replays_then_observes_disconnect(engine, clean_db):
    with engine.begin() as conn:
        append_event(conn, 'tag.created', {'resource': {'name': 'tool'}})
    sent = _invoke_stream(0)
    assert sent[0]['status'] == 200
    assert b'id: 1\nevent: tag.created\n' in sent[1]['body']
    assert sent[1]['more_body'] is True


def test_event_stream_sends_reset_and_closes_for_expired_cursor(engine, clean_db, monkeypatch):
    monkeypatch.setenv('EVENT_RETENTION_LIMIT', '1')
    with engine.begin() as conn:
        append_event(conn, 'tag.created', {'n': 1})
        append_event(conn, 'tag.created', {'n': 2})
    sent = _invoke_stream(0)
    assert b'event: reset-required' in sent[1]['body']
    assert sent[1]['more_body'] is False
