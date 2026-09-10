from groq import Groq
from config import GROQ_API_KEY

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
        # max_tokens=500 (deprecated name, too low a budget) let long
        # reasoning eat the whole allowance, leaving zero tokens for the
        # actual answer and producing an empty response — which Telegram's
        # API then rejects outright when it's sent as a message. Low
        # reasoning_effort keeps this a quick retrieval-QA task rather than
        # deep reasoning, so more of the (now larger) budget goes to the
        # actual answer.
        max_completion_tokens=1024,
        reasoning_effort="low",
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        # Belt and suspenders: whatever the cause, never hand back an
        # empty string — Telegram's send_message rejects empty text with a
        # BadRequest, which otherwise crashes the caller.
        return "Sorry, I couldn't come up with an answer for that — try rephrasing the question?"
    return content