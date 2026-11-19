from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.image import Image
from app.models.processing_job import ProcessingJob
from app.services import post_service
from app.services.evaluation_import_service import import_evaluation_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    test_db = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield test_db
    finally:
        test_db.close()
        transaction.rollback()
        connection.close()


def test_evaluation_import_is_offline_and_idempotent(db, tmp_path, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("evaluation import must not generate embeddings")

    monkeypatch.setattr(post_service, "embed_post", fail_if_called)

    kwargs = {
        "manifest_path": PROJECT_ROOT / "data/evaluation/manifest.json",
        "provenance_path": PROJECT_ROOT / "data/evaluation/provenance.json",
        "images_dir": PROJECT_ROOT / "data/evaluation/images",
        "review_path": PROJECT_ROOT / "data/evaluation/review/post_review.csv",
        "storage_dir": tmp_path / "data/images/evaluation",
    }

    first = import_evaluation_dataset(db, **kwargs)
    second = import_evaluation_dataset(db, **kwargs)

    assert len(first.post_ids) == 10
    assert len(first.image_ids) == 40
    assert len(second.skipped_posts) == 10
    assert len(second.skipped_images) == 40
    assert db.scalar(select(func.count()).select_from(ProcessingJob)) == 0
    assert len(db.scalars(select(Image)).all()) == 40
