"""Thin async Telegram Bot API client (httpx).

Used by both the long-poll bot process and Celery tasks that send DMs.
"""

from typing import Any

import httpx


class TelegramClient:
    """Minimal async wrapper over the Telegram Bot API."""

    def __init__(
        self,
        token: str,
        base_url: str = "https://api.telegram.org",
        timeout: float = 35.0,
    ) -> None:
        self._token = token
        self._base = f"{base_url}/bot{token}"
        self._timeout = timeout

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._base}/{method}", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_updates(
        self, offset: int | None = None, timeout: int = 30
    ) -> list[dict[str, Any]]:
        """Long-poll for updates. `timeout` is the server-side long-poll wait."""
        payload: dict[str, Any] = {"timeout": timeout}
        if offset is not None:
            payload["offset"] = offset
        # Client timeout must exceed the long-poll timeout.
        async with httpx.AsyncClient(timeout=timeout + 10) as client:
            resp = await client.post(f"{self._base}/getUpdates", json=payload)
            resp.raise_for_status()
            return resp.json().get("result", [])

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return await self._post("sendMessage", payload)

    async def answer_callback_query(self, callback_query_id: str) -> dict[str, Any]:
        return await self._post(
            "answerCallbackQuery", {"callback_query_id": callback_query_id}
        )
