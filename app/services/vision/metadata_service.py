
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.image import Image
from app.models.image_metadata import ImageMetadata
from app.services.vision.vision_service import VisionAnalysis


def save_image_metadata(
    db: Session,
    image_id: UUID,
    analysis: VisionAnalysis,
    *,
    commit: bool = True,
) -> ImageMetadata:

    # Find the image in the database
    image = db.get(Image, image_id)

    if image is None:
        raise ValueError("Image not found")

    try:
        # Check whether metadata already exists
        metadata = db.query(ImageMetadata).filter(
            ImageMetadata.image_id == image_id
        ).first()

        if metadata is None:
            # Create new metadata
            metadata = ImageMetadata(
                image_id=image_id,
                subject=analysis.subject,
                category=analysis.category,
                attributes=analysis.attributes,
                caption=analysis.caption,
                confidence=analysis.confidence
            )

            db.add(metadata)

        else:
            # Update existing metadata
            metadata.subject = analysis.subject
            metadata.category = analysis.category
            metadata.attributes = analysis.attributes
            metadata.caption = analysis.caption
            metadata.confidence = analysis.confidence

            # Metadata changes invalidate the previous text embedding.
            metadata.embedding = None
            metadata.embedding_model = None

        # Mark image processing as completed
        image.processing_status = "completed"

        if commit:
            db.commit()
            db.refresh(metadata)
        else:
            db.flush()

        return metadata

    except Exception:
        db.rollback()
        raise
        
