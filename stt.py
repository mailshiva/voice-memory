import os
from faster_whisper import WhisperModel

# "base" is a good speed/accuracy tradeoff on most machines. On a low-RAM
# host (e.g. Google Cloud's free e2-micro, ~1GB RAM), set WHISPER_MODEL=tiny
# in .env to avoid running out of memory during transcription.
_model_size = os.environ.get("WHISPER_MODEL", "base")
_model = WhisperModel(_model_size, device="cpu", compute_type="int8")


def transcribe(audio_path: str) -> str:
    """Transcribe a local audio file (e.g. downloaded Telegram voice note) to text.
    Language is forced to English rather than auto-detected — auto-detection
    can misfire on short or quiet clips, especially with the smaller model
    sizes, and transcribe (or even translate) into the wrong language."""
    segments, _info = _model.transcribe(audio_path, beam_size=5, language="en")
    return " ".join(segment.text.strip() for segment in segments).strip()
