import os
import re
import tempfile

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


async def save_memory(bot, chat_id: int, text: str, source: str) -> None:
    vector = embed(text)
    memory_id = store_memory(text, vector, source=source)
    await bot.send_message(chat_id=chat_id, text=f"Saved (id {memory_id}): \"{text}\"")


async def erase_memory(bot, chat_id: int, memory_id: int) -> None:
    deleted = delete_memory(memory_id)
    if deleted:
        await bot.send_message(chat_id=chat_id, text=f"Erased memory {memory_id}.")
    else:
        await bot.send_message(chat_id=chat_id, text=f"No memory found with id {memory_id}.")


async def answer(bot, chat_id: int, question: str) -> None:
    vector = embed(question)
    memories = search_memories(vector)
    reply = answer_question(question, memories)
    await bot.send_message(chat_id=chat_id, text=reply)


async def process_text(bot, chat_id: int, text: str) -> None:
    """Handles a typed message that isn't /start or /mem: either an erase
    command or a question."""
    erase_match = ERASE_PATTERN.match(text)
    if erase_match:
        await erase_memory(bot, chat_id, int(erase_match.group(1)))
        return
    await answer(bot, chat_id, text)


async def process_mem_command(bot, chat_id: int, text: str) -> None:
    content = text.removeprefix("/mem").strip()
    if not content:
        await bot.send_message(chat_id=chat_id, text="Usage: /mem <what you want to save>")
        return
    await save_memory(bot, chat_id, content, source="text")


async def _download_and_transcribe(bot, file_id: str) -> str:
    tg_file = await bot.get_file(file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        audio_path = tmp.name
    try:
        return transcribe(audio_path)
    finally:
        os.remove(audio_path)


async def process_voice(bot, chat_id: int, file_id: str) -> None:
    text = await _download_and_transcribe(bot, file_id)

    if not text:
        await bot.send_message(chat_id=chat_id, text="Couldn't make out any speech in that note.")
        return

    erase_match = ERASE_PATTERN.match(text)
    if erase_match:
        await erase_memory(bot, chat_id, int(erase_match.group(1)))
        return

    question_match = QUESTION_PREFIX_PATTERN.match(text)
    if question_match:
        question = text[question_match.end():].strip()
        if not question:
            await bot.send_message(chat_id=chat_id, text="Heard \"question\" but no question after it.")
            return
        await answer(bot, chat_id, question)
        return

    await save_memory(bot, chat_id, text, source="voice")
