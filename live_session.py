import asyncio
import os
import time
from datetime import datetime, timedelta, timezone

from telegram import Bot

from config import TELEGRAM_BOT_TOKEN
from db import get_state, set_state
from core import HELP_TEXT, process_voice, process_text, process_mem_command

STATE_KEY = "last_update_id"

# Shared with poll_once.py: while this holds a future UTC timestamp,
# poll_once.py skips its run instead of opening a second concurrent
# get_updates connection (Telegram allows only one per bot token and
# answers the second with a 409 Conflict).
SESSION_LOCK_KEY = "live_session_until"

# Telegram long-poll timeout per get_updates call, in seconds. The HTTP
# client's own read timeout is set a bit higher than this (see
# _get_updates below) so it never gives up before Telegram's long-poll
# wait itself would return.
POLL_TIMEOUT_SECONDS = 25

# Safety margin added on top of the requested duration when claiming the
# lock, so a slightly slow shutdown here doesn't let a scheduled poll_once
# run sneak in a moment early.
LOCK_MARGIN_SECONDS = 30


def _duration_minutes() -> float:
    raw = os.environ.get("DURATION_MINUTES", "15")
    try:
        value = float(raw)
    except ValueError:
        return 15.0
    return value if value > 0 else 15.0


async def _handle_update(bot: Bot, update) -> None:
    message = update.message
    if message is not None:
        chat_id = message.chat_id

        try:
            if message.voice:
                await process_voice(bot, chat_id, message.voice.file_id)
            elif message.text:
                text = message.text.strip()
                if text == "/start":
                    await bot.send_message(chat_id=chat_id, text=HELP_TEXT)
                elif text.startswith("/mem"):
                    await process_mem_command(bot, chat_id, text)
                else:
                    await process_text(bot, chat_id, text)
        except Exception as exc:
            # This is exactly what crashed the session before: one bad
            # message (e.g. an empty LLM response) propagating up and
            # ending the whole live_session.py run early — and, since
            # set_state below would then be skipped too, getting
            # re-fetched and re-failed by every future run forever. Log
            # it, tell the user, and keep listening instead.
            print(f"Error processing update {update.update_id}: {exc!r}")
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="Sorry, something went wrong processing that — try again?",
                )
            except Exception:
                pass  # best-effort notification only

    # Advance the stored offset even for update types we don't act on (or
    # ones that errored above), so they aren't re-fetched next time.
    set_state(STATE_KEY, str(update.update_id))


async def _get_updates(bot: Bot, offset, poll_timeout: int):
    # get_updates(timeout=...) tells Telegram how long to hold the request
    # open waiting for a new message. python-telegram-bot's own HTTP read
    # timeout defaults to a few seconds, which is shorter than our 25s
    # long-poll — without bumping it explicitly, the client would raise a
    # read timeout before Telegram ever gets to respond.
    return await bot.get_updates(
        offset=offset,
        timeout=poll_timeout,
        read_timeout=poll_timeout + 5,
    )


async def main() -> None:
    duration = _duration_minutes()
    deadline = time.monotonic() + duration * 60

    lock_until = datetime.now(timezone.utc) + timedelta(
        minutes=duration, seconds=LOCK_MARGIN_SECONDS
    )
    set_state(SESSION_LOCK_KEY, lock_until.strftime("%Y-%m-%dT%H:%M:%SZ"))

    print(f"Live session started — listening for up to {duration:.0f} minute(s).")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    try:
        last_id = get_state(STATE_KEY)
        offset = int(last_id) + 1 if last_id else None

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 1:
                break

            poll_timeout = max(1, min(POLL_TIMEOUT_SECONDS, int(remaining)))

            try:
                updates = await _get_updates(bot, offset, poll_timeout)
            except Exception as exc:
                # A transient network/Telegram hiccup shouldn't end the
                # whole session — log it and keep listening.
                print(f"get_updates error: {exc!r} — retrying")
                await asyncio.sleep(2)
                continue

            for update in updates:
                await _handle_update(bot, update)
                offset = update.update_id + 1

            if updates:
                print(f"Processed {len(updates)} update(s).")

        print("Live session window elapsed — shutting down.")

    finally:
        # Release the lock immediately rather than waiting for it to
        # expire on its own, so the regular schedule (or a manual
        # workflow_dispatch of poll.yml) can resume right away.
        set_state(SESSION_LOCK_KEY, "")


if __name__ == "__main__":
    asyncio.run(main())