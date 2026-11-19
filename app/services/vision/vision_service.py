
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from app.core.database import settings


# Gemini model selected for image understanding
VISION_MODEL = "gemini-3.1-flash-lite"


class VisionConfigurationError(ValueError):
    """A local configuration problem that cannot succeed on retry."""


class InvalidImageInputError(ValueError):
    """An uploaded file cannot be processed by the supported vision flow."""


# Expected structured output from Gemini
class VisionAnalysis(BaseModel):
    subject: str = Field(
        description="Main subject visible in the image"
    )

    category: str = Field(
        description="General category of the image"
    )

    attributes: dict[str, str] = Field(
        description="Important visual attributes of the image"
    )

    caption: str = Field(
        description="Short and descriptive image caption"
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Estimated confidence in the analysis, from 0 to 1"
    )


def analyze_image(
    image_bytes: bytes,
    mime_type: str
) -> VisionAnalysis:
    """
    Analyze an image and return structured information about it.
    """
    if not settings.GEMINI_API_KEY:
        raise VisionConfigurationError("GEMINI_API_KEY is missing from .env")

    if not image_bytes:
        raise InvalidImageInputError("Image data is empty")

    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp"
    }

    if mime_type not in allowed_types:
        raise InvalidImageInputError("Unsupported image MIME type")

    client = genai.Client(
        api_key=settings.GEMINI_API_KEY
    )

    prompt = """
    Analyze the provided image carefully.

    Identify:
    1. The main subject.
    2. Its general category.
    3. Important visual attributes.
    4. A clear and concise caption.
    5. Your estimated confidence between 0 and 1.

    Do not invent details that cannot be identified.
    If the subject is unclear, state that uncertainty.
    Return only the requested structured information.
    """

    image_part = types.Part.from_bytes(
        data=image_bytes,
        mime_type=mime_type
    )

    response = client.models.generate_content(
        model=VISION_MODEL,
        contents=[prompt, image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VisionAnalysis
        )
    )

    if response.parsed is None:
        raise ValueError("Gemini returned no structured analysis")

    if isinstance(response.parsed, VisionAnalysis):
        return response.parsed

    return VisionAnalysis.model_validate(response.parsed)
