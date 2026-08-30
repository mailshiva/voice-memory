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
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()
