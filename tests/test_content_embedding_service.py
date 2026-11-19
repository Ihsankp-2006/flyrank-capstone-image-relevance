import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.image import Image
from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.models.ai_usage_log import AIUsageLog
from app.services.embeddings import content_embedding_service
from app.services.embeddings.embedding_service import EMBEDDING_MODEL
from app.services.post_service import create_post_with_embedding


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
def image_metadata(db):
    image = Image(
        filename="fox.jpg",
        file_path="data/images/fox.jpg",
        processing_status="completed",
    )
    db.add(image)
    db.flush()

    metadata = ImageMetadata(
        image_id=image.id,
        subject="Fox",
        category="Wildlife",
        attributes={"environment": "forest", "color": "orange"},
        caption="An orange fox standing in a forest.",
        confidence=0.95,
    )
    db.add(metadata)
    db.flush()
    return metadata


def test_embed_image_metadata_persists_vector_and_model(
    db, image_metadata, monkeypatch
):
    captured_text = None

    def fake_generate_embedding(text):
        nonlocal captured_text
        captured_text = text
        return [0.1] * 768

    monkeypatch.setattr(
        content_embedding_service,
        "generate_embedding",
        fake_generate_embedding,
    )

    result = content_embedding_service.embed_image_metadata(
        db,
        image_metadata.image_id,
    )

    assert result.embedding == [0.1] * 768
    assert result.embedding_model == EMBEDDING_MODEL
    assert "semantic image-to-article matching" in captured_text
    assert "Image subject: Fox" in captured_text
    assert "Caption: An orange fox standing in a forest." in captured_text
    assert "color: orange; environment: forest" in captured_text


def test_embed_image_metadata_requires_metadata(db):
    from uuid import uuid4

    with pytest.raises(ValueError, match="Image metadata not found"):
        content_embedding_service.embed_image_metadata(db, uuid4())


def test_embed_post_persists_vector_and_model(db, monkeypatch):
    post = Post(
        title="Fox habitat",
        content="Red foxes commonly live near forest edges.",
    )
    db.add(post)
    db.flush()

    monkeypatch.setattr(
        content_embedding_service,
        "generate_embedding",
        lambda text: [0.2] * 768,
    )

    result = content_embedding_service.embed_post(db, post.id)

    assert result.embedding == [0.2] * 768
    assert result.embedding_model == EMBEDDING_MODEL


def test_create_post_with_embedding_is_atomic(db, monkeypatch):
    monkeypatch.setattr(
        content_embedding_service,
        "generate_embedding",
        lambda text: [0.3] * 768,
    )

    post = create_post_with_embedding(
        db,
        title="  Fox habitat  ",
        content="  Red foxes live near forest edges.  ",
    )

    assert post.title == "Fox habitat"
    assert post.content == "Red foxes live near forest edges."
    assert post.embedding == [0.3] * 768
    assert post.embedding_model == EMBEDDING_MODEL
    usage_log = db.query(AIUsageLog).filter(AIUsageLog.post_id == post.id).one()
    assert usage_log.operation == "post_embedding"
    assert usage_log.input_tokens is None
    assert usage_log.estimated_cost_usd is None


def test_create_post_rolls_back_when_embedding_fails(db, monkeypatch):
    def embedding_failure(text):
        raise RuntimeError("Temporary embedding API failure")

    monkeypatch.setattr(
        content_embedding_service,
        "generate_embedding",
        embedding_failure,
    )

    with pytest.raises(RuntimeError, match="Temporary embedding API failure"):
        create_post_with_embedding(
            db,
            title="Fox habitat",
            content="Red foxes live near forest edges.",
        )

    assert (
        db.query(Post)
        .filter(Post.title == "Fox habitat")
        .one_or_none()
        is None
    )


@pytest.mark.parametrize("title, content", [("", "content"), ("title", " ")])
def test_create_post_with_embedding_rejects_empty_fields(db, title, content):
    with pytest.raises(ValueError, match="cannot be empty"):
        create_post_with_embedding(db, title=title, content=content)
