"""Application service for creating posts with searchable embeddings."""

from sqlalchemy.orm import Session
from time import perf_counter

from app.models.post import Post
from app.services.embeddings.content_embedding_service import embed_post
from app.services.embeddings.embedding_service import EMBEDDING_MODEL
from app.services.ai_usage_service import log_ai_usage


def create_post_with_embedding(
    db: Session,
    *,
    title: str,
    content: str,
) -> Post:
    """Create a post and its embedding as one database transaction."""

    normalized_title = title.strip()
    normalized_content = content.strip()

    if not normalized_title:
        raise ValueError("Post title cannot be empty")

    if not normalized_content:
        raise ValueError("Post content cannot be empty")

    try:
        post = Post(title=normalized_title, content=normalized_content)
        db.add(post)
        db.flush()

        embedding_started = perf_counter()
        embed_post(db, post.id, commit=False)
        log_ai_usage(
            db,
            post_id=post.id,
            operation="post_embedding",
            model_name=EMBEDDING_MODEL,
            duration_ms=round((perf_counter() - embedding_started) * 1000),
        )

        db.commit()
        db.refresh(post)
        return post
    except Exception:
        db.rollback()
        raise


def create_post_offline(
    db: Session,
    *,
    title: str,
    content: str,
) -> Post:
    """Create an intentionally unembedded post for offline evaluation import."""

    normalized_title = title.strip()
    normalized_content = content.strip()

    if not normalized_title:
        raise ValueError("Post title cannot be empty")

    if not normalized_content:
        raise ValueError("Post content cannot be empty")

    try:
        post = Post(
            title=normalized_title,
            content=normalized_content,
            embedding=None,
            embedding_model=None,
        )
        db.add(post)
        db.commit()
        db.refresh(post)
        return post
    except Exception:
        db.rollback()
        raise
