import queue

from agentloom.graph.event_bus import register_queue, unregister_queue, emit_event


def test_emit_event_to_registered_queue():
    q = queue.Queue()
    register_queue("test-1", q)
    emit_event("test-1", {"type": "test", "content": "hello"})
    item = q.get_nowait()
    assert item["type"] == "test"
    assert item["content"] == "hello"
    unregister_queue("test-1")


def test_emit_event_to_unregistered_does_nothing():
    emit_event("nonexistent", {"type": "test"})  # should not raise


def test_unregister_cleans_up():
    q = queue.Queue()
    register_queue("test-2", q)
    unregister_queue("test-2")
    emit_event("test-2", {"type": "test"})
    assert q.empty()
