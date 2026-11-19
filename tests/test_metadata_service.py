
import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.image import Image
from app.models.image_metadata import ImageMetadata
from app.services.vision.metadata_service import save_image_metadata
from app.services.vision.vision_service import VisionAnalysis


@pytest.fixture
def db():
    # Start an outer transaction
    connection = engine.connect()
    transaction = connection.begin()

    # Session commits use savepoints, preserving the outer transaction
    test_db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint"
    )

    try:
        yield test_db
    finally:
        test_db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def sample_image(db):
    image = Image(
        filename="test-fox.jpg",
        file_path="data/images/test-fox.jpg",
        processing_status="pending"
    )

    db.add(image)
    db.flush()

    return image


@pytest.fixture
def sample_analysis():
    return VisionAnalysis(
        subject="Fox",
        category="Wildlife",
        attributes={
            "color": "Orange",
            "environment": "Forest"
        },
        caption="An orange fox standing in a forest.",
        confidence=0.95
    )


def test_save_new_metadata(db, sample_image, sample_analysis):
    metadata = save_image_metadata(
        db=db,
        image_id=sample_image.id,
        analysis=sample_analysis
    )

    assert metadata.image_id == sample_image.id
    assert metadata.subject == "Fox"
    assert metadata.category == "Wildlife"
    assert metadata.confidence == 0.95

    assert sample_image.processing_status == "completed"


def test_update_existing_metadata(db, sample_image, sample_analysis):
    # Save initial metadata
    save_image_metadata(
        db=db,
        image_id=sample_image.id,
        analysis=sample_analysis
    )

    # Prepare updated analysis
    updated_analysis = VisionAnalysis(
        subject="Red Fox",
        category="Animal",
        attributes={
            "color": "Reddish orange",
            "environment": "Grassland"
        },
        caption="A red fox standing in grass.",
        confidence=0.98
    )

    # Update existing metadata
    updated_metadata = save_image_metadata(
        db=db,
        image_id=sample_image.id,
        analysis=updated_analysis
    )

    # Verify updated values
    assert updated_metadata.subject == "Red Fox"
    assert updated_metadata.category == "Animal"
    assert updated_metadata.confidence == 0.98

    # Changed metadata must not retain an embedding of its old description.
    updated_metadata.embedding = [0.1] * 768
    updated_metadata.embedding_model = "gemini-embedding-2"
    db.commit()

    updated_metadata = save_image_metadata(
        db=db,
        image_id=sample_image.id,
        analysis=sample_analysis,
    )

    assert updated_metadata.embedding is None
    assert updated_metadata.embedding_model is None

    # Confirm only one metadata record exists
    metadata_records = db.query(ImageMetadata).filter(
        ImageMetadata.image_id == sample_image.id
    ).all()

    assert len(metadata_records) == 1


def test_metadata_for_missing_image(db, sample_analysis):
    from uuid import uuid4

    with pytest.raises(ValueError, match="Image not found"):
        save_image_metadata(
            db=db,
            image_id=uuid4(),
            analysis=sample_analysis
        )
