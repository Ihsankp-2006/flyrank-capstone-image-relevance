
import pytest

from app.core.database import engine
from app.models.image import Image
from app.models.image_metadata import ImageMetadata
from app.models.processing_job import ProcessingJob
from app.services.vision import pipeline_service
from app.services.vision.vision_service import VisionAnalysis

from sqlalchemy.orm import Session


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


@pytest.fixture
def sample_records(db):
    image = Image(
        filename="test-fox.jpg",
        file_path="data/images/test-fox.jpg",
        processing_status="pending"
    )

    db.add(image)
    db.flush()

    job = ProcessingJob(
        image_id=image.id,
        status="pending",
        attempts=0,
        max_attempts=3
    )

    db.add(job)
    db.flush()

    return image, job


@pytest.fixture
def sample_analysis():
    return VisionAnalysis(
        subject="Fox",
        category="Wildlife",
        attributes={"color": "Orange"},
        caption="An orange fox in a forest.",
        confidence=0.95
    )


def test_successful_processing(
    db, sample_records, sample_analysis, tmp_path, monkeypatch
):
    image, job = sample_records

    # Create a temporary image file
    image_dir = tmp_path / "data" / "images"
    image_dir.mkdir(parents=True)

    image_file = image_dir / "test-fox.jpg"
    image_file.write_bytes(b"fake-image-data")

    # Use temporary directory instead of project directory
    monkeypatch.setattr(
        pipeline_service,
        "BASE_DIR",
        tmp_path
    )

    # Mock Gemini response
    monkeypatch.setattr(
        pipeline_service,
        "analyze_image",
        lambda **kwargs: sample_analysis
    )

    monkeypatch.setattr(
        pipeline_service,
        "embed_image_metadata",
        lambda **kwargs: None
    )

    result = pipeline_service.process_image(
        db=db,
        image_id=image.id,
        job_id=job.id
    )

    assert result["status"] == "completed"
    assert result["subject"] == "Fox"

    db.refresh(image)
    db.refresh(job)

    assert image.processing_status == "completed"
    assert job.status == "completed"
    assert job.attempts == 1


def test_temporary_failure_allows_retry(
    db, sample_records, tmp_path, monkeypatch
):
    image, job = sample_records

    image_dir = tmp_path / "data" / "images"
    image_dir.mkdir(parents=True)

    image_file = image_dir / "test-fox.jpg"
    image_file.write_bytes(b"fake-image-data")

    monkeypatch.setattr(
        pipeline_service,
        "BASE_DIR",
        tmp_path
    )

    # Simulate a temporary Gemini/API error
    def mock_failure(**kwargs):
        raise RuntimeError("Temporary API failure")

    monkeypatch.setattr(
        pipeline_service,
        "analyze_image",
        mock_failure
    )

    result = pipeline_service.process_image(
        db=db,
        image_id=image.id,
        job_id=job.id
    )

    db.refresh(image)
    db.refresh(job)

    assert result["status"] == "pending"
    assert job.status == "pending"
    assert image.processing_status == "pending"
    assert job.attempts == 1
    assert job.next_attempt_at is not None


def test_missing_image_file(
    db, sample_records, tmp_path, monkeypatch
):
    image, job = sample_records

    # Use an empty temporary directory
    monkeypatch.setattr(
        pipeline_service,
        "BASE_DIR",
        tmp_path
    )

    result = pipeline_service.process_image(
        db=db,
        image_id=image.id,
        job_id=job.id
    )

    db.refresh(image)
    db.refresh(job)

    assert result["status"] == "failed"
    assert job.status == "failed"
    assert image.processing_status == "failed"
    assert job.attempts == 1


def test_embedding_failure_does_not_persist_partial_metadata(
    db, sample_records, sample_analysis, tmp_path, monkeypatch
):
    image, job = sample_records
    image_dir = tmp_path / "data" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "test-fox.jpg").write_bytes(b"fake-image-data")

    monkeypatch.setattr(pipeline_service, "BASE_DIR", tmp_path)
    monkeypatch.setattr(
        pipeline_service,
        "analyze_image",
        lambda **kwargs: sample_analysis,
    )

    def embedding_failure(**kwargs):
        raise RuntimeError("Temporary embedding API failure")

    monkeypatch.setattr(
        pipeline_service,
        "embed_image_metadata",
        embedding_failure,
    )

    result = pipeline_service.process_image(db, image.id, job.id)

    assert result["status"] == "pending"
    assert (
        db.query(ImageMetadata)
        .filter(ImageMetadata.image_id == image.id)
        .one_or_none()
        is None
    )


def test_retry_delay_is_exponential_and_capped():
    assert pipeline_service.retry_delay_seconds(1) == 5
    assert pipeline_service.retry_delay_seconds(2) == 10
    assert pipeline_service.retry_delay_seconds(10) == 300

