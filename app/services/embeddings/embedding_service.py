
from google import genai
from google.genai import types

from app.core.database import settings


EMBEDDING_MODEL = "gemini-embedding-2"
EMBEDDING_DIMENSIONS = 768


class EmbeddingConfigurationError(ValueError):
    """A local embedding configuration problem that cannot succeed on retry."""


def generate_embedding(text: str) -> list[float]:
    """Generate a 768-dimensional embedding for text."""

    if not settings.GEMINI_API_KEY:
        raise EmbeddingConfigurationError("GEMINI_API_KEY is missing from .env")

    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY
    )

    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSIONS
        )
    )

    if not response.embeddings:
        raise ValueError("Gemini returned no embedding")

    embedding = response.embeddings[0].values

    if embedding is None:
        raise ValueError("Embedding values are missing")

    if len(embedding) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSIONS} dimensions, "
            f"received {len(embedding)}"
        )

    return [float(value) for value in embedding]
