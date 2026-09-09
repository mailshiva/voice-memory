FROM python:3.12-slim

# ffmpeg is needed by faster-whisper (via PyAV) to read audio files
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download model weights at build time (not import-time config, so no
# secrets are needed here) — this means a job using this image doesn't need
# to fetch anything from Hugging Face at runtime, which is most of what
# made each Actions run slow before.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8')"

COPY . .

CMD ["python", "poll_once.py"]
