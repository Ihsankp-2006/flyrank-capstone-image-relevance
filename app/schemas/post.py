from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    title: str = Field(max_length=255)
    content: str = Field(min_length=1)


class PostResponse(BaseModel):
    id: UUID
    title: str
    content: str
    embedding_model: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
