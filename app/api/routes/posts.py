import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.post import Post
from app.schemas.post import PostCreate, PostResponse
from app.services.post_service import create_post_with_embedding


router = APIRouter(prefix="/posts", tags=["Posts"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate, db: Session = Depends(get_db)):
    """Create a post only when its matching embedding is also persisted."""

    try:
        return create_post_with_embedding(
            db,
            title=payload.title,
            content=payload.content,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception("Post creation failed")
        raise HTTPException(
            status_code=502,
            detail="Unable to create the post embedding",
        ) from error


@router.get("/{post_id}", response_model=PostResponse)
def get_post(post_id: UUID, db: Session = Depends(get_db)):
    post = db.get(Post, post_id)

    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    return post
