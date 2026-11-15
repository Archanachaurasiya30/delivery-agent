"""Shared raw-Groq HTTP client for the executive-layer features.

The raw httpx path to Groq is the one reliable LLM route with the current
keys (litellm has no Groq branch), so new features (morning brief, autopilot
triage, ask-the-DM) call Groq through here instead of copying the boilerplate
again. Mirrors the proven settings of ``standup_service._analyze_standup_json``
and the ``/agent/analyze`` endpoint: gpt-oss ``reasoning_effort``, 60s timeout,
and empty-content handling (a reasoning model can exhaust ``max_tokens`` on
reasoning and return empty content with finish_reason="length" — surfaced as a
:class:`GroqError`, never a silent empty string). Existing call sites are
intentionally untouched.
"""

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqError(RuntimeError):
    """Raised when Groq is unconfigured, unreachable, or returns no usable content."""


def extract_json(text: str) -> dict:
    """Extract the first balanced JSON object from an LLM response."""
    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object in response")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("Incomplete JSON object in response")


async def groq_chat(
    messages: list[dict],
    *,
    temperature: float = 0.4,
    max_tokens: int | None = None,
) -> str:
    """Send a chat completion to Groq and return the response content.

    Raises :class:`GroqError` on a missing key, transport failure, non-200
    response, or empty content.
    """
    if not settings.groq_api_key:
        raise GroqError("GROQ_API_KEY not configured")

    payload: dict = {
        "model": settings.groq_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens or settings.groq_max_tokens,
    }
    # gpt-oss reasoning models accept reasoning_effort; sending it to a
    # non-reasoning model would be rejected, so only attach it for those.
    if "gpt-oss" in settings.groq_model:
        payload["reasoning_effort"] = settings.groq_reasoning_effort

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                GROQ_CHAT_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.groq_api_key}",
                },
                json=payload,
            )
    except httpx.HTTPError as exc:
        logger.error(f"Groq API request failed: {exc}")
        raise GroqError(f"Groq API request failed: {exc}") from exc

    if response.status_code != 200:
        try:
            detail = response.json().get("error", {}).get("message", "Unknown error")
        except Exception:  # noqa: BLE001 - error body may not be JSON
            detail = response.text[:200]
        logger.error(f"Groq API error: {response.status_code} - {detail}")
        raise GroqError(f"Groq API error: {detail}")

    choice = response.json()["choices"][0]
    content = choice["message"].get("content") or ""
    finish_reason = choice.get("finish_reason")

    # A reasoning model can exhaust max_tokens on reasoning and return
    # empty/truncated content with finish_reason="length". Surface that as an
    # error instead of handing callers an empty string.
    if not content.strip():
        logger.error(f"Groq returned empty content (finish_reason={finish_reason})")
        raise GroqError(
            "Groq returned an empty response "
            f"(finish_reason={finish_reason}). The model likely ran out of "
            "token budget; try a shorter prompt or raise GROQ_MAX_TOKENS."
        )
    if finish_reason == "length":
        logger.warning("Groq response truncated (finish_reason=length)")

    return content


async def groq_json(
    prompt: str,
    system_prompt: str,
    *,
    temperature: float = 0.3,
) -> dict:
    """Call Groq for a structured answer and return the parsed JSON object."""
    content = await groq_chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    try:
        return extract_json(content)
    except ValueError as exc:  # includes json.JSONDecodeError
        logger.error(f"Groq response was not valid JSON: {exc}")
        raise GroqError(f"Groq response was not valid JSON: {exc}") from exc
