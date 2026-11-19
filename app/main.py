import logging

from fastapi import FastAPI, HTTPException

from app.core.database import test_connection
from app.api.routes.images import router as images_router
from app.api.routes.posts import router as posts_router
from app.api.routes.suggestions import router as suggestions_router

app = FastAPI(
    title="FlyRank AI Image Matching Engine",
    description="AI-powered image understanding and content matching API",
    version="1.0.0"
)
logger = logging.getLogger(__name__)


app.include_router(images_router, prefix="/api")
app.include_router(posts_router, prefix="/api")
app.include_router(suggestions_router, prefix="/api")


@app.get("/")
def home():
    return {
        "message": "Welcome to FlyRank AI Image Matching Engine",
        "status": "running"
    }


@app.get("/health")
def health_check():
    try:
        test_connection()

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception:
        logger.exception("Health check failed")
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "database": "disconnected"
            }
        )
