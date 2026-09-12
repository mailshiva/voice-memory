from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from groq import Groq
from config import GROQ_API_KEY, USER_TIMEZONE

_client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = (
    "You are a personal memory assistant. You are given snippets the user "
    "recorded or typed in the past, each with a timestamp, followed by a "
    "question. Answer the question using only the snippets provided. If the "
    "snippets don't contain the answer, say so plainly instead of guessing."
)


def answer_question(question: str, memories: list[dict]) -> str:
    if not memories:
        context = "(No matching memories were found.)"
    else:
        context = "\n".join(
            f"- [{m['created_at']}] {m['content']}" for m in memories
        )

    user_prompt = f"Memories:\n{context}\n\nQuestion: {question}"

    response = _client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        # gpt-oss is a reasoning model — it spends tokens on a hidden
        # "thinking" pass before writing the visible answer. The previous
        # max_tokens=500 was too small a budget: long reasoning could eat
        # the whole allowance, leaving zero tokens for the actual answer
        # and producing an empty response — which Telegram's API then
        # rejects outright when it's sent as a message.
        #
        # NOTE: the pinned `groq==0.9.0` SDK predates both
        # `max_completion_tokens` and a typed `reasoning_effort` parameter
        # (its create() has a fixed argument list, no **kwargs passthrough
        # — passing either by name raises a TypeError on every call, which
        # is what actually broke every question after the first attempt at
        # this fix). `max_tokens` is the one this SDK version still
        # supports directly; `reasoning_effort` is instead smuggled into
        # the raw request body via `extra_body`, which this SDK does
        # support and which Groq's API (server-side, independent of SDK
        # version) accepts as a real field for gpt-oss models — low effort
        # keeps this a quick retrieval-QA task rather than deep reasoning,
        # leaving more of the budget for the actual answer.
        max_tokens=1024,
        extra_body={"reasoning_effort": "low"},
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        # Belt and suspenders: whatever the cause, never hand back an
        # empty string — Telegram's send_message rejects empty text with a
        # BadRequest, which otherwise crashes the caller.
        return "Sorry, I couldn't come up with an answer for that — try rephrasing the question?"
    return content


PHOTO_MEMORY_SYSTEM_PROMPT = (
    "You help turn a photo into a short factual memory note for a personal "
    "journal. You're given the user's caption on the photo, the raw text "
    "read off the photo itself (which may include chat-app clutter — "
    "sender names, timestamps, UI labels — mixed in with the actual "
    "content), and the date the photo was sent.\n\n"
    "If the caption gives a specific instruction about what to capture and "
    "how to phrase it, follow it — but only using facts actually present "
    "in the caption or the photo's text. Never invent a name, date, or "
    "relationship that isn't evidenced by the input.\n\n"
    "If something in the photo's text implies an event is happening "
    "\"today\" (a birthday wish, \"many happy returns\", \"congratulations "
    "on this special day\", etc.), use the given send date as that actual "
    "calendar date rather than leaving it vague.\n\n"
    "If the caption is just a plain note with no real instruction in it "
    "(e.g. \"remember this\"), don't overthink it — write a clean, "
    "readable version of the photo's text and keep the caption as a short "
    "prefix.\n\n"
    "Output ONLY the final memory text: one or two plain sentences, no "
    "preamble, no quotes, no markdown."
)


def compose_photo_memory(caption: str, extracted_text: str, sent_at: datetime | None) -> str:
    """Combine a photo's caption (a note, or an instruction like "store the
    b'day and whose son he is") with the text read off the photo into one
    memory string, resolving relative-date language ("today", "many happy
    returns") against the date the photo was actually sent rather than
    leaving it as a vague reference. Falls back to a plain
    "caption: extracted_text" concatenation if the Groq call fails or
    comes back empty, so a photo is never dropped over an LLM hiccup."""
    sent_at = sent_at or datetime.now(timezone.utc)
    local_date = sent_at.astimezone(ZoneInfo(USER_TIMEZONE)).strftime("%A, %B %d, %Y")

    user_prompt = (
        f"Caption: {caption}\n\n"
        f"Text read from the photo:\n{extracted_text}\n\n"
        f"Photo sent on: {local_date} (use this as \"today\" if the "
        "content implies something is happening today).\n\n"
        "Write the memory."
    )

    try:
        response = _client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": PHOTO_MEMORY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=300,
            extra_body={"reasoning_effort": "low"},
        )
        content = (response.choices[0].message.content or "").strip()
        if content:
            return content
    except Exception:
        pass  # fall through to the plain concatenation below

    return f"{caption}: {extracted_text}"