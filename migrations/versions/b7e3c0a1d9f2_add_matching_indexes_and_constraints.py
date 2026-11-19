"""Add matching and workflow indexes

Revision ID: b7e3c0a1d9f2
Revises: 402fb3250115
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa


revision = "b7e3c0a1d9f2"
down_revision = "402fb3250115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_images_processing_status", "images", ["processing_status"])
    op.create_index(
        "ix_processing_jobs_status_created_at",
        "processing_jobs",
        ["status", "created_at"],
    )
    op.create_index("ix_processing_jobs_image_id", "processing_jobs", ["image_id"])
    op.create_index("ix_image_metadata_image_id", "image_metadata", ["image_id"])
    op.create_index("ix_suggestions_post_id", "suggestions", ["post_id"])
    op.create_index("ix_suggestions_image_id", "suggestions", ["image_id"])
    op.create_index("ix_reviews_suggestion_id", "reviews", ["suggestion_id"])
    op.create_index("ix_ai_usage_logs_image_id", "ai_usage_logs", ["image_id"])
    op.create_index("ix_ai_usage_logs_post_id", "ai_usage_logs", ["post_id"])
    op.create_unique_constraint(
        "uq_suggestions_post_image", "suggestions", ["post_id", "image_id"]
    )
    op.create_index(
        "ix_image_metadata_embedding_hnsw_cosine",
        "image_metadata",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_where=sa.text("embedding IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_image_metadata_embedding_hnsw_cosine", table_name="image_metadata")
    op.drop_constraint("uq_suggestions_post_image", "suggestions", type_="unique")
    op.drop_index("ix_ai_usage_logs_post_id", table_name="ai_usage_logs")
    op.drop_index("ix_ai_usage_logs_image_id", table_name="ai_usage_logs")
    op.drop_index("ix_reviews_suggestion_id", table_name="reviews")
    op.drop_index("ix_suggestions_image_id", table_name="suggestions")
    op.drop_index("ix_suggestions_post_id", table_name="suggestions")
    op.drop_index("ix_image_metadata_image_id", table_name="image_metadata")
    op.drop_index("ix_processing_jobs_image_id", table_name="processing_jobs")
    op.drop_index("ix_processing_jobs_status_created_at", table_name="processing_jobs")
    op.drop_index("ix_images_processing_status", table_name="images")
