import asyncio

from telegram import Bot

from config import TELEGRAM_BOT_TOKEN
from db import get_state, set_state
from core import HELP_TEXT, process_voice, process_text, process_mem_command

STATE_KEY = "last_update_id"


async def main() -> None:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    last_id = get_state(STATE_KEY)
    offset = int(last_id) + 1 if last_id else None

    # Short poll (not run_polling's long-lived listen) — just grab whatever
    # is currently waiting, since this process exits right after.
    updates = await bot.get_updates(offset=offset, timeout=5)

    if not updates:
        print("No new messages.")
        return

    for update in updates:
        message = update.message
        if message is not None:
            chat_id = message.chat_id

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

        # Advance the stored offset even for update types we don't act on,
        # so they aren't re-fetched (and re-attempted) on the next run.
        set_state(STATE_KEY, str(update.update_id))

    print(f"Processed {len(updates)} update(s).")


if __name__ == "__main__":
    asyncio.run(main())
