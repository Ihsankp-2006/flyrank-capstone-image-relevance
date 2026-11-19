
from unittest.mock import MagicMock

import pytest

from app.services.vision import vision_service
from app.services.vision.vision_service import (
    VisionAnalysis,
    analyze_image
)


@pytest.fixture
def sample_analysis():
    return VisionAnalysis(
        subject="Fox",
        category="Wildlife",
        attributes={
            "color": "Orange",
            "environment": "Forest"
        },
        caption="An orange fox standing in a forest.",
        confidence=0.95
    )


def test_analyze_image_success(monkeypatch, sample_analysis):
    # Provide a fake API key
    monkeypatch.setattr(
        vision_service.settings,
        "GEMINI_API_KEY",
        "test-api-key"
    )

    # Mock Gemini response
    mock_response = MagicMock()
    mock_response.parsed = sample_analysis

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    monkeypatch.setattr(
        vision_service.genai,
        "Client",
        lambda **kwargs: mock_client
    )

    result = analyze_image(
        image_bytes=b"fake-image-data",
        mime_type="image/jpeg"
    )

    assert result.subject == "Fox"
    assert result.category == "Wildlife"
    assert result.confidence == 0.95

    mock_client.models.generate_content.assert_called_once()


def test_missing_api_key(monkeypatch):
    monkeypatch.setattr(
        vision_service.settings,
        "GEMINI_API_KEY",
        None
    )

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        analyze_image(
            image_bytes=b"fake-image-data",
            mime_type="image/jpeg"
        )


def test_empty_image():
    with pytest.raises(ValueError, match="empty"):
        analyze_image(
            image_bytes=b"",
            mime_type="image/jpeg"
        )


def test_unsupported_image_type():
    with pytest.raises(ValueError, match="Unsupported"):
        analyze_image(
            image_bytes=b"fake-image-data",
            mime_type="image/gif"
        )


def test_invalid_confidence():
    with pytest.raises(ValueError):
        VisionAnalysis(
            subject="Fox",
            category="Wildlife",
            attributes={},
            caption="A fox",
            confidence=1.5
        )
