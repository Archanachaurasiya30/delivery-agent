"""Pure tests for groq_chat transient-failure retries (issue #19).

Same philosophy as test_demo_mode: no network, no DB — httpx.MockTransport
counts calls and decides what each attempt receives; asyncio.sleep is
captured so nothing actually waits.
"""

import asyncio

import httpx
import pytest

from app.config import settings
from app.services import groq_client
from app.services.groq_client import GroqError, groq_chat


def ok() -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": "pong"}, "finish_reason": "stop"}]}
    )


def rate_limited(retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return httpx.Response(429, headers=headers, json={"error": {"message": "slow down"}})


class FakeGroq:
    """MockTransport handler serving queued outcomes, one per call."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, request):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def mount(monkeypatch, handler) -> list[float]:
    """Point groq_chat at the fake transport; return the captured sleep delays."""
    sleeps: list[float] = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    real_client = httpx.AsyncClient

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(settings, "demo_mode", False)
    monkeypatch.setattr(settings, "groq_api_key", "test-key")
    monkeypatch.setattr(groq_client.httpx, "AsyncClient", factory)
    monkeypatch.setattr(groq_client.asyncio, "sleep", fake_sleep)
    return sleeps


def test_429_then_200_succeeds_on_second_attempt(monkeypatch):
    handler = FakeGroq(rate_limited(), ok())
    sleeps = mount(monkeypatch, handler)
    assert asyncio.run(groq_chat([{"role": "user", "content": "hi"}])) == "pong"
    assert handler.calls == 2
    assert len(sleeps) == 1 and 0 < sleeps[0] <= 5  # 0.5s base ±25% jitter


def test_429_three_times_raises_after_three_attempts(monkeypatch):
    handler = FakeGroq(rate_limited(), rate_limited(), rate_limited())
    sleeps = mount(monkeypatch, handler)
    with pytest.raises(GroqError, match="slow down"):
        asyncio.run(groq_chat([{"role": "user", "content": "hi"}]))
    assert handler.calls == 3
    assert len(sleeps) == 2  # two backoffs, not one per failure


def test_400_fails_fast_without_retry(monkeypatch):
    handler = FakeGroq(httpx.Response(400, json={"error": {"message": "bad request"}}))
    sleeps = mount(monkeypatch, handler)
    with pytest.raises(GroqError, match="bad request"):
        asyncio.run(groq_chat([{"role": "user", "content": "hi"}]))
    assert handler.calls == 1
    assert sleeps == []


def test_connect_error_then_200_retries_transport_failure(monkeypatch):
    handler = FakeGroq(httpx.ConnectError("connection reset"), ok())
    sleeps = mount(monkeypatch, handler)
    assert asyncio.run(groq_chat([{"role": "user", "content": "hi"}])) == "pong"
    assert handler.calls == 2
    assert len(sleeps) == 1


def test_retry_after_header_honored_capped_at_5s(monkeypatch):
    handler = FakeGroq(rate_limited(retry_after="9"), ok())
    sleeps = mount(monkeypatch, handler)
    assert asyncio.run(groq_chat([{"role": "user", "content": "hi"}])) == "pong"
    assert handler.calls == 2
    assert sleeps == [5.0]
