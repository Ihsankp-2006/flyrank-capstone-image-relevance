import pytest

from app.models.image_metadata import ImageMetadata
from app.models.post import Post
from app.services.guard.mismatch_guard import GuardPolicy, evaluate_image_match


def make_post(title: str, content: str = "") -> Post:
    return Post(title=title, content=content)


def make_metadata(
    subject: str = "Fox",
    category: str = "Wildlife",
    confidence: float = 0.9,
) -> ImageMetadata:
    return ImageMetadata(
        image_id=None,
        subject=subject,
        category=category,
        attributes={},
        caption="Test caption",
        confidence=confidence,
    )


def test_rejects_direct_subject_conflict_with_explanation():
    decision = evaluate_image_match(
        make_post("Fox habitat and behaviour"),
        make_metadata(subject="Wolf"),
        similarity_score=0.8,
    )

    assert decision.status == "rejected"
    assert "focuses on fox" in decision.explanation
    assert "Wolf" in decision.explanation


def test_rejects_category_conflict_with_explanation():
    decision = evaluate_image_match(
        make_post("A guide to software programming"),
        make_metadata(subject="Fox", category="Wildlife"),
        similarity_score=0.8,
    )

    assert decision.status == "rejected"
    assert "conflicts" in decision.explanation
    assert "technology" in decision.explanation


def test_marks_unknown_analysis_for_review():
    decision = evaluate_image_match(
        make_post("Forest ecology"),
        make_metadata(subject="Unknown", category="Wildlife"),
        similarity_score=0.8,
    )

    assert decision.status == "needs_review"
    assert "could not identify" in decision.explanation


@pytest.mark.parametrize(
    "confidence, similarity, policy, expected_fragment",
    [
        (0.0, 0.8, GuardPolicy(), "zero confidence"),
        (0.4, 0.8, GuardPolicy(min_confidence=0.5), "vision confidence"),
        (0.9, 0.2, GuardPolicy(min_similarity=0.3), "similarity"),
    ],
)
def test_applies_only_explicit_policy_thresholds(
    confidence, similarity, policy, expected_fragment
):
    decision = evaluate_image_match(
        make_post("Fox habitat"),
        make_metadata(confidence=confidence),
        similarity_score=similarity,
        policy=policy,
    )

    assert decision.status == "rejected"
    assert expected_fragment in decision.explanation


def test_accepts_non_conflicting_candidate_without_default_threshold():
    decision = evaluate_image_match(
        make_post("Fox habitat"),
        make_metadata(subject="Red fox", category="Wildlife", confidence=0.2),
        similarity_score=-0.4,
    )

    assert decision.status == "accepted"
