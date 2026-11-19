from app.services.evaluation_service import (
    calculate_metrics,
    processing_rates,
    validate_manifest,
)


def test_manifest_validation_reports_capstone_minimums():
    failures = validate_manifest({"image_ids": [], "categories": [], "posts": []})

    assert len(failures) == 4
    assert "human-verified" in failures[-1]


def test_calculates_retrieval_and_guard_metrics():
    metrics = calculate_metrics(
        [
            {
                "relevant_image_ids": ["fox"],
                "mismatched_image_ids": ["wolf"],
                "result_image_ids": ["fox", "wolf"],
                "guard_status_by_image_id": {"fox": "accepted", "wolf": "rejected"},
            },
            {
                "relevant_image_ids": ["recipe"],
                "mismatched_image_ids": ["laptop"],
                "result_image_ids": ["laptop", "recipe"],
                "guard_status_by_image_id": {"laptop": "accepted", "recipe": "rejected"},
            },
        ],
        top_k=2,
    )

    assert metrics["top_1_precision"] == 0.5
    assert metrics["top_k_relevance"] == 1.0
    assert metrics["mismatch_rejection_rate"] == 0.5
    assert metrics["false_acceptances"] == 1
    assert metrics["false_rejections"] == 1


def test_processing_rates():
    rates = processing_rates(["completed", "completed", "failed", "pending"])

    assert rates["processing_success_rate"] == 0.5
    assert rates["processing_failure_rate"] == 0.25
