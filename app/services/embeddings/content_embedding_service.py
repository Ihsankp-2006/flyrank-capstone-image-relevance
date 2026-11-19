"""Persistence helpers for embeddings used by the matching engine."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.services.embeddings.embedding_service import (
    EMBEDDING_MODEL,
    generate_embedding,
)


MATCHING_TASK_PREFIX = (
    "task: semantic image-to-article matching | content: "
)


def _format_attributes(attributes: dict | None) -> str:
    """Return JSON metadata as stable, readable text for embedding."""

    if not attributes:
        return "None"

    return "; ".join(
        f"{key}: {value}"
        for key, value in sorted(attributes.items(), key=lambda item: str(item[0]))
    )


def build_image_embedding_text(metadata: ImageMetadata) -> str:
    """Build the text representation of one analyzed image."""

    return (
        f"{MATCHING_TASK_PREFIX}"
        f"Image subject: {metadata.subject}\n"
        f"Category: {metadata.category}\n"
        f"Attributes: {_format_attributes(metadata.attributes)}\n"
        f"Caption: {metadata.caption}"
    )


def build_post_embedding_text(post: Post) -> str:
    """Build the text representation of one blog post."""

    return (
        f"{MATCHING_TASK_PREFIX}"
        f"Post title: {post.title}\n"
        f"Post content: {post.content}"
    )


def embed_image_metadata(
    db: Session,
    image_id: UUID,
    *,
    commit: bool = True,
) -> ImageMetadata:
    """Generate and persist an embedding for an existing metadata record."""

    metadata = (
        db.query(ImageMetadata)
        .filter(ImageMetadata.image_id == image_id)
        .one_or_none()
    )

    if metadata is None:
        raise ValueError("Image metadata not found")

    metadata.embedding = generate_embedding(build_image_embedding_text(metadata))
    metadata.embedding_model = EMBEDDING_MODEL

    if commit:
        db.commit()
        db.refresh(metadata)
    else:
        db.flush()

    return metadata


def embed_post(
    db: Session,
    post_id: UUID,
    *,
    commit: bool = True,
) -> Post:
    """Generate and persist an embedding for an existing post."""

    post = db.get(Post, post_id)

    if post is None:
        raise ValueError("Post not found")

    post.embedding = generate_embedding(build_post_embedding_text(post))
    post.embedding_model = EMBEDDING_MODEL

    if commit:
        db.commit()
        db.refresh(post)
    else:
        db.flush()

    return post
