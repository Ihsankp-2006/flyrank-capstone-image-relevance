import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("ix_processing_jobs_status_created_at", "status", "created_at"),
        Index("ix_processing_jobs_image_id", "image_id"),
        Index(
            "ix_processing_jobs_status_next_attempt_at",
            "status",
            "next_attempt_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("images.id"),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False
    )

    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )

    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
