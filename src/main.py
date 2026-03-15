"""
Healthcare AI V2 - Main Application
FastAPI application with comprehensive setup and lifecycle management
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.core.config import settings
from src.core.logging import setup_logging
from src.core.exceptions import HealthcareAIException
from src.security.middleware import (
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    EnhancedCORSMiddleware,
    RequestSizeMiddleware,
    SecurityAuditMiddleware
)
from src.database.connection import init_database, close_database
from src.web.api.v1 import health
from src.web.api.v1 import security as security_routes
from src.web.auth import routes as auth_routes
from src.web.live2d import live2d_router
from src.web.admin import data_routes
# Security monitoring
from src.security.monitoring import initialize_security_monitor
from src.security.events import initialize_security_events

# Setup logging first
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("Starting Healthcare AI V2 application...")
    
    try:
        # Initialize database connections (skip if not available)
        try:
            await init_database()
            logger.info("Database connections initialized")
            
            # Seed demo users if enabled
            if settings.seed_demo_data:
                try:
                    from src.database.seed_demo_users import seed_demo_users, ensure_super_admin, seed_assessment_rules, seed_kb_categories, seed_kb_documents
                    
                    # Ensure super admin exists first
                    await ensure_super_admin()
                    
                    # Seed demo users
                    seeded = await seed_demo_users(force=False)
                    if seeded:
                        logger.info("✅ Demo users seeded successfully")
                    else:
                        logger.info("✅ Demo users already exist, skipping seed")
                    
                    # Seed assessment rules for movement analysis
                    rules_seeded = await seed_assessment_rules()
                    if rules_seeded:
                        logger.info("✅ Assessment rules seeded successfully")
                    else:
                        logger.info("✅ Assessment rules already exist, skipping seed")
                    
                    # KB seeding disabled - user wants to fix KB system first
                    # Uncomment below to re-enable auto-seeding on startup
                    
                    # # Seed KB categories (Age Groups, Categories, Topics)
                    # kb_seeded = await seed_kb_categories()
                    # if kb_seeded:
                    #     logger.info("✅ KB categories seeded successfully")
                    # else:
                    #     logger.info("✅ KB categories already exist, skipping seed")
                    # 
                    # # Seed KB documents (Elderly services documents)
                    # kb_docs_seeded = await seed_kb_documents()
                    # if kb_docs_seeded:
                    #     logger.info("✅ KB documents seeded successfully")
                    # else:
                    #     logger.info("✅ KB documents already exist or no new documents to seed")
                    
                    logger.info("ℹ️  KB auto-seeding is disabled. Use manual scripts to seed KB data.")
                        
                except Exception as seed_error:
                    logger.warning(f"Demo user seeding failed, continuing: {seed_error}")
        except Exception as db_error:
            logger.warning(f"Database initialization failed, continuing without database: {db_error}")
        
        # Initialize security systems
        try:
            await initialize_security_monitor()
            logger.info("Security monitor initialized")
        except Exception as sec_error:
            logger.warning(f"Security monitor initialization failed: {sec_error}")
        
        try:
            await initialize_security_events()
            logger.info("Security event tracker initialized")
        except Exception as event_error:
            logger.warning(f"Security event tracker initialization failed: {event_error}")
        
        logger.info("Healthcare AI V2 started successfully")
        
        yield  # Application runs here
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    finally:
        # Shutdown
        logger.info("Shutting down Healthcare AI V2...")
        
        try:
            # Close database connections
            await close_database()
            logger.info("Database connections closed")
            
            # Cleanup other services
            # await close_redis()
            # await stop_background_tasks()
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info("Healthcare AI V2 shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Healthcare AI System for Hong Kong with Multi-Agent Architecture",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
    lifespan=lifespan,
)

# =============================================================================
# SECURITY MIDDLEWARE STACK (Order matters - applied in reverse order)
# =============================================================================

# 1. Security Audit Middleware (first to catch all requests)
app.add_middleware(SecurityAuditMiddleware)

# 2. Request Size Limiting (prevent DoS attacks)
app.add_middleware(RequestSizeMiddleware, max_size=150 * 1024 * 1024)  # 150MB limit for video uploads

# 3. Enhanced Request Logging
app.add_middleware(RequestLoggingMiddleware)

# 4. Security Headers (comprehensive security headers)
app.add_middleware(SecurityHeadersMiddleware, enable_hsts=settings.is_production)

# 5. Enhanced CORS (stricter than default)
app.add_middleware(
    EnhancedCORSMiddleware,
    allowed_origins=settings.cors_origins,
    allowed_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]
)

# 6. Trusted Host Middleware (production only)
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.healthcare-ai.com", "localhost", "127.0.0.1"]
    )

# =============================================================================
# EXCEPTION HANDLERS
# =============================================================================

@app.exception_handler(HealthcareAIException)
async def healthcare_ai_exception_handler(request: Request, exc: HealthcareAIException):
    """Handle custom Healthcare AI exceptions"""
    logger.error(
        f"Healthcare AI exception: {exc.detail}",
        extra={
            'error_type': exc.error_type,
            'status_code': exc.status_code,
            'endpoint': str(request.url),
            'method': request.method
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "error_type": exc.error_type,
            "timestamp": exc.timestamp.isoformat(),
            "request_id": getattr(request.state, 'request_id', None)
        }
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Resource not found",
            "error_type": "not_found",
            "path": str(request.url.path)
        }
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """Handle 500 errors"""
    logger.error(
        f"Internal server error: {str(exc)}",
        extra={
            'endpoint': str(request.url),
            'method': request.method
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "error_type": "internal_error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )

# =============================================================================
# STATIC FILES AND TEMPLATES
# =============================================================================

# Mount static files for admin interface
if settings.enable_admin_interface:
    # Get the correct path for static files
    from pathlib import Path
    static_dir = Path(__file__).parent / "web" / "admin" / "static"
    template_dir = Path(__file__).parent / "web" / "admin" / "templates"
    
    if static_dir.exists():
        # Mount to /static for general access (legacy support)
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        # Also mount to /admin/static to match some relative paths if they exist
        app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin_static")
        
        # Setup Jinja2 templates
        if template_dir.exists():
            templates = Jinja2Templates(directory=str(template_dir))
    else:
        logger.warning(f"Static directory not found: {static_dir}")

# =============================================================================
# ROUTES
# =============================================================================

# Health check endpoints
app.include_router(
    health.router,
    prefix=settings.api_v1_prefix,
    tags=["health"]
)

# Authentication endpoints
app.include_router(
    auth_routes.router,
    prefix=settings.api_v1_prefix,
    tags=["authentication"]
)

# Admin data management endpoints
app.include_router(
    data_routes.data_router,
    prefix=settings.api_v1_prefix,
    tags=["admin-data"]
)

# Security monitoring endpoints
app.include_router(
    security_routes.router,
    prefix=f"{settings.api_v1_prefix}/security",
    tags=["security"]
)

# Additional API endpoints (after app setup - FastAPI pattern)
# MERGED: Keep KB from TTSSTT, Questionnaire from Host, remove unused (adk_tools, hk_data, function_calling_admin)
from src.web.api.v1 import users, agents, uploads, live2d as live2d_api, social_worker_dashboard, questionnaires, ai_questionnaire, organizations, smartkidpath, knowledge_base, forms, budget  # noqa: E402

# User management endpoints
app.include_router(
    users.router,
    prefix=settings.api_v1_prefix,
    tags=["users"]
)

# Organization management endpoints
app.include_router(
    organizations.router,
    prefix=settings.api_v1_prefix,
    tags=["organizations"]
)

# Agent system endpoints
app.include_router(
    agents.router,
    prefix=settings.api_v1_prefix,
    tags=["agents"]
)

# OmniCare Screener endpoint
app.include_router(
    smartkidpath.router,
    prefix=settings.api_v1_prefix,
    tags=["smartkidpath"]
)

# Social Worker Dashboard endpoints (legacy)
app.include_router(
    social_worker_dashboard.router,
    prefix=settings.api_v1_prefix,
    tags=["social-worker", "dashboard"]
)

# Social Worker Hub API (new - case management, alerts, analytics)
from src.web.api.v1.social_worker_hub import router as sw_hub_router  # noqa: E402
app.include_router(
    sw_hub_router,
    prefix=settings.api_v1_prefix,
    tags=["social-worker-hub"]
)

# Questionnaire Management endpoints
app.include_router(
    questionnaires.router,
    prefix=f"{settings.api_v1_prefix}/questionnaires",
    tags=["questionnaires", "screening"]
)

# AI Questionnaire endpoints  
app.include_router(
    ai_questionnaire.router,
    prefix=f"{settings.api_v1_prefix}/ai-questionnaire",
    tags=["ai-questionnaire", "file-upload"]
)

# Questionnaire Assignment endpoints (for Live2D chat integration)
from src.web.api.v1.questionnaire_assignments import router as questionnaire_assignments_router  # noqa: E402
app.include_router(
    questionnaire_assignments_router,
    prefix=f"{settings.api_v1_prefix}/questionnaire-assignments",
    tags=["questionnaire-assignments", "live2d"]
)

# Questionnaire Scores endpoints (for viewing user scores)
from src.web.api.v1.questionnaire_scores import router as questionnaire_scores_router  # noqa: E402
app.include_router(
    questionnaire_scores_router,
    prefix=f"{settings.api_v1_prefix}/questionnaire-scores",
    tags=["questionnaire-scores", "analytics"]
)

# File upload endpoints
app.include_router(
    uploads.router,
    prefix=settings.api_v1_prefix,
    tags=["uploads"]
)

# Knowledge base endpoints (TTSSTT - KB/RAG system)
app.include_router(
    knowledge_base.router,
    prefix=settings.api_v1_prefix,
    tags=["knowledge-base"]
)

# Form download endpoints (JWT-based secure downloads)
app.include_router(
    forms.router,
    prefix=settings.api_v1_prefix,
    tags=["forms"]
)

# Budget monitoring endpoints (Admin only)
app.include_router(
    budget.router,
    prefix=settings.api_v1_prefix,
    tags=["budget"]
)


# Administrative endpoints (OLD - replaced by super_admin_simple.py)
# app.include_router(
#     admin.router,
#     prefix=settings.api_v1_prefix,
#     tags=["admin"]
# )

# pgAdmin Integration endpoints
from src.web.api.v1.pgadmin import router as pgadmin_router  # noqa: E402
app.include_router(
    pgadmin_router,
    prefix=settings.api_v1_prefix,
    tags=["pgadmin"]
)

# Live2D API integration endpoints
app.include_router(
    live2d_api.router,
    prefix=settings.api_v1_prefix,
    tags=["live2d-api"]
)

# Live2D main interface endpoints
app.include_router(
    live2d_router,
    tags=["live2d"]
)

# Custom Live AI (Emotion Tracking) Integration
try:
    from src.custom_live_ai.main import app as custom_live_ai_app
    # Mount under /custom-live-ai
    app.mount("/custom-live-ai", custom_live_ai_app)
    logger.info("✅ Mounted Custom Live AI at /custom-live-ai")
except Exception as e:
    logger.warning(f"Failed to mount Custom Live AI: {e}")

# =============================================================================
# Movement Analysis Module Routes
# =============================================================================
try:
    from src.movement_analysis.routes import router as movement_analysis_api_router, admin_router as movement_analysis_admin_router
    from src.web.movement_analysis import assessment_page_router as movement_analysis_page_router
    
    # Movement Analysis API endpoints
    app.include_router(
        movement_analysis_api_router,
        prefix=settings.api_v1_prefix,
        tags=["movement-analysis"]
    )
    
    # Movement Analysis Admin API endpoints
    app.include_router(
        movement_analysis_admin_router,
        prefix=settings.api_v1_prefix,
        tags=["movement-analysis-admin"]
    )
    
    # Movement Analysis Web Pages (standalone interface)
    app.include_router(
        movement_analysis_page_router,
        tags=["movement-analysis-pages"]
    )
    
    logger.info("Movement Analysis module routes registered successfully")
except Exception as movement_analysis_error:
    logger.warning(f"Movement Analysis module initialization skipped: {movement_analysis_error}")

# Simple admin API endpoints for frontend compatibility
from fastapi import Request  # noqa: E402
from pathlib import Path  # noqa: E402
from datetime import datetime  # noqa: E402

@app.get("/api/admin/models")
async def get_admin_models():
    """Get available Live2D models for admin interface"""
    try:
        # List available models in the Live2D Resources directory
        models = []
        live2d_resources_path = Path(__file__).parent / "web" / "live2d" / "frontend" / "Resources"
        
        if live2d_resources_path.exists():
            for model_dir in live2d_resources_path.iterdir():
                if model_dir.is_dir() and not model_dir.name.startswith('.'):
                    model_file = model_dir / f"{model_dir.name}.model3.json"
                    if model_file.exists():
                        models.append({
                            "id": model_dir.name,
                            "name": model_dir.name,
                            "path": f"Resources/{model_dir.name}/{model_dir.name}.model3.json",
                            "available": True
                        })
        
        return {
            "success": True,
            "models": models,
            "total": len(models)
        }
    except Exception as e:
        logger.error(f"Error getting admin models: {e}")
        return {
            "success": False,
            "models": [],
            "error": str(e)
        }

@app.post("/api/swap-model")
async def api_swap_model(request: Request):
    """API endpoint to swap Live2D model"""
    try:
        body = await request.json()
        model_name = body.get("model", "Hiyori")
        
        return {
            "success": True,
            "message": f"Model swapped to {model_name}",
            "current_model": model_name
        }
    except Exception as e:
        logger.error(f"Error swapping model: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/chat")
async def api_chat(request: Request):
    """API endpoint for chat"""
    try:
        body = await request.json()
        message = body.get("message", "")
        
        return {
            "success": True,
            "response": f"Echo: {message}",
            "agent": "Live2D Assistant",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in chat API: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# Handle Live2D compiled JS resource requests (without /live2d prefix)
@app.get("/Resources/{file_path:path}")
async def serve_live2d_compiled_resources(file_path: str):
    """Serve Live2D Resources for compiled JS that expects /Resources/ paths"""
    try:
        from fastapi.responses import FileResponse
        live2d_resources_path = Path(__file__).parent / "web" / "live2d" / "frontend" / "Resources"
        full_path = live2d_resources_path / file_path
        
        if full_path.exists() and full_path.is_file():
            return FileResponse(full_path)
        else:
            raise HTTPException(status_code=404, detail=f"Resource not found: {file_path}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving compiled resource {file_path}: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# Authentication and User Interface Routes
@app.get("/auth.html")
async def serve_auth_page():
    """Serve the authentication page"""
    try:
        from fastapi.responses import FileResponse
        auth_path = Path(__file__).parent / "web" / "live2d" / "frontend" / "auth.html"
        
        if auth_path.exists():
            return FileResponse(auth_path)
        else:
            raise HTTPException(status_code=404, detail="Authentication page not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving auth page: {e}")
        raise HTTPException(status_code=500, detail="Error serving auth page")


@app.get("/profile.html")
async def serve_profile_page():
    """Serve the user profile page"""
    try:
        from fastapi.responses import FileResponse
        profile_path = Path(__file__).parent / "web" / "live2d" / "frontend" / "profile.html"
        
        if profile_path.exists():
            return FileResponse(profile_path)
        else:
            raise HTTPException(status_code=404, detail="Profile page not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving profile page: {e}")
        raise HTTPException(status_code=500, detail="Error serving profile page")


@app.get("/admin-dashboard.html")
async def serve_admin_dashboard():
    """Serve the admin dashboard"""
    try:
        from fastapi.responses import FileResponse
        dashboard_path = Path(__file__).parent / "web" / "live2d" / "frontend" / "admin-dashboard.html"
        
        if dashboard_path.exists():
            return FileResponse(dashboard_path)
        else:
            raise HTTPException(status_code=404, detail="Admin dashboard not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving admin dashboard: {e}")
        raise HTTPException(status_code=500, detail="Error serving admin dashboard")


@app.get("/chatbot-working-enhanced.html")
async def serve_chatbot_enhanced():
    """Serve the enhanced chatbot page"""
    try:
        from fastapi.responses import FileResponse
        chatbot_path = Path(__file__).parent / "web" / "live2d" / "frontend" / "index.html"
        
        if chatbot_path.exists():
            return FileResponse(chatbot_path)
        else:
            raise HTTPException(status_code=404, detail="Enhanced chatbot page not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving enhanced chatbot page: {e}")
        raise HTTPException(status_code=500, detail="Error serving enhanced chatbot page")


@app.get("/admin.html")
async def serve_admin_page():
    """Serve the admin page"""
    try:
        from fastapi.responses import FileResponse
        admin_path = Path(__file__).parent / "web" / "live2d" / "frontend" / "admin.html"
        
        if admin_path.exists():
            return FileResponse(admin_path)
        else:
            raise HTTPException(status_code=404, detail="Admin page not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving admin page: {e}")
        raise HTTPException(status_code=500, detail="Error serving admin page")


# Admin dashboard routes (if enabled)
if settings.enable_admin_interface:
    try:
        # New refactored admin routes
        from src.web.admin.routes import admin_router as new_admin_router
        # Legacy admin routes from the old routes.py file
        from src.web.admin.legacy_routes import admin_router, admin_api_router
        from src.web.admin.dashboard_routes import router as dashboard_router
        from src.web.api.v1.super_admin_simple import router as super_admin_router
        
        # New refactored admin interface
        app.include_router(
            new_admin_router,
            tags=["admin-v2"]
        )
        
        # Legacy admin routes (for backward compatibility)
        app.include_router(
            admin_router,
            tags=["admin-dashboard"]
        )
        
        app.include_router(
            admin_api_router,
            tags=["admin-api"]
        )
        
        # Super Admin API endpoints
        app.include_router(
            super_admin_router,
            tags=["super-admin-api"]
        )
        
        # Legacy Super Admin Dashboard (HTML)
        app.include_router(
            dashboard_router,
            tags=["super-admin-dashboard"]
        )
        
        # Social Worker Hub routes
        try:
            from src.web.admin.routes.social_worker_hub import router as sw_hub_router
            app.include_router(
                sw_hub_router,
                prefix="/admin",
                tags=["social-worker-hub"]
            )
            logger.info("Social Worker Hub routes registered")
        except Exception as sw_err:
            logger.warning(f"Social Worker Hub routes not loaded: {sw_err}")
            
    except Exception as e:
        logger.warning(f"Admin interface initialization skipped due to error: {e}")

# =============================================================================
# ROOT ENDPOINTS
# =============================================================================

@app.get("/")
async def root():
    """Serve the main Live2D interface"""
    try:
        from fastapi.responses import FileResponse
        index_path = Path(__file__).parent / "web" / "live2d" / "frontend" / "index.html"
        
        if index_path.exists():
            return FileResponse(index_path)
        else:
            # Fallback gracefully to Live2D route or API docs if the file is unavailable in container
            # Prefer Live2D interface if router is mounted
            return RedirectResponse(url="/live2d/", status_code=302)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving main interface: {e}")
        # Final fallback to docs to keep UX usable
        return RedirectResponse(url="/docs", status_code=302)


@app.get("/health")
async def simple_health():
    """Simple health check endpoint"""
    from datetime import datetime
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": settings.app_name,
        "version": settings.app_version
    }


@app.get("/info")
async def app_info():
    """Application information endpoint"""
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "debug": settings.debug,
        "supported_languages": settings.supported_languages,
        "cultural_context": settings.cultural_context,
        "agent_types": [
            "illness_monitor",
            "mental_health", 
            "safety_guardian",
            "wellness_coach"
        ],
        "api_version": "v1",
        "api_prefix": settings.api_v1_prefix
    }


# =============================================================================
# DEVELOPMENT UTILITIES
# =============================================================================

if settings.is_development:
    @app.get("/dev/config")
    async def dev_config():
        """Development endpoint to view configuration (non-sensitive)"""
        return {
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "debug": settings.debug,
            "log_level": settings.log_level,
            "database_host": settings.database_host,
            "database_port": settings.database_port,
            "database_name": settings.database_name,
            "redis_host": settings.redis_host,
            "redis_port": settings.redis_port,
            "cors_origins": settings.cors_origins,
            "supported_languages": settings.supported_languages
        }

# =============================================================================
# CLI INTERFACE
# =============================================================================

def cli():
    """Command line interface for the application"""
    import typer
    
    app_cli = typer.Typer()
    
    @app_cli.command()
    def serve(
        host: str = settings.host,
        port: int = settings.port,
        reload: bool = settings.reload,
        log_level: str = settings.log_level.lower()
    ):
        """Start the Healthcare AI V2 server"""
        uvicorn.run(
            "src.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
            access_log=settings.log_api_requests,
            use_colors=settings.is_development
        )
    
    @app_cli.command()
    def init_db():
        """Initialize the database"""
        async def _init_db():
            from src.database.connection import init_database, create_tables
            await init_database()
            await create_tables()
            logger.info("Database initialized successfully")
        
        asyncio.run(_init_db())
    
    @app_cli.command()
    def create_admin():
        """Create an admin user"""
        async def _create_admin():
            # TODO: Implement admin user creation
            logger.info("Admin user creation not yet implemented")
        
        asyncio.run(_create_admin())
    
    app_cli()


# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Run with uvicorn directly
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
        access_log=settings.log_api_requests,
        use_colors=settings.is_development
    )


# =============================================================================
# APPLICATION ENTRY POINT
# =============================================================================
