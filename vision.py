import base64

from groq import Groq
from config import GROQ_API_KEY

_client = Groq(api_key=GROQ_API_KEY)

# Groq's vision-capable chat model. Originally qwen/qwen3.6-27b, which
# started 404ing with "model_not_found" only days after this was built —
# Groq had dropped it from their lineup entirely. qwen/qwen3.8-27b is the
# only other vision-capable model Groq currently lists (as of 2026-09), but
# note it's a *Preview* model in Groq's own docs — "may be discontinued at
# short notice, not for production use" — so this may well need updating
# again. If a call here ever errors with "model not found"/"decommissioned"
# /"does not exist", check console.groq.com/docs/vision (or /docs/models)
# for whatever's current and swap it in here.
VISION_MODEL = "qwen/qwen3.8-27b"

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
        # Kept at 900 as a conservative carryover from qwen/qwen3.6-27b,
        # whose free/on-demand tier had a 1000-output-tokens-per-minute
        # (OTPM) cap that Groq enforces by rejecting the request outright
        # if max_tokens alone exceeds it — regardless of actual usage.
        # qwen3.8-27b's exact OTPM limit for this org hasn't been
        # separately confirmed; if this ever 429s with a rate_limit_exceeded
        # on output tokens, lower this further, or check the current limit
        # at console.groq.com under Settings > Limits.
        max_tokens=900,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text or text == "NO_TEXT_FOUND":
        return ""
    return text