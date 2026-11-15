"""Telegram long-polling bot for standup collection.

Run as a standalone process: ``python -m app.integrations.telegram_bot``.

Responsibilities:
- Long-poll getUpdates (offset persisted in Redis so restarts don't replay).
- ``/start <code>``  -> link a Telegram account to a TeamMember.
- plain text          -> answer to the current standup question.

All DB / conversation logic lives in StandupService; this module is just the
transport loop + routing.
"""

import asyncio
import logging

from app.config import settings
from app.integrations import standup_state
from app.integrations.telegram_client import TelegramClient
from app.services.standup_service import StandupService
from app.tasks.db import create_task_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_BACKOFF_START = 1.0
_BACKOFF_MAX = 30.0


async def handle_update(update: dict, client: TelegramClient) -> None:
    """Route a single Telegram update."""
    message = update.get("message")
    if not message:
        return  # ignore non-message updates (edited, channel posts, etc.)

    chat_id = str(message["chat"]["id"])
    text = (message.get("text") or "").strip()
    username = message.get("from", {}).get("username")
    if not text:
        return

    async with create_task_session() as session:
        service = StandupService(session)

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            code = parts[1].strip() if len(parts) > 1 else ""
            reply = await service.link_member(code, chat_id, username)
            await client.send_message(chat_id, reply)
            return

        # Otherwise treat as an answer to the active standup question.
        result = await service.record_answer(chat_id, text)
        if result.reply:
            await client.send_message(chat_id, result.reply)
        if result.round_complete and result.round_id:
            from app.tasks.standup_tasks import close_standup_round

            close_standup_round.delay(result.round_id)


async def run_polling() -> None:
    client = TelegramClient(settings.telegram_bot_token)
    redis = standup_state.get_redis()
    offset = await standup_state.get_offset(redis)
    backoff = _BACKOFF_START
    logger.info("Telegram bot polling started (offset=%s)", offset)

    while True:
        try:
            updates = await client.get_updates(offset=offset, timeout=30)
            backoff = _BACKOFF_START  # reset after a successful poll
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    await handle_update(update, client)
                except Exception:  # noqa: BLE001 - one bad update must not kill the loop
                    logger.exception("Error handling update %s", update.get("update_id"))
                await standup_state.set_offset(redis, offset)
        except Exception:  # noqa: BLE001 - network/API errors: back off and retry
            logger.exception("Polling error; backing off %.1fs", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_MAX)


def main() -> None:
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; telegram bot exiting.")
        return
    asyncio.run(run_polling())


if __name__ == "__main__":
    main()
