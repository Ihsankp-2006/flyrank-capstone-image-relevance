from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models.image import Image
from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.services.matching.suggestion_service import generate_suggestions


def vector(*components: float) -> list[float]:
    return [*components, *([0.0] * (768 - len(components)))]


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    test_db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield test_db
    finally:
        test_db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def post_and_images(db):
    post = Post(
        title="Fox habitat",
        content="How foxes live in forest habitats.",
        embedding=vector(1.0, 0.0),
        embedding_model="gemini-embedding-2",
    )
    db.add(post)
    db.flush()

    fox = Image(filename="fox.jpg", file_path="data/images/fox.jpg", processing_status="completed")
    wolf = Image(filename="wolf.jpg", file_path="data/images/wolf.jpg", processing_status="completed")
    db.add_all([fox, wolf])
    db.flush()
    db.add_all([
        ImageMetadata(
            image_id=fox.id, subject="Fox", category="Wildlife", attributes={},
            caption="A fox in a forest.", confidence=0.9, embedding=vector(1.0, 0.0),
            embedding_model="gemini-embedding-2",
        ),
        ImageMetadata(
            image_id=wolf.id, subject="Wolf", category="Wildlife", attributes={},
            caption="A wolf in a forest.", confidence=0.9, embedding=vector(0.9, 0.1),
            embedding_model="gemini-embedding-2",
        ),
    ])
    db.flush()
    return post, fox, wolf


def test_generates_guarded_suggestions_and_is_idempotent(db, post_and_images):
    post, fox, wolf = post_and_images

    first = generate_suggestions(db, post.id, top_k=2)
    second = generate_suggestions(db, post.id, top_k=2)

    assert len(first) == 2
    assert len(second) == 2
    by_image = {suggestion.image_id: suggestion for suggestion in first}
    assert by_image[fox.id].guard_status == "accepted"
    assert by_image[wolf.id].guard_status == "rejected"
    assert "focuses on fox" in by_image[wolf.id].explanation
    assert {item.id for item in first} == {item.id for item in second}


@pytest.fixture
def client(db, post_and_images):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client, post_and_images
    app.dependency_overrides.clear()


def test_suggestion_endpoints_and_review_history(client):
    test_client, (post, fox, _) = client
    created = test_client.post(f"/api/posts/{post.id}/suggestions?top_k=2")

    assert created.status_code == 201
    suggestions = created.json()
    fox_suggestion = next(item for item in suggestions if item["image_id"] == str(fox.id))
    assert fox_suggestion["guard_status"] == "accepted"

    approved = test_client.post(f"/api/suggestions/{fox_suggestion['id']}/approve")
    rejected = test_client.post(f"/api/suggestions/{fox_suggestion['id']}/reject")

    assert approved.status_code == 201
    assert approved.json()["decision"] == "approved"
    assert rejected.status_code == 201
    assert rejected.json()["decision"] == "rejected"

    listed = test_client.get(f"/api/posts/{post.id}/suggestions")
    assert listed.status_code == 200
    assert len(listed.json()) == 2
