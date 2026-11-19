
from types import SimpleNamespace

import pytest

from app.services.embeddings import embedding_service


def test_generate_embedding_success(monkeypatch):
    fake_values = [0.1] * 768

    class FakeModels:
        def embed_content(self, **kwargs):
            assert kwargs["model"] == "gemini-embedding-2"
            assert kwargs["contents"] == "A fox in a forest."

            return SimpleNamespace(
                embeddings=[
                    SimpleNamespace(values=fake_values)
                ]
            )

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(
        embedding_service.settings,
        "GEMINI_API_KEY",
        "test-api-key"
    )

    monkeypatch.setattr(
        embedding_service.genai,
        "Client",
        FakeClient
    )

    result = embedding_service.generate_embedding(
        "A fox in a forest."
    )

    assert len(result) == 768
    assert all(isinstance(value, float) for value in result)


def test_missing_api_key(monkeypatch):
    monkeypatch.setattr(
        embedding_service.settings,
        "GEMINI_API_KEY",
        None
    )

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        embedding_service.generate_embedding("A fox")


def test_empty_text():
    with pytest.raises(ValueError, match="Text cannot be empty"):
        embedding_service.generate_embedding("   ")


def test_invalid_embedding_dimensions(monkeypatch):
    class FakeModels:
        def embed_content(self, **kwargs):
            return SimpleNamespace(
                embeddings=[
                    SimpleNamespace(values=[0.1] * 100)
                ]
            )

    class FakeClient:
        def __init__(self, api_key):
            self.models = FakeModels()

    monkeypatch.setattr(
        embedding_service.settings,
        "GEMINI_API_KEY",
        "test-api-key"
    )

    monkeypatch.setattr(
        embedding_service.genai,
        "Client",
        FakeClient
    )

    with pytest.raises(ValueError, match="Expected 768 dimensions"):
        embedding_service.generate_embedding("A fox")
