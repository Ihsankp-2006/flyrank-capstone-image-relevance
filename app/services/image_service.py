
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.image import Image
from app.models.processing_job import ProcessingJob


def register_image(
    db: Session,
    filename: str,
    file_path: str
):
    """
    Save image information and create a processing job.
    """

    try:
        # Create image database record
        image = Image(
            filename=filename,
            file_path=file_path,
            processing_status="pending"
        )

        db.add(image)
        db.flush()

        # Create processing job for this image
        job = ProcessingJob(
            image_id=image.id,
            status="pending",
            attempts=0,
            max_attempts=3
        )

        db.add(job)

        # Save both records
        db.commit()

        db.refresh(image)
        db.refresh(job)

        return image, job

    except Exception:
        db.rollback()
        raise


def register_offline_image(
    db: Session,
    *,
    filename: str,
    file_path: str,
) -> Image:
    """Register an evaluation image without creating an AI processing job."""

    existing = db.scalar(
        select(Image).where(Image.file_path == file_path)
    )
    if existing is not None:
        return existing

    image = Image(
        filename=filename,
        file_path=file_path,
        processing_status="pending",
    )
    db.add(image)
    db.commit()
    db.refresh(image)
    return image
