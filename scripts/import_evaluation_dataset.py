"""Import the evaluation corpus without embeddings or image processing."""

import argparse
from pathlib import Path

from app.core.database import SessionLocal
from app.services.evaluation_import_service import import_evaluation_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/manifest.json",
    )
    parser.add_argument(
        "--provenance",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/provenance.json",
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/images",
    )
    parser.add_argument(
        "--review",
        type=Path,
        default=PROJECT_ROOT / "data/evaluation/review/post_review.csv",
    )
    parser.add_argument(
        "--storage",
        type=Path,
        default=PROJECT_ROOT / "data/images/evaluation",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = import_evaluation_dataset(
            db,
            manifest_path=args.manifest,
            provenance_path=args.provenance,
            images_dir=args.images,
            review_path=args.review,
            storage_dir=args.storage,
        )
    finally:
        db.close()

    print(f"Imported posts: {len(result.post_ids)}")
    print(f"Imported images: {len(result.image_ids)}")
    print(f"Skipped existing posts: {len(result.skipped_posts)}")
    print(f"Skipped existing images: {len(result.skipped_images)}")
    for post_id, database_id in result.post_ids.items():
        print(f"post {post_id}: {database_id}")
    for image_id, database_id in result.image_ids.items():
        print(f"image {image_id}: {database_id}")


if __name__ == "__main__":
    main()
