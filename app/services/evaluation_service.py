"""Reproducible metrics for a labeled FlyRank evaluation corpus."""

from collections.abc import Iterable


def validate_manifest(manifest: dict) -> list[str]:
    """Return human-readable corpus requirement failures, if any."""

    failures: list[str] = []
    if len(manifest.get("image_ids", [])) < 40:
        failures.append("Evaluation manifest requires at least 40 image_ids")
    if len(set(manifest.get("categories", []))) < 4:
        failures.append("Evaluation manifest requires at least 4 categories")
    if len(manifest.get("posts", [])) < 10:
        failures.append("Evaluation manifest requires at least 10 post cases")
    if manifest.get("labels_verified") is not True:
        failures.append(
            "Evaluation manifest labels must be human-verified before evaluation"
        )
    return failures


def calculate_metrics(cases: Iterable[dict], *, top_k: int) -> dict:
    """Calculate retrieval and guard quality from labeled evaluation outcomes.

    Each case contains ``relevant_image_ids``, ranked ``result_image_ids``, and
    optional ``guard_status_by_image_id`` values for returned known candidates.
    """

    cases = list(cases)
    top1_hits = 0
    topk_hits = 0
    mismatch_total = 0
    mismatch_rejected = 0
    false_acceptances = 0
    false_rejections = 0
    relevant_total = 0

    for case in cases:
        relevant = set(case.get("relevant_image_ids", []))
        mismatched = set(case.get("mismatched_image_ids", []))
        ranked = case.get("result_image_ids", [])[:top_k]
        statuses = case.get("guard_status_by_image_id", {})

        relevant_total += len(relevant)
        if ranked and ranked[0] in relevant:
            top1_hits += 1
        if relevant.intersection(ranked):
            topk_hits += 1

        for image_id in mismatched.intersection(ranked):
            mismatch_total += 1
            if statuses.get(image_id) == "rejected":
                mismatch_rejected += 1
            if statuses.get(image_id) == "accepted":
                false_acceptances += 1

        for image_id in relevant.intersection(ranked):
            if statuses.get(image_id) == "rejected":
                false_rejections += 1

    case_count = len(cases)
    return {
        "case_count": case_count,
        "top_1_precision": top1_hits / case_count if case_count else None,
        "top_k_relevance": topk_hits / case_count if case_count else None,
        "mismatch_rejection_rate": (
            mismatch_rejected / mismatch_total if mismatch_total else None
        ),
        "false_acceptances": false_acceptances,
        "false_rejections": false_rejections,
        "evaluated_mismatch_candidates": mismatch_total,
        "evaluated_relevant_candidates": relevant_total,
    }


def processing_rates(statuses: Iterable[str]) -> dict:
    statuses = list(statuses)
    total = len(statuses)
    completed = sum(status == "completed" for status in statuses)
    failed = sum(status == "failed" for status in statuses)
    return {
        "image_count": total,
        "processing_success_rate": completed / total if total else None,
        "processing_failure_rate": failed / total if total else None,
    }
