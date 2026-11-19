"""Offline import of the approved evaluation corpus without AI calls."""

import csv
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.image import Image
from app.models.post import Post
from app.services.image_service import register_offline_image
from app.services.post_service import create_post_offline


ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024


@dataclass(frozen=True)
class EvaluationImportResult:
    post_ids: dict[str, str]
    image_ids: dict[str, str]
    skipped_posts: tuple[str, ...]
    skipped_images: tuple[str, ...]


def _validate_image_bytes(content: bytes, suffix: str) -> None:
    if not content or len(content) > MAX_FILE_SIZE:
        raise ValueError("Evaluation image is empty or exceeds the 5 MB limit")

    signatures = {
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
    }
    if not signatures.get(suffix, False):
        raise ValueError(f"Invalid evaluation image content for {suffix}")


def _load_review_mappings(review_path: Path, image_ids: set[str]) -> None:
    with review_path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))

    if len(rows) != 10:
        raise ValueError("Expected exactly 10 approved post review rows")

    for row in rows:
        if row.get("human_verified", "").lower() != "true":
            raise ValueError(f"Post review is not approved: {row.get('post_id')}")
        if row.get("correct_image_id") not in image_ids:
            raise ValueError(
                f"Post review references unknown image: {row.get('correct_image_id')}"
            )


def _find_existing_post(db: Session, title: str, content: str) -> Post | None:
    matches = db.scalars(
        select(Post).where(
            Post.title == title,
            Post.content == content,
        )
    ).all()
    if len(matches) > 1:
        raise ValueError(f"Duplicate evaluation post content found: {title}")
    return matches[0] if matches else None


def import_evaluation_dataset(
    db: Session,
    *,
    manifest_path: Path,
    provenance_path: Path,
    images_dir: Path,
    review_path: Path,
    storage_dir: Path,
) -> EvaluationImportResult:
    """Import evaluation posts and images idempotently without processing jobs."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    project_root = manifest_path.resolve().parents[2]
    provenance_by_id = {
        record["image_id"]: record for record in provenance["images"]
    }
    manifest_image_ids = set(manifest["image_ids"])

    if set(provenance_by_id) != manifest_image_ids:
        raise ValueError("Manifest and provenance image IDs do not match")
    _load_review_mappings(review_path, manifest_image_ids)

    post_ids: dict[str, str] = {}
    skipped_posts: list[str] = []
    for case in manifest["posts"]:
        post = _find_existing_post(db, case["title"], case["content"])
        if post is None:
            post = create_post_offline(
                db,
                title=case["title"],
                content=case["content"],
            )
        else:
            skipped_posts.append(case["post_id"])
        post_ids[case["post_id"]] = str(post.id)

    storage_dir.mkdir(parents=True, exist_ok=True)
    image_ids: dict[str, str] = {}
    skipped_images: list[str] = []
    for image_id in manifest["image_ids"]:
        record = provenance_by_id[image_id]
        source_path = images_dir / record["filename"]
        if not source_path.is_file():
            raise FileNotFoundError(f"Evaluation image not found: {source_path}")

        content = source_path.read_bytes()
        suffix = source_path.suffix.lower()
        _validate_image_bytes(content, suffix)
        if hashlib.sha256(content).hexdigest() != record["sha256"]:
            raise ValueError(f"Checksum mismatch for evaluation image: {image_id}")

        destination_name = f"{image_id}{suffix}"
        destination_path = storage_dir / destination_name
        if not destination_path.exists():
            shutil.copy2(source_path, destination_path)

        try:
            relative_path = destination_path.resolve().relative_to(project_root)
            file_path = relative_path.as_posix()
        except ValueError:
            file_path = f"data/images/evaluation/{destination_name}"
        existing = db.scalar(
            select(Image).where(Image.file_path == file_path)
        )
        image = register_offline_image(
            db,
            filename=destination_name,
            file_path=file_path,
        )
        if existing is not None:
            skipped_images.append(image_id)
        image_ids[image_id] = str(image.id)

    return EvaluationImportResult(
        post_ids=post_ids,
        image_ids=image_ids,
        skipped_posts=tuple(skipped_posts),
        skipped_images=tuple(skipped_images),
    )
