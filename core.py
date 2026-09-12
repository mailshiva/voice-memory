import os
import re
import tempfile

from stt import transcribe
from embeddings import embed
from vision import extract_text as extract_image_text
from db import store_memory, search_memories, delete_memory, get_memory, update_memory
from llm import answer_question, compose_photo_memory


HELP_TEXT = (
    "Send me a voice note and I'll remember it.\n\n"
    "To save a typed note, start your message with /mem, e.g.\n"
    "/mem Paid the electrician $200 on July 8th\n\n"
    "Every saved memory gets shown with an id number. To erase one, say or "
    "type \"erase 101\" or \"erase id 101\".\n\n"
    "To fix a transcription typo, type /upd <id> <wrong text>: <correct "
    "text>, e.g.\n"
    "/upd 101 said: side\n"
    "If that text appears more than once in the memory, every occurrence "
    "gets replaced — add a surrounding word or two to target just one "
    "occurrence, e.g. /upd 101 said hello: side hello. Typed only, not "
    "supported via voice.\n\n"
    "Send a photo of anything with text in it (an invite, a sign, a note) "
    "and I'll read and save it. Add a caption for context, e.g. \"remember "
    "this\" — the caption is kept alongside the text I read.\n\n"
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

# Matches the part of an "/upd ..." command after the "/upd" prefix has
# already been stripped, e.g. "101 said: side" or
# "id 101 said hello: side hello". Group 1 is the memory id, group 2 the
# text to find (everything up to the last colon), group 3 the replacement
# text. Typed only — never matched against voice transcriptions, since the
# colon and exact wording it depends on are exactly what Whisper tends to
# mangle.
UPDATE_PATTERN = re.compile(
    r"^\s*(?:id\s+)?(\d+)\s+(.+?)\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)


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


async def update_memory_text(bot, chat_id: int, memory_id: int, old_text: str, new_text: str) -> None:
    memory = get_memory(memory_id)
    if memory is None:
        await bot.send_message(chat_id=chat_id, text=f"No memory found with id {memory_id}.")
        return

    find_pattern = re.compile(re.escape(old_text), re.IGNORECASE)
    new_content, count = find_pattern.subn(new_text, memory["content"])

    if count == 0:
        await bot.send_message(
            chat_id=chat_id,
            text=f"Memory {memory_id} doesn't contain \"{old_text}\" — nothing changed.",
        )
        return

    vector = embed(new_content)
    update_memory(memory_id, new_content, vector)
    times = "1 occurrence" if count == 1 else f"{count} occurrences"
    await bot.send_message(
        chat_id=chat_id,
        text=f"Updated (id {memory_id}, {times} replaced): \"{new_content}\"",
    )


async def process_upd_command(bot, chat_id: int, text: str) -> None:
    content = text.removeprefix("/upd").strip()
    match = UPDATE_PATTERN.match(content)
    if not match:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Usage: /upd <id> <wrong text>: <correct text>\n"
                "e.g. /upd 101 said: side"
            ),
        )
        return

    memory_id = int(match.group(1))
    old_text = match.group(2)
    new_text = match.group(3)
    await update_memory_text(bot, chat_id, memory_id, old_text, new_text)


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


async def _download_photo(bot, file_id: str) -> str:
    tg_file = await bot.get_file(file_id)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        await tg_file.download_to_drive(tmp.name)
        return tmp.name


async def process_photo(bot, chat_id: int, file_id: str, caption: str | None, sent_at=None) -> None:
    image_path = await _download_photo(bot, file_id)
    try:
        extracted = extract_image_text(image_path)
    finally:
        os.remove(image_path)

    if not extracted:
        await bot.send_message(chat_id=chat_id, text="Couldn't find any readable text in that photo.")
        return

    caption = (caption or "").strip()
    if caption:
        # An LLM pass rather than a plain prefix, so a real instruction in
        # the caption ("store the b'day, boy's name, and whose son he is")
        # actually gets followed, not just stapled onto the raw OCR text —
        # while a plain note caption ("remember this") still degrades
        # gracefully to something close to the old behavior (see the
        # fallback and prompt in compose_photo_memory).
        content = compose_photo_memory(caption, extracted, sent_at)
    else:
        content = extracted
    await save_memory(bot, chat_id, content, source="photo")


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