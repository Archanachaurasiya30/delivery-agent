"""Thin async Webex Messaging API client (httpx).

Sibling of ``telegram_client.py`` — same shape, different transport. Used by the
Celery tasks that DM standup questions, push the morning brief, and send
autopilot nudges.

Webex addresses people by email (``toPersonEmail``), so no per-member linking
flow is needed: ``TeamMember.email`` is the durable DM target. Bot tokens do not
expire, so the token is a plain setting like the Telegram one.
"""

from typing import Any

import httpx

from app.config import settings

# The ADO sync synthesizes this domain for people it has no email for.
SYNTHETIC_EMAIL_DOMAIN = "@delivery.local"


def is_reachable(email: str | None) -> bool:
    """A real address a message could be delivered to (ignores test mode)."""
    return bool(email) and not email.endswith(SYNTHETIC_EMAIL_DOMAIN)


def can_deliver(email: str | None) -> bool:
    """Worth sending to: test mode delivers everything (to the tester)."""
    if settings.webex_redirect_to:
        return True
    return settings.webex_live and is_reachable(email)


class WebexError(Exception):
    """Non-2xx response from the Webex API."""

    def __init__(self, status_code: int, body: str) -> None:
        super().__init__(f"Webex API error {status_code}: {body[:500]}")
        self.status_code = status_code
        self.body = body


class WebexRecipientError(WebexError):
    """The recipient does not exist / is not reachable on Webex.

    Split out from ``WebexError`` because it is *permanent*: the send tasks use
    ``autoretry_for=(Exception,)`` and must not spend retries on a member who
    simply has no Webex account.
    """


class WebexClient:
    """Minimal async wrapper over the Webex Messaging API."""

    def __init__(
        self,
        token: str,
        base_url: str = "https://webexapis.com/v1",
        timeout: float = 30.0,
        redirect_to: str | None = None,
    ) -> None:
        self._token = token
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        # Test mode — see settings.webex_redirect_to. Enforced here so no
        # caller can reach a real person by accident.
        self._redirect = (redirect_to if redirect_to is not None else settings.webex_redirect_to).strip()

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        # Last line of defence: only the tester, unless explicitly live.
        if self._redirect:
            if payload.get("toPersonEmail") != self._redirect:
                raise WebexRecipientError(403, "blocked: test mode only sends to WEBEX_REDIRECT_TO")
        elif not settings.webex_live:
            raise WebexRecipientError(
                403, "blocked: Webex is not live (set WEBEX_REDIRECT_TO or WEBEX_LIVE=true)"
            )
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base}/{path}", json=payload, headers=self._headers
            )
        if resp.status_code >= 400:
            # Webex answers an unknown/unreachable person with 400 (and 404 for a
            # missing room). Both are permanent for this recipient.
            if resp.status_code in (400, 404):
                raise WebexRecipientError(resp.status_code, resp.text)
            raise WebexError(resp.status_code, resp.text)
        return resp.json()

    async def send_to_email(self, email: str, markdown: str) -> dict[str, Any]:
        """DM a person by email. Creates the 1:1 space on first send."""
        if self._redirect and email != self._redirect:
            markdown = f"🧪 _Test mode — meant for **{email}**_\n\n{markdown}"
            email = self._redirect
        return await self._post("messages", {"toPersonEmail": email, "markdown": markdown})

    async def send_to_room(self, room_id: str, markdown: str) -> dict[str, Any]:
        """Post to a space."""
        if self._redirect:
            return await self.send_to_email(
                self._redirect, f"🧪 _Test mode — meant for space {room_id[:12]}…_\n\n{markdown}"
            )
        return await self._post("messages", {"roomId": room_id, "markdown": markdown})

    async def send(self, target: str, markdown: str) -> dict[str, Any]:
        """Send to an email or a room id.

        Room ids are base64-ish and never contain "@", so the discriminator is
        unambiguous. Lets a single config value hold a mix of both.
        """
        if "@" in target:
            return await self.send_to_email(target, markdown)
        return await self.send_to_room(target, markdown)
