"""Run FlyRank retrieval and guard evaluation from a labeled JSON manifest."""

import argparse
import json
import uuid
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.image import Image
from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.services.evaluation_service import (
    calculate_metrics,
    processing_rates,
    validate_manifest,
)
from app.services.guard.mismatch_guard import evaluate_image_match
from app.services.matching.matching_service import find_matching_images


def resolve_manifest_post(db, case: dict) -> Post:
    """Resolve either a database UUID or the manifest's stable post metadata."""

    post_id = str(case["post_id"])
    try:
        post = db.get(Post, uuid.UUID(post_id))
    except ValueError:
        post = None

    if post is not None:
        return post

    title = case.get("title")
    content = case.get("content")
    if not title or not content:
        raise ValueError(
            f"Post {post_id!r} is not a UUID and has no title/content fallback"
        )

    matches = db.scalars(
        select(Post).where(Post.title == title, Post.content == content)
    ).all()
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one database post for manifest case {post_id!r}; "
            f"found {len(matches)}"
        )
    return matches[0]


def run_evaluation(manifest: dict, top_k: int) -> dict:
    failures = validate_manifest(manifest)
    if failures:
        return {"valid": False, "errors": failures}

    db = SessionLocal()
    try:
        evaluated_cases = []
        for case in manifest["posts"]:
            try:
                post = resolve_manifest_post(db, case)
            except ValueError as error:
                return {"valid": False, "errors": [str(error)]}

            matches = find_matching_images(db, post.id, top_k=top_k)
            guard_statuses = {}
            for match in matches:
                metadata = db.scalar(
                    select(ImageMetadata).where(ImageMetadata.image_id == match.image_id)
                )
                guard_statuses[str(match.image_id)] = evaluate_image_match(
                    post, metadata, match.similarity_score
                ).status

            evaluated_cases.append(
                {
                    "relevant_image_ids": case["relevant_image_ids"],
                    "mismatched_image_ids": case.get("mismatched_image_ids", []),
                    "result_image_ids": [str(match.image_id) for match in matches],
                    "guard_status_by_image_id": guard_statuses,
                }
            )

        statuses = db.scalars(select(Image.processing_status)).all()
        return {
            "valid": True,
            "metrics": calculate_metrics(evaluated_cases, top_k=top_k),
            "processing": processing_rates(statuses),
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    if args.top_k < 1:
        parser.error("--top-k must be positive")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(json.dumps(run_evaluation(manifest, args.top_k), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
