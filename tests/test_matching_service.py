from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.image import Image
from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.services.matching.matching_service import (
    MissingPostEmbeddingError,
    PostNotFoundError,
    find_matching_images,
)


def vector(*components: float) -> list[float]:
    """Create a test vector compatible with the project's VECTOR(768) column."""

    return [*components, *([0.0] * (768 - len(components)))]


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


def create_image_with_embedding(
    db: Session,
    *,
    filename: str,
    embedding: list[float] | None,
    status: str = "completed",
) -> Image:
    image = Image(
        filename=filename,
        file_path=f"data/images/{filename}",
        processing_status=status,
    )
    db.add(image)
    db.flush()

    metadata = ImageMetadata(
        image_id=image.id,
        subject="Test subject",
        category="Test category",
        attributes={},
        caption="Test caption",
        confidence=0.9,
        embedding=embedding,
        embedding_model="gemini-embedding-2" if embedding else None,
    )
    db.add(metadata)
    db.flush()
    return image


def test_matches_are_ranked_by_pgvector_cosine_distance(db):
    post = Post(
        title="Fox habitat",
        content="About foxes.",
        embedding=vector(1.0, 0.0),
        embedding_model="gemini-embedding-2",
    )
    db.add(post)
    db.flush()

    identical = create_image_with_embedding(
        db, filename="identical.jpg", embedding=vector(1.0, 0.0)
    )
    orthogonal = create_image_with_embedding(
        db, filename="orthogonal.jpg", embedding=vector(0.0, 1.0)
    )
    opposite = create_image_with_embedding(
        db, filename="opposite.jpg", embedding=vector(-1.0, 0.0)
    )

    matches = find_matching_images(db, post.id, top_k=2)

    assert [match.image_id for match in matches] == [
        identical.id,
        orthogonal.id,
    ]
    assert matches[0].cosine_distance == pytest.approx(0.0)
    assert matches[0].similarity_score == pytest.approx(1.0)
    assert matches[1].cosine_distance == pytest.approx(1.0)
    assert matches[1].similarity_score == pytest.approx(0.0)

    all_matches = find_matching_images(db, post.id, top_k=3)
    assert all_matches[2].image_id == opposite.id
    assert all_matches[2].cosine_distance == pytest.approx(2.0)
    assert all_matches[2].similarity_score == pytest.approx(-1.0)


def test_skips_unprocessed_or_unembedded_images(db):
    post = Post(
        title="Fox habitat",
        content="About foxes.",
        embedding=vector(1.0, 0.0),
        embedding_model="gemini-embedding-2",
    )
    db.add(post)
    db.flush()

    eligible = create_image_with_embedding(
        db, filename="eligible.jpg", embedding=vector(1.0, 0.0)
    )
    create_image_with_embedding(
        db, filename="pending.jpg", embedding=vector(1.0, 0.0), status="pending"
    )
    create_image_with_embedding(
        db, filename="missing-vector.jpg", embedding=None
    )

    matches = find_matching_images(db, post.id)

    assert [match.image_id for match in matches] == [eligible.id]


def test_returns_empty_list_when_no_candidate_embeddings_exist(db):
    post = Post(
        title="Fox habitat",
        content="About foxes.",
        embedding=vector(1.0, 0.0),
        embedding_model="gemini-embedding-2",
    )
    db.add(post)
    db.flush()

    assert find_matching_images(db, post.id) == []


def test_rejects_unknown_post_and_post_without_embedding(db):
    with pytest.raises(PostNotFoundError, match="Post not found"):
        find_matching_images(db, uuid4())

    post = Post(title="Not embedded", content="No vector yet.")
    db.add(post)
    db.flush()

    assert post.embedding is None
    assert post.embedding_model is None
    with pytest.raises(MissingPostEmbeddingError, match="embedding is missing"):
        find_matching_images(db, post.id)


@pytest.mark.parametrize("top_k", [0, -1, True, "5"])
def test_rejects_invalid_top_k(db, top_k):
    post = Post(
        title="Fox habitat",
        content="About foxes.",
        embedding=vector(1.0, 0.0),
        embedding_model="gemini-embedding-2",
    )
    db.add(post)
    db.flush()

    with pytest.raises(ValueError, match="top_k must be a positive integer"):
        find_matching_images(db, post.id, top_k=top_k)
