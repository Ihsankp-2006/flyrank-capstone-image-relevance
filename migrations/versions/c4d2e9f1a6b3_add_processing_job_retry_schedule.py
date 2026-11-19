"""Add scheduled retry support for processing jobs

Revision ID: c4d2e9f1a6b3
Revises: b7e3c0a1d9f2
Create Date: 2026-11-19
"""

from alembic import op
import sqlalchemy as sa


revision = "c4d2e9f1a6b3"
down_revision = "b7e3c0a1d9f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "processing_jobs",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_processing_jobs_status_next_attempt_at",
        "processing_jobs",
        ["status", "next_attempt_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_status_next_attempt_at", table_name="processing_jobs")
    op.drop_column("processing_jobs", "next_attempt_at")
