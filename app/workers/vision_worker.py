
import logging
import time

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select

from app.core.database import SessionLocal
from app.models.image import Image
from app.models.processing_job import ProcessingJob
from app.services.vision.pipeline_service import process_image


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5
STALE_JOB_TIMEOUT = 30


def recover_stale_jobs():
    """Recover jobs left processing after a worker interruption."""

    db = SessionLocal()

    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(
            minutes=STALE_JOB_TIMEOUT
        )

        statement = (
            select(ProcessingJob)
            .where(
                ProcessingJob.status == "processing",
                (
                    (ProcessingJob.started_at.is_(None))
                    | (ProcessingJob.started_at < cutoff_time)
                )
            )
            .with_for_update(skip_locked=True)
        )

        stale_jobs = db.scalars(statement).all()

        for job in stale_jobs:
            image = db.get(Image, job.image_id)

            if job.attempts >= job.max_attempts:
                job.status = "failed"
                job.next_attempt_at = None

                if image:
                    image.processing_status = "failed"
            else:
                job.status = "pending"
                job.next_attempt_at = datetime.now(timezone.utc)

                if image:
                    image.processing_status = "pending"

            job.error_message = "Recovered after worker interruption"
            job.completed_at = datetime.now(timezone.utc)

            logger.warning("Recovered stale job: %s", job.id)

        db.commit()

        logger.info("Stale jobs recovered: %s", len(stale_jobs))

    except Exception:
        db.rollback()
        logger.exception("Failed to recover stale jobs")

    finally:
        db.close()


def claim_next_job():
    """Atomically claim one pending job."""

    db = SessionLocal()

    try:
        statement = (
            select(ProcessingJob)
            .where(
                ProcessingJob.status == "pending",
                or_(
                    ProcessingJob.next_attempt_at.is_(None),
                    ProcessingJob.next_attempt_at <= datetime.now(timezone.utc),
                ),
            )
            .order_by(ProcessingJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )

        job = db.scalars(statement).first()

        if job is None:
            return None

        image = db.get(Image, job.image_id)

        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.error_message = "Maximum attempts reached"
            job.completed_at = datetime.now(timezone.utc)
            job.next_attempt_at = None

            if image:
                image.processing_status = "failed"

            db.commit()
            logger.warning("Finalized exhausted job: %s", job.id)
            return None

        if image is None:
            job.status = "failed"
            job.error_message = "Image record not found"
            job.completed_at = datetime.now(timezone.utc)
            job.next_attempt_at = None
            db.commit()
            return None

        job.status = "processing"
        job.attempts += 1
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = None
        job.next_attempt_at = None
        job.error_message = None

        image.processing_status = "processing"

        image_id = job.image_id
        job_id = job.id

        db.commit()

        logger.info("Claimed job: %s", job_id)

        return image_id, job_id

    except Exception:
        db.rollback()
        logger.exception("Failed to claim a job")
        return None

    finally:
        db.close()


def process_pending_jobs():
    claimed_job = claim_next_job()

    if claimed_job is None:
        return False

    image_id, job_id = claimed_job

    db = SessionLocal()

    try:
        logger.info("Processing image: %s", image_id)

        result = process_image(
            db=db,
            image_id=image_id,
            job_id=job_id,
            already_claimed=True
        )

        logger.info("Processing result: %s", result)

        return True

    except Exception:
        logger.exception("Unexpected processing error")
        return False

    finally:
        db.close()


def start_worker():
    logger.info("FlyRank Vision Worker started")

    recover_stale_jobs()

    try:
        while True:
            job_found = process_pending_jobs()

            if not job_found:
                time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Vision Worker stopped")


if __name__ == "__main__":
    start_worker()
