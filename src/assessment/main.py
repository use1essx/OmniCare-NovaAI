"""
Assessment Server
FastAPI application for video analysis and assessment
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    logger.info("🚀 Assessment Server starting...")
    logger.info("📍 Assessment service available at http://localhost:8002")
    yield
    logger.info("Shutting down Assessment Server...")


# Create FastAPI app
app = FastAPI(
    lifespan=lifespan,
    title="Assessment Server",
    description="Video analysis and assessment service",
    version="1.0.0"
)

# Add CORS middleware
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8000,http://localhost:8001,http://localhost:8002"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    import time
    return {
        "status": "healthy",
        "service": "assessment",
        "timestamp": time.time()
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Assessment Server",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/api/assess/video")
async def assess_video(data: dict):
    """
    Assess video data
    Placeholder for video assessment logic
    """
    return {
        "success": True,
        "message": "Video assessment endpoint - implementation pending",
        "data": data
    }


@app.post("/api/assess/session/{session_id}")
async def assess_session(session_id: str):
    """
    Assess a recorded session
    Placeholder for session assessment logic
    """
    return {
        "success": True,
        "session_id": session_id,
        "message": "Session assessment endpoint - implementation pending"
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.assessment.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True
    )
