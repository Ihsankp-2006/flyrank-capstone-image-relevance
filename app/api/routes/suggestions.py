from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.suggestion import Suggestion
from app.schemas.suggestion import ReviewResponse, SuggestionResponse
from app.services.matching.matching_service import (
    MissingPostEmbeddingError,
    PostNotFoundError,
)
from app.services.matching.suggestion_service import (
    generate_suggestions,
    list_post_suggestions,
    review_suggestion,
)


router = APIRouter(tags=["Suggestions"])


@router.post(
    "/posts/{post_id}/suggestions",
    response_model=list[SuggestionResponse],
    status_code=status.HTTP_201_CREATED,
)
def create_suggestions(
    post_id: UUID,
    top_k: int = Query(default=5, ge=1),
    db: Session = Depends(get_db),
):
    try:
        return generate_suggestions(db, post_id, top_k=top_k)
    except PostNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except MissingPostEmbeddingError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/posts/{post_id}/suggestions", response_model=list[SuggestionResponse])
def get_post_suggestions(post_id: UUID, db: Session = Depends(get_db)):
    return list_post_suggestions(db, post_id)


@router.get("/suggestions/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion(suggestion_id: UUID, db: Session = Depends(get_db)):
    suggestion = db.get(Suggestion, suggestion_id)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return suggestion


@router.post(
    "/suggestions/{suggestion_id}/approve",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def approve_suggestion(suggestion_id: UUID, db: Session = Depends(get_db)):
    try:
        return review_suggestion(db, suggestion_id, "approved")
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/suggestions/{suggestion_id}/reject",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def reject_suggestion(suggestion_id: UUID, db: Session = Depends(get_db)):
    try:
        return review_suggestion(db, suggestion_id, "rejected")
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
