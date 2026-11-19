from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.services.embeddings import content_embedding_service
from app.services import post_service


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    test_db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield test_db
    finally:
        test_db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(
        content_embedding_service,
        "generate_embedding",
        lambda text: [0.25] * 768,
    )
    app.dependency_overrides[get_db] = lambda: db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_create_post_persists_embedding(client):
    response = client.post(
        "/api/posts/",
        json={
            "title": "Fox habitat",
            "content": "Red foxes live near forest edges.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Fox habitat"
    assert body["embedding_model"] == "gemini-embedding-2"

    fetched = client.get(f"/api/posts/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]


def test_create_post_rejects_blank_title(client):
    response = client.post(
        "/api/posts/",
        json={"title": "   ", "content": "Red foxes live near forests."},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Post title cannot be empty"


def test_offline_post_import_does_not_call_embedding(db, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("offline import must not generate an embedding")

    monkeypatch.setattr(post_service, "embed_post", fail_if_called)

    post = post_service.create_post_offline(
        db,
        title="Offline evaluation post",
        content="This post intentionally has no embedding.",
    )

    assert post.embedding is None
    assert post.embedding_model is None


def test_get_post_returns_not_found_for_unknown_id(client):
    response = client.get("/api/posts/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
