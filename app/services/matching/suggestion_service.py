"""Compose retrieval and guard decisions into persistent suggestions."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.models.review import Review
from app.models.suggestion import Suggestion
from app.services.guard.mismatch_guard import GuardPolicy, evaluate_image_match
from app.services.matching.matching_service import find_matching_images


def generate_suggestions(
    db: Session,
    post_id: UUID,
    *,
    top_k: int = 5,
    policy: GuardPolicy | None = None,
) -> list[Suggestion]:
    """Persist one idempotent suggestion per retrieved post/image pair."""

    post = db.get(Post, post_id)
    matches = find_matching_images(db, post_id, top_k=top_k)
    suggestions: list[Suggestion] = []

    try:
        for match in matches:
            existing = db.scalar(
                select(Suggestion).where(
                    Suggestion.post_id == post_id,
                    Suggestion.image_id == match.image_id,
                )
            )
            if existing is not None:
                suggestions.append(existing)
                continue

            metadata = db.scalar(
                select(ImageMetadata).where(ImageMetadata.image_id == match.image_id)
            )
            if metadata is None:
                continue

            decision = evaluate_image_match(
                post,
                metadata,
                match.similarity_score,
                policy=policy,
            )
            suggestion = Suggestion(
                post_id=post_id,
                image_id=match.image_id,
                similarity_score=match.similarity_score,
                guard_status=decision.status,
                explanation=decision.explanation,
            )
            db.add(suggestion)
            suggestions.append(suggestion)

        db.commit()
        for suggestion in suggestions:
            db.refresh(suggestion)
        return suggestions
    except Exception:
        db.rollback()
        raise


def list_post_suggestions(db: Session, post_id: UUID) -> list[Suggestion]:
    return list(
        db.scalars(
            select(Suggestion)
            .where(Suggestion.post_id == post_id)
            .order_by(Suggestion.similarity_score.desc(), Suggestion.created_at.desc())
        )
    )


def review_suggestion(
    db: Session,
    suggestion_id: UUID,
    decision: str,
) -> Review:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Review decision must be approved or rejected")

    if db.get(Suggestion, suggestion_id) is None:
        raise ValueError("Suggestion not found")

    review = Review(suggestion_id=suggestion_id, decision=decision)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review
