"""
Healthcare AI V2 Admin Routes
Main router that combines all admin routes
"""

from fastapi import APIRouter
from .pages import router as pages_router
from .api import router as api_router
from .tts_routes import tts_router

# Create main admin router
admin_router = APIRouter(prefix="/admin", tags=["admin"])

# Include sub-routers
admin_router.include_router(pages_router)
admin_router.include_router(api_router)
admin_router.include_router(tts_router)

# Export the main router
__all__ = ["admin_router"]
