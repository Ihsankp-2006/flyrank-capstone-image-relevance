"""Persist auditable AI operation metadata without inventing provider usage."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ai_usage_log import AIUsageLog


def log_ai_usage(
    db: Session,
    *,
    operation: str,
    model_name: str,
    duration_ms: int | None,
    image_id: UUID | None = None,
    post_id: UUID | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
    commit: bool = False,
) -> AIUsageLog:
    """Store measured/provider-reported values; unknown fields stay NULL."""

    log = AIUsageLog(
        image_id=image_id,
        post_id=post_id,
        operation=operation,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        duration_ms=duration_ms,
        estimated_cost_usd=estimated_cost_usd,
    )
    db.add(log)

    if commit:
        db.commit()
        db.refresh(log)
    else:
        db.flush()

    return log
