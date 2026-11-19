
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.image import Image
from app.models.processing_job import ProcessingJob
from app.workers import vision_worker


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
def worker_session(db, monkeypatch):
    # Give the worker a session using the test transaction.
    def create_session():
        return Session(
            bind=db.connection(),
            join_transaction_mode="create_savepoint"
        )

    monkeypatch.setattr(
        vision_worker,
        "SessionLocal",
        create_session
    )


@pytest.fixture
def sample_job(db):
    image = Image(
        filename="worker-test.jpg",
        file_path="data/images/worker-test.jpg",
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


def test_claim_next_job(db, sample_job, worker_session):
    image, job = sample_job

    claimed = vision_worker.claim_next_job()

    assert claimed == (image.id, job.id)

    db.refresh(job)
    db.refresh(image)

    assert job.status == "processing"
    assert job.attempts == 1
    assert image.processing_status == "processing"


def test_worker_does_not_claim_same_job_twice(
    db, sample_job, worker_session
):
    image, job = sample_job

    first_claim = vision_worker.claim_next_job()
    second_claim = vision_worker.claim_next_job()

    assert first_claim == (image.id, job.id)
    assert second_claim is None

    db.refresh(job)

    assert job.attempts == 1


def test_recover_stale_job(
    db, sample_job, worker_session
):
    image, job = sample_job

    job.status = "processing"
    job.attempts = 1
    job.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    image.processing_status = "processing"

    db.flush()

    vision_worker.recover_stale_jobs()

    db.refresh(job)
    db.refresh(image)

    assert job.status == "pending"
    assert image.processing_status == "pending"
    assert job.error_message == "Recovered after worker interruption"


def test_stale_job_fails_after_max_attempts(
    db, sample_job, worker_session
):
    image, job = sample_job

    job.status = "processing"
    job.attempts = job.max_attempts
    job.started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    image.processing_status = "processing"

    db.flush()

    vision_worker.recover_stale_jobs()

    db.refresh(job)
    db.refresh(image)

    assert job.status == "failed"
    assert image.processing_status == "failed"


def test_recover_job_with_missing_start_time(
    db, sample_job, worker_session
):
    image, job = sample_job
    job.status = "processing"
    job.attempts = 1
    job.started_at = None
    image.processing_status = "processing"
    db.flush()

    vision_worker.recover_stale_jobs()

    db.refresh(job)
    db.refresh(image)

    assert job.status == "pending"
    assert image.processing_status == "pending"


def test_claim_finalizes_exhausted_pending_job(
    db, sample_job, worker_session
):
    image, job = sample_job
    job.attempts = job.max_attempts
    db.flush()

    assert vision_worker.claim_next_job() is None

    db.refresh(job)
    db.refresh(image)

    assert job.status == "failed"
    assert image.processing_status == "failed"


def test_worker_does_not_claim_job_before_retry_time(
    db, sample_job, worker_session
):
    image, job = sample_job
    job.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=1)
    db.flush()

    assert vision_worker.claim_next_job() is None

    db.refresh(job)
    assert job.status == "pending"
    assert job.attempts == 0

