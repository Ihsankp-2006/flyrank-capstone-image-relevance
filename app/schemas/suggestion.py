from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SuggestionResponse(BaseModel):
    id: UUID
    post_id: UUID
    image_id: UUID
    similarity_score: float
    guard_status: str
    explanation: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewResponse(BaseModel):
    id: UUID
    suggestion_id: UUID
    decision: str
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)
