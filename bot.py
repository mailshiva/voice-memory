import os
import re
import tempfile

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN
from stt import transcribe
from embeddings import embed
from db import store_memory, search_memories, delete_memory
from llm import answer_question


HELP_TEXT = (
    "Send me a voice note and I'll remember it.\n\n"
    "To save a typed note, start your message with /mem, e.g.\n"
    "/mem Paid the electrician $200 on July 8th\n\n"
    "Every saved memory gets shown with an id number. To erase one, say or "
    "type \"erase 101\" or \"erase id 101\".\n\n"
    "Any other text message is treated as a question, and I'll search your "
    "memories to answer it. In a voice note, start with the word "
    "\"question\" to ask instead of save, e.g. \"question, where did I park "
    "the car?\""
)

# Matches "erase 101", "erase id 101", with optional trailing punctuation,
# case-insensitive, from either typed text or Whisper-transcribed voice.
ERASE_PATTERN = re.compile(r"^\s*erase\s+(?:id\s+)?(\d+)\s*[.!]?\s*$", re.IGNORECASE)

# Matches a "question" prefix at the start of a voice transcription, e.g.
# "question, where did I park?" or "question where did I park".
QUESTION_PREFIX_PATTERN = re.compile(r"^\s*question\b[,:]?\s*", re.IGNORECASE)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)


async def _save_memory(update: Update, text: str, source: str) -> None:
    vector = embed(text)
    memory_id = store_memory(text, vector, source=source)
    await update.message.reply_text(f"Saved (id {memory_id}): \"{text}\"")


async def _erase_memory(update: Update, memory_id: int) -> None:
    deleted = delete_memory(memory_id)
    if deleted:
        await update.message.reply_text(f"Erased memory {memory_id}.")
    else:
        await update.message.reply_text(f"No memory found with id {memory_id}.")


async def _answer(update: Update, question: str) -> None:
    vector = embed(question)
    memories = search_memories(vector)
    answer = answer_question(question, memories)
    await update.message.reply_text(answer)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    voice = update.message.voice
    tg_file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        audio_path = tmp.name

    try:
        text = transcribe(audio_path)
    finally:
        os.remove(audio_path)

    if not text:
        await update.message.reply_text("Couldn't make out any speech in that note.")
        return

    erase_match = ERASE_PATTERN.match(text)
    if erase_match:
        await _erase_memory(update, int(erase_match.group(1)))
        return

    question_match = QUESTION_PREFIX_PATTERN.match(text)
    if question_match:
        question = text[question_match.end():].strip()
        if not question:
            await update.message.reply_text("Heard \"question\" but no question after it.")
            return
        await _answer(update, question)
        return

    await _save_memory(update, text, source="voice")


async def handle_mem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.removeprefix("/mem").strip()
    if not text:
        await update.message.reply_text("Usage: /mem <what you want to save>")
        return
    await _save_memory(update, text, source="text")


async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()

    erase_match = ERASE_PATTERN.match(text)
    if erase_match:
        await _erase_memory(update, int(erase_match.group(1)))
        return

    await _answer(update, text)


def main() -> None:
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mem", handle_mem))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

    print("Bot running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
