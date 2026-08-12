import importlib.util
from pathlib import Path


def _module():
    path = Path(__file__).parent.parent / 'client_overrides' / 'binctl_client' / 'event_stream.py'
    source = path.read_text().replace('from .client import Client', 'Client = object')
    spec = importlib.util.spec_from_loader('event_stream_under_test', loader=None)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    exec(compile(source, path, 'exec'), module.__dict__)
    return module


def test_decode_inventory_event():
    module = _module()
    event = module._decode_event(['id: 12', 'event: node.updated', 'data: {"resource":', 'data: {"id":"abc"}}'])
    assert event.id == 12
    assert event.event == 'node.updated'
    assert event.data == {'resource': {'id': 'abc'}}


def test_decode_reset_required_without_id():
    module = _module()
    event = module._decode_event(['event: reset-required', 'data: {"reason":"event-history-expired","current_cursor":20}'])
    assert event.reason == 'event-history-expired'
    assert event.current_cursor == 20


def test_comments_and_fragmented_event_groups():
    module = _module()
    events = list(module._events_from_lines(iter([': heartbeat', '', 'id: 1', 'event: tag.created', 'data: {"resource":{"name":"tool"}}', ''])))
    assert len(events) == 1
    assert events[0].id == 1
