from faster_whisper import WhisperModel

# "base" is a good speed/accuracy tradeoff for personal voice memos on CPU.
# Use "small" or "medium" if you want better accuracy and have the CPU time to spare.
_model = WhisperModel("base", device="cpu", compute_type="int8")


def transcribe(audio_path: str) -> str:
    """Transcribe a local audio file (e.g. downloaded Telegram voice note) to text."""
    segments, _info = _model.transcribe(audio_path, beam_size=5)
    return " ".join(segment.text.strip() for segment in segments).strip()
