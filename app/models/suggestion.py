import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = (
        UniqueConstraint("post_id", "image_id", name="uq_suggestions_post_image"),
        Index("ix_suggestions_post_id", "post_id"),
        Index("ix_suggestions_image_id", "image_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id"),
        nullable=False
    )

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("images.id"),
        nullable=False
    )

    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)

    guard_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    explanation: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
