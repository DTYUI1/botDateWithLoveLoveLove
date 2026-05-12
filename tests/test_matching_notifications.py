from uuid import uuid4

import pytest

from api.v1 import matching


@pytest.mark.asyncio
async def test_swipe_event_publisher_does_not_duplicate_match_event(monkeypatch):
    """Match push is published by Celery notification task, not by swipe hot-path."""
    calls = []

    class FakePublisher:
        async def publish_swipe_event(self, **kwargs):
            calls.append(("publish_swipe_event", kwargs))

        async def publish_match_event(self, **kwargs):
            calls.append(("publish_match_event", kwargs))

    async def fake_safe_publish(coro_factory, *, op):
        calls.append(("safe_publish", op))
        await coro_factory(FakePublisher())
        return True

    monkeypatch.setattr(matching, "safe_publish", fake_safe_publish)

    await matching._publish_swipe_events(
        swiper_id=uuid4(),
        swiped_id=uuid4(),
        action="like",
        result={
            "is_match": True,
            "match_id": uuid4(),
            "swipe_id": uuid4(),
        },
    )

    assert [call[0] for call in calls] == ["safe_publish", "publish_swipe_event"]
    assert calls[0] == ("safe_publish", "swipe_event")
