
import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    Depends
)
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.core.database import get_db

from app.models.image import Image
from app.models.processing_job import ProcessingJob
from app.models.image_metadata import ImageMetadata
from app.models.suggestion import Suggestion
from app.models.review import Review
from app.models.ai_usage_log import AIUsageLog

from app.services.image_service import register_image

from app.schemas.image import (
    ImageUploadResponse,
    ImageResponse,
    ImageMetadataResponse,
    ImageProcessRequest,
    ImageProcessResponse,
)


router = APIRouter(prefix="/images", tags=["Images"])
logger = logging.getLogger(__name__)


# Image storage configuration
BASE_DIR = Path(__file__).resolve().parents[3]
UPLOAD_DIR = BASE_DIR / "data" / "images"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp"
}


# Validate actual image content
def validate_image(content: bytes, extension: str) -> bool:

    if extension in {".jpg", ".jpeg"}:
        return content.startswith(b"\xff\xd8\xff")

    if extension == ".png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")

    if extension == ".webp":
        return (
            content.startswith(b"RIFF")
            and content[8:12] == b"WEBP"
        )

    return False


# Upload image
@router.post(
    "/upload",
    response_model=ImageUploadResponse
)
async def upload_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format"
        )

    content = await file.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Image size must not exceed 5 MB"
        )

    if not validate_image(content, extension):
        raise HTTPException(
            status_code=400,
            detail="Invalid image file"
        )

    filename = f"{uuid4()}{extension}"

    file_path = UPLOAD_DIR / filename
    relative_path = f"data/images/{filename}"

    try:

        file_path.write_bytes(content)

        image, job = register_image(
            db=db,
            filename=filename,
            file_path=relative_path
        )

        return ImageUploadResponse(
            message="Image uploaded successfully",
            image_id=image.id,
            filename=image.filename,
            processing_status=image.processing_status,
            job_id=job.id,
            job_status=job.status
        )

    except Exception:
        db.rollback()
        logger.exception("Image upload failed for filename %s", filename)

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Image upload failed"
        )

    finally:
        await file.close()


# Retrieve all images
@router.get("/", response_model=list[ImageResponse])
def get_images(db: Session = Depends(get_db)):

    statement = select(Image).order_by(
        Image.created_at.desc()
    )

    images = db.scalars(statement).all()
    metadata_by_image_id = {
        metadata.image_id: metadata
        for metadata in db.scalars(select(ImageMetadata)).all()
    }

    return [
        ImageResponse(
            id=image.id,
            filename=image.filename,
            file_path=image.file_path,
            processing_status=image.processing_status,
            created_at=image.created_at,
            metadata=(
                ImageMetadataResponse.model_validate(
                    metadata_by_image_id[image.id]
                )
                if image.id in metadata_by_image_id
                else None
            ),
        )
        for image in images
    ]


@router.post(
    "/process",
    response_model=ImageProcessResponse,
    status_code=202,
)
def process_image_request(
    payload: ImageProcessRequest,
    db: Session = Depends(get_db),
):
    """Queue an image for the background vision worker."""

    image = db.get(Image, payload.image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="Image not found")

    job = db.scalar(
        select(ProcessingJob)
        .where(ProcessingJob.image_id == image.id)
        .order_by(ProcessingJob.created_at.desc())
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Processing job not found")

    if job.status == "completed":
        return ImageProcessResponse(
            image_id=image.id,
            job_id=job.id,
            processing_status=image.processing_status,
            job_status=job.status,
            message="Image has already been processed",
        )

    if job.status == "processing":
        return ImageProcessResponse(
            image_id=image.id,
            job_id=job.id,
            processing_status=image.processing_status,
            job_status=job.status,
            message="Image processing is already in progress",
        )

    if job.status == "failed" and job.attempts >= job.max_attempts:
        raise HTTPException(
            status_code=409,
            detail="Image processing has exhausted its retry attempts",
        )

    job.status = "pending"
    job.next_attempt_at = None
    job.error_message = None
    image.processing_status = "pending"
    db.commit()

    return ImageProcessResponse(
        image_id=image.id,
        job_id=job.id,
        processing_status=image.processing_status,
        job_status=job.status,
        message="Image queued for background processing",
    )


# Retrieve one image
@router.get("/{image_id}", response_model=ImageResponse)
def get_image(
    image_id: UUID,
    db: Session = Depends(get_db)
):

    image = db.get(Image, image_id)

    if image is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    metadata = db.scalar(
        select(ImageMetadata).where(ImageMetadata.image_id == image.id)
    )
    return ImageResponse(
        id=image.id,
        filename=image.filename,
        file_path=image.file_path,
        processing_status=image.processing_status,
        created_at=image.created_at,
        metadata=(
            ImageMetadataResponse.model_validate(metadata)
            if metadata is not None
            else None
        ),
    )


# Retrieve image processing status
@router.get("/{image_id}/status")
def get_image_status(
    image_id: UUID,
    db: Session = Depends(get_db)
):

    image = db.get(Image, image_id)

    if image is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    return {
        "image_id": str(image.id),
        "processing_status": image.processing_status
    }


# Delete image
@router.delete("/{image_id}")
def delete_image(
    image_id: UUID,
    db: Session = Depends(get_db)
):

    image = db.get(Image, image_id)

    if image is None:
        raise HTTPException(
            status_code=404,
            detail="Image not found"
        )

    file_path = BASE_DIR / image.file_path

    try:

        # Delete reviews linked to suggestions for this image
        suggestion_ids = select(Suggestion.id).where(
            Suggestion.image_id == image_id
        )

        db.execute(
            delete(Review).where(
                Review.suggestion_id.in_(suggestion_ids)
            )
        )

        # Delete AI usage logs linked to this image
        db.execute(
            delete(AIUsageLog).where(
                AIUsageLog.image_id == image_id
            )
        )

        # Delete suggestions
        db.execute(
            delete(Suggestion).where(
                Suggestion.image_id == image_id
            )
        )

        # Delete metadata
        db.execute(
            delete(ImageMetadata).where(
                ImageMetadata.image_id == image_id
            )
        )

        # Delete processing jobs
        db.execute(
            delete(ProcessingJob).where(
                ProcessingJob.image_id == image_id
            )
        )

        # Delete image record
        db.delete(image)

        db.commit()

    except Exception:
        db.rollback()
        logger.exception("Image deletion failed for image %s", image_id)

        raise HTTPException(
            status_code=500,
            detail="Image deletion failed"
        )

    # Remove local image after successful database deletion
    if file_path.exists():
        file_path.unlink()

    return {
        "message": "Image deleted successfully",
        "image_id": str(image_id)
    }
