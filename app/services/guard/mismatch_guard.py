"""Explainable compatibility checks layered on top of semantic retrieval."""

from dataclasses import dataclass
import re

from app.models.image_metadata import ImageMetadata
from app.models.post import Post


@dataclass(frozen=True)
class GuardPolicy:
    """Optional, evaluation-calibrated thresholds; unset values are not applied."""

    min_similarity: float | None = None
    min_confidence: float | None = None


@dataclass(frozen=True)
class GuardDecision:
    status: str
    explanation: str


# A small, transparent taxonomy catches direct species conflicts such as fox vs.
# wolf without pretending that a lexical heuristic understands every domain.
SUBJECT_GROUPS = {
    "animal": {
        "bear", "cat", "deer", "dog", "elephant", "fox", "giraffe",
        "horse", "lion", "tiger", "wolf", "zebra",
    },
}

CATEGORY_SIGNALS = {
    "wildlife": {"animal", "animals", "wildlife", "habitat", "species"},
    "food": {"bake", "cooking", "dish", "food", "meal", "recipe"},
    "technology": {"ai", "computer", "programming", "software", "technology"},
    "travel": {"destination", "journey", "tourism", "travel", "trip"},
}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _category_key(category: str) -> str | None:
    category_tokens = _tokens(category)
    for key in CATEGORY_SIGNALS:
        if key in category_tokens:
            return key
    return None


def _conflicting_subject(post_tokens: set[str], subject_tokens: set[str]) -> str | None:
    for subjects in SUBJECT_GROUPS.values():
        requested = subjects & post_tokens
        detected = subjects & subject_tokens
        if requested and detected and requested.isdisjoint(detected):
            return sorted(requested)[0]
    return None


def evaluate_image_match(
    post: Post,
    metadata: ImageMetadata,
    similarity_score: float,
    *,
    policy: GuardPolicy | None = None,
) -> GuardDecision:
    """Return an explainable compatibility decision for one retrieved image.

    This is intentionally independent of pgvector retrieval. Thresholds only
    apply when explicitly supplied from a labeled-evaluation calibration.
    """

    policy = policy or GuardPolicy()
    post_tokens = _tokens(f"{post.title} {post.content}")
    subject_tokens = _tokens(metadata.subject)

    if metadata.confidence <= 0:
        return GuardDecision(
            status="rejected",
            explanation="Rejected because the vision analysis reported zero confidence.",
        )

    if (
        policy.min_confidence is not None
        and metadata.confidence < policy.min_confidence
    ):
        return GuardDecision(
            status="rejected",
            explanation=(
                f"Rejected because vision confidence {metadata.confidence:.2f} is below "
                f"the configured minimum of {policy.min_confidence:.2f}."
            ),
        )

    if (
        policy.min_similarity is not None
        and similarity_score < policy.min_similarity
    ):
        return GuardDecision(
            status="rejected",
            explanation=(
                f"Rejected because similarity {similarity_score:.4f} is below the "
                f"configured minimum of {policy.min_similarity:.4f}."
            ),
        )

    requested_subject = _conflicting_subject(post_tokens, subject_tokens)
    if requested_subject is not None:
        return GuardDecision(
            status="rejected",
            explanation=(
                f"Rejected because the post focuses on {requested_subject}, while "
                f"the image subject is {metadata.subject}."
            ),
        )

    candidate_category = _category_key(metadata.category)
    if candidate_category is not None:
        competing_categories = [
            category
            for category, signals in CATEGORY_SIGNALS.items()
            if category != candidate_category and post_tokens & signals
        ]
        if competing_categories:
            return GuardDecision(
                status="rejected",
                explanation=(
                    f"Rejected because image category {metadata.category} conflicts "
                    f"with post signals for {competing_categories[0]}."
                ),
            )

    uncertain_terms = {"unknown", "unclear", "uncertain"}
    if subject_tokens & uncertain_terms or _tokens(metadata.category) & uncertain_terms:
        return GuardDecision(
            status="needs_review",
            explanation=(
                "Needs review because the vision analysis could not identify a clear "
                "subject or category."
            ),
        )

    return GuardDecision(
        status="accepted",
        explanation=(
            f"Accepted for review: image subject {metadata.subject} and category "
            f"{metadata.category} show no detected conflict with the post; vision "
            f"confidence is {metadata.confidence:.2f}."
        ),
    )
