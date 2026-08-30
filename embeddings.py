from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL_NAME

_model = SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed(text: str) -> list[float]:
    """Return a 384-dim embedding vector for the given text."""
    vector = _model.encode(text, normalize_embeddings=True)
    return vector.tolist()
