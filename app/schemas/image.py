
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ImageMetadataResponse(BaseModel):
    subject: str
    category: str
    attributes: dict
    caption: str
    confidence: float
    review_status: str
    embedding_model: str | None

    model_config = ConfigDict(from_attributes=True)


class ImageResponse(BaseModel):
    id: UUID
    filename: str
    file_path: str
    processing_status: str
    created_at: datetime
    metadata: ImageMetadataResponse | None = None

    model_config = ConfigDict(from_attributes=True)


class ImageUploadResponse(BaseModel):
    message: str
    image_id: UUID
    filename: str
    processing_status: str
    job_id: UUID
    job_status: str


class ImageProcessRequest(BaseModel):
    image_id: UUID


class ImageProcessResponse(BaseModel):
    image_id: UUID
    job_id: UUID
    processing_status: str
    job_status: str
    message: str
