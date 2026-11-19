import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Float, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class ImageMetadata(Base):
    __tablename__ = "image_metadata"
    __table_args__ = (
        Index("ix_image_metadata_image_id", "image_id"),
        Index(
            "ix_image_metadata_embedding_hnsw_cosine",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("embedding IS NOT NULL"),
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
        unique=True,
        nullable=False
    )

    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False
    )

    embedding: Mapped[list | None] = mapped_column(Vector(768), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
