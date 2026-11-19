
import pytest

from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.image_metadata import ImageMetadata
from app.models.processing_job import ProcessingJob
from app.models.ai_usage_log import AIUsageLog
from app.services.image_service import register_image
from app.services.vision import pipeline_service
from app.services.vision.vision_service import VisionAnalysis
from app.services.embeddings import content_embedding_service


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()

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


def test_complete_image_processing_workflow(
    db, tmp_path, monkeypatch
):
    # 1. Create a temporary image file
    image_dir = tmp_path / "data" / "images"
    image_dir.mkdir(parents=True)

    image_file = image_dir / "fox.jpg"
    image_file.write_bytes(b"fake-image-data")

    # 2. Register image and create processing job
    image, job = register_image(
        db=db,
        filename="fox.jpg",
        file_path="data/images/fox.jpg"
    )

    assert image.processing_status == "pending"
    assert job.status == "pending"

    # 3. Configure pipeline to use temporary directory
    monkeypatch.setattr(
        pipeline_service,
        "BASE_DIR",
        tmp_path
    )

    # 4. Mock Gemini vision response
    mock_analysis = VisionAnalysis(
        subject="Fox",
        category="Wildlife",
        attributes={
            "color": "Orange",
            "environment": "Forest"
        },
        caption="An orange fox standing in a forest.",
        confidence=0.96
    )

    monkeypatch.setattr(
        pipeline_service,
        "analyze_image",
        lambda **kwargs: mock_analysis
    )

    monkeypatch.setattr(
        content_embedding_service,
        "generate_embedding",
        lambda text: [0.1] * 768
    )

    # 5. Process the registered image
    result = pipeline_service.process_image(
        db=db,
        image_id=image.id,
        job_id=job.id
    )

    # 6. Verify processing result
    assert result["status"] == "completed"
    assert result["subject"] == "Fox"

    db.refresh(image)
    db.refresh(job)

    assert image.processing_status == "completed"
    assert job.status == "completed"
    assert job.attempts == 1

    # 7. Verify metadata was saved in PostgreSQL
    metadata = (
        db.query(ImageMetadata)
        .filter(ImageMetadata.image_id == image.id)
        .first()
    )

    assert metadata is not None
    assert metadata.subject == "Fox"
    assert metadata.category == "Wildlife"
    assert metadata.confidence == 0.96
    assert metadata.attributes["color"] == "Orange"
    
    assert metadata.attributes["environment"] == "Forest"
    assert metadata.embedding == [0.1] * 768
    assert metadata.embedding_model == "gemini-embedding-2"

    usage_logs = db.query(AIUsageLog).filter(AIUsageLog.image_id == image.id).all()
    assert {log.operation for log in usage_logs} == {
        "vision_analysis", "image_metadata_embedding"
    }
    assert all(log.duration_ms is not None for log in usage_logs)
    assert all(log.input_tokens is None for log in usage_logs)
    assert all(log.estimated_cost_usd is None for log in usage_logs)
    
    print("\nComplete image-processing workflow passed!")
