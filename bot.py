from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN
from core import HELP_TEXT, process_voice, process_photo, process_text, process_mem_command, process_upd_command


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_voice(context.bot, update.effective_chat.id, update.message.voice.file_id)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # message.photo is a list of resolutions Telegram generated for the
    # same image, ordered smallest to largest — take the largest.
    largest = update.message.photo[-1]
    await process_photo(
        context.bot,
        update.effective_chat.id,
        largest.file_id,
        update.message.caption,
        update.message.date,
    )


async def handle_mem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_mem_command(context.bot, update.effective_chat.id, update.message.text)


async def handle_upd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_upd_command(context.bot, update.effective_chat.id, update.message.text)


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_text(context.bot, update.effective_chat.id, update.message.text.strip())


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        # Longer timeouts than the library default (5s) — needed on modest
        # network throughput (e.g. a small cloud VM) so voice note downloads
        # don't spuriously time out.
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mem", handle_mem))
    app.add_handler(CommandHandler("upd", handle_upd))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

    print("Bot running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()