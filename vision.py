import base64

from groq import Groq
from config import GROQ_API_KEY

_client = Groq(api_key=GROQ_API_KEY)

# Groq's vision-capable chat model, per console.groq.com/docs/vision at the
# time this was written. Groq's model lineup moves fast — if a call here
# ever errors with something like "model not found" or "decommissioned",
# check that page for the current vision model id and update this constant.
VISION_MODEL = "qwen/qwen3.6-27b"

# Told to transcribe rather than describe/summarize, so the result reads
# like an OCR pass and is safe to store verbatim as a memory — a vision
# model asked "what's in this image?" tends to narrate ("a flyer
# advertising...") instead of reproducing the actual text.
EXTRACTION_PROMPT = (
    "Read every piece of text visible in this image (signs, invitations, "
    "flyers, screenshots, handwriting, labels, etc.) and transcribe it "
    "exactly, in a natural reading order. Don't summarize, describe the "
    "image, or add commentary — output only the transcribed text itself, "
    "with no surrounding quotes or markdown. If there is no legible text "
    "anywhere in the image, respond with exactly: NO_TEXT_FOUND"
)


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_text(image_path: str) -> str:
    """Send an image to Groq's vision model and return the text found in
    it, transcribed as-is (not summarized). Returns "" if no legible text
    was found, so callers can treat that the same as an empty voice
    transcription."""
    data_url = f"data:image/jpeg;base64,{_encode_image(image_path)}"

    response = _client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0.2,
        # Plain max_tokens, not max_completion_tokens — see the note in
        # llm.py: the pinned groq==0.9.0 SDK's create() predates the newer
        # named parameter and raises a TypeError if it's passed directly.
        #
        # Kept comfortably under 1000: this org's free/on-demand tier caps
        # qwen/qwen3.6-27b at 1000 output tokens per minute (OTPM), and Groq
        # rejects the request outright if max_tokens alone exceeds that —
        # it doesn't matter that a typical extraction uses far fewer than
        # 900 tokens, the requested ceiling is checked before the call
        # runs. If this ever gets bumped back up, confirm the account's
        # current OTPM limit for this model first (console.groq.com,
        # Settings > Limits) — it's an org-wide cap shared with any other
        # concurrent use of the same model, not just this bot.
        max_tokens=900,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text or text == "NO_TEXT_FOUND":
        return ""
    return text
