import pytest

from app.workers import queue


@pytest.fixture(autouse=True)
def _inline(monkeypatch):
    monkeypatch.setenv("ARQ_INLINE", "true")
    from app.config import get_settings
    get_settings.cache_clear()


async def test_enqueue_inline_runs_sync():
    """In inline mode, enqueue() should call the registered task immediately."""
    called = []

    async def fake(ctx, *, msg):
        called.append(msg)

    queue.register("__test_fake", fake)
    result = await queue.enqueue("__test_fake", msg="hello")
    assert result == "inline"
    assert called == ["hello"]


async def test_enqueue_unknown_task_raises():
    with pytest.raises(RuntimeError, match="not registered"):
        await queue.enqueue("__nope__")
