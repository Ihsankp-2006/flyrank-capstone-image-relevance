from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import engine, get_db
from app.main import app
from app.models.image import Image
from app.models.processing_job import ProcessingJob


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    test_db = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield test_db
    finally:
        test_db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_image_and_job(db, *, status="pending", attempts=0):
    image = Image(
        filename="queue-test.jpg",
        file_path="data/images/queue-test.jpg",
        processing_status="pending",
    )
    db.add(image)
    db.flush()
    job = ProcessingJob(
        image_id=image.id,
        status=status,
        attempts=attempts,
        max_attempts=3,
        next_attempt_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.flush()
    return image, job


def test_process_endpoint_queues_pending_image(client, db):
    image, job = create_image_and_job(db)
    job.next_attempt_at = datetime.now(timezone.utc)
    db.flush()

    response = client.post("/api/images/process", json={"image_id": str(image.id)})

    assert response.status_code == 202
    assert response.json()["job_status"] == "pending"
    assert response.json()["message"] == "Image queued for background processing"
    assert job.next_attempt_at is None


def test_process_endpoint_rejects_exhausted_job(client, db):
    image, job = create_image_and_job(db, status="failed", attempts=3)

    response = client.post("/api/images/process", json={"image_id": str(image.id)})

    assert response.status_code == 409
    assert "exhausted" in response.json()["detail"]


def test_process_endpoint_returns_not_found_for_unknown_image(client):
    response = client.post(
        "/api/images/process",
        json={"image_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Image not found"
