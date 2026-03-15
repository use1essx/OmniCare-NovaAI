"""
API v1 Router Registration

This module centralizes all API v1 endpoint routers and provides
a single router for inclusion in the main FastAPI application.
"""

from fastapi import APIRouter

# MERGED: Keep KB from TTSSTT, add questionnaire routes from Host
from src.web.api.v1 import (
    health, 
    security, 
    users, 
    agents, 
    uploads, 
    admin, 
    smartkidpath,
    questionnaires,
    ai_questionnaire,
    questionnaire_assignments,
    questionnaire_scores,
    knowledge_base,
    forms
)

# Create main v1 router
router = APIRouter()

# Include all endpoint routers
router.include_router(health.router, tags=["health"])
router.include_router(security.router, prefix="/security", tags=["security"])
router.include_router(users.router, tags=["users"])  
router.include_router(agents.router, tags=["agents"])
router.include_router(uploads.router, tags=["uploads"])
router.include_router(admin.router, tags=["admin"])
router.include_router(smartkidpath.router, tags=["smartkidpath"])
router.include_router(questionnaires.router, prefix="/questionnaires", tags=["questionnaires"])
router.include_router(ai_questionnaire.router, prefix="/ai-questionnaire", tags=["ai-questionnaire"])
router.include_router(questionnaire_assignments.router, prefix="/questionnaire-assignments", tags=["questionnaire-assignments"])
router.include_router(questionnaire_scores.router, tags=["questionnaire-scores"])
router.include_router(knowledge_base.router, tags=["knowledge-base"])
router.include_router(forms.router, tags=["forms"])

