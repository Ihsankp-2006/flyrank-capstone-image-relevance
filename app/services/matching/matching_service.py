"""pgvector retrieval for ranking images against a blog post."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.image import Image
from app.models.image_metadata import ImageMetadata
from app.models.post import Post


class PostNotFoundError(ValueError):
    """The requested post does not exist."""


class MissingPostEmbeddingError(ValueError):
    """The requested post cannot be searched until it has an embedding."""


@dataclass(frozen=True)
class ImageMatch:
    """A ranked semantic candidate; it is not yet a suitability decision."""

    post_id: UUID
    image_id: UUID
    cosine_distance: float
    similarity_score: float


def find_matching_images(
    db: Session,
    post_id: UUID,
    *,
    top_k: int = 5,
) -> list[ImageMatch]:
    """Return completed image candidates ordered by pgvector cosine distance.

    pgvector's ``<=>`` operator returns cosine distance, where lower values are
    better. The application exposes similarity as ``1 - cosine_distance`` and
    intentionally does not clamp that value: cosine similarity can be negative.
    """

    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")

    post = db.get(Post, post_id)

    if post is None:
        raise PostNotFoundError("Post not found")

    if post.embedding is None:
        raise MissingPostEmbeddingError("Post embedding is missing")

    cosine_distance = ImageMetadata.embedding.cosine_distance(
        post.embedding
    ).label("cosine_distance")

    statement = (
        select(Image.id, cosine_distance)
        .join(ImageMetadata, ImageMetadata.image_id == Image.id)
        .where(
            Image.processing_status == "completed",
            ImageMetadata.embedding.is_not(None),
        )
        .order_by(cosine_distance.asc())
        .limit(top_k)
    )

    rows = db.execute(statement).all()

    return [
        ImageMatch(
            post_id=post.id,
            image_id=row.id,
            cosine_distance=float(row.cosine_distance),
            similarity_score=1.0 - float(row.cosine_distance),
        )
        for row in rows
    ]
