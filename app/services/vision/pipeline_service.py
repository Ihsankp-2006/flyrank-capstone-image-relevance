
import mimetypes
from time import perf_counter
from pathlib import Path
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.image import Image
from app.models.processing_job import ProcessingJob

from app.services.vision.vision_service import (
    InvalidImageInputError,
    VISION_MODEL,
    VisionConfigurationError,
    analyze_image,
)
from app.services.vision.metadata_service import save_image_metadata
from app.services.embeddings.content_embedding_service import embed_image_metadata
from app.services.embeddings.embedding_service import EmbeddingConfigurationError
from app.services.embeddings.embedding_service import EMBEDDING_MODEL
from app.services.ai_usage_service import log_ai_usage


BASE_DIR = Path(__file__).resolve().parents[3]
RETRY_BASE_SECONDS = 5
RETRY_MAX_SECONDS = 300


def _is_permanent_processing_error(error: Exception) -> bool:
    """Identify failures for which retrying the same job cannot help."""

    return isinstance(
        error,
        (
            FileNotFoundError,
            InvalidImageInputError,
            VisionConfigurationError,
            EmbeddingConfigurationError,
        ),
    )


def retry_delay_seconds(attempts: int) -> int:
    """Return capped exponential retry delay for a failed processing attempt."""

    return min(RETRY_BASE_SECONDS * (2 ** max(attempts - 1, 0)), RETRY_MAX_SECONDS)


def process_image(
    db: Session,
    image_id: UUID,
    job_id: UUID,
    already_claimed: bool = False
):
    image = db.get(Image, image_id)
    job = db.get(ProcessingJob, job_id)

    if image is None:
        raise ValueError("Image not found")

    if job is None or job.image_id != image_id:
        raise ValueError("Processing job not found")

    if job.status == "completed":
        return {"status": "completed", "message": "Already processed"}

    if job.attempts >= job.max_attempts and job.status != "processing":
        return {"status": "failed", "message": "Maximum attempts reached"}

    try:
        if already_claimed:
            if job.status != "processing":
                raise ValueError("Job has not been claimed by the worker")
        else:
            job.status = "processing"
            job.attempts += 1
            job.started_at = datetime.now(timezone.utc)
            job.completed_at = None
            job.next_attempt_at = None
            job.error_message = None

            image.processing_status = "processing"
            db.commit()

        file_path = BASE_DIR / image.file_path

        if not file_path.exists():
            raise FileNotFoundError("Image file not found")

        image_bytes = file_path.read_bytes()

        mime_type, _ = mimetypes.guess_type(str(file_path))

        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise InvalidImageInputError("Unsupported image format")

        vision_started = perf_counter()
        analysis = analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type
        )
        log_ai_usage(
            db,
            image_id=image_id,
            operation="vision_analysis",
            model_name=VISION_MODEL,
            duration_ms=round((perf_counter() - vision_started) * 1000),
        )

        save_image_metadata(
            db=db,
            image_id=image_id,
            analysis=analysis,
            commit=False,
        )

        # Keep metadata, its embedding, and completed job state in one
        # transaction so matching never sees only part of a successful run.
        embedding_started = perf_counter()
        embed_image_metadata(
            db=db,
            image_id=image_id,
            commit=False,
        )
        log_ai_usage(
            db,
            image_id=image_id,
            operation="image_metadata_embedding",
            model_name=EMBEDDING_MODEL,
            duration_ms=round((perf_counter() - embedding_started) * 1000),
        )

        job = db.get(ProcessingJob, job_id)

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = None
        job.next_attempt_at = None

        db.commit()

        return {
            "image_id": str(image_id),
            "job_id": str(job_id),
            "status": "completed",
            "subject": analysis.subject,
            "category": analysis.category
        }

    except Exception as error:
        db.rollback()

        job = db.get(ProcessingJob, job_id)
        image = db.get(Image, image_id)

        if job is None or image is None:
            raise

        permanent_error = _is_permanent_processing_error(error)

        if permanent_error or job.attempts >= job.max_attempts:
            job.status = "failed"
            image.processing_status = "failed"
            job.next_attempt_at = None
        else:
            job.status = "pending"
            image.processing_status = "pending"
            job.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                seconds=retry_delay_seconds(job.attempts)
            )

        job.error_message = str(error)
        job.completed_at = datetime.now(timezone.utc)

        db.commit()

        return {
            "image_id": str(image_id),
            "job_id": str(job_id),
            "status": job.status,
            "attempts": job.attempts,
            "error": str(error)
        }
