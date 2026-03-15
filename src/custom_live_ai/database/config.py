"""
Database Configuration and Connection Management
PostgreSQL connection setup using SQLAlchemy
Supports both Docker and local development environments
"""

import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv
import logging

from src.custom_live_ai.models.database import Base

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get database URL from environment
# Uses same database as main Healthcare AI system
# Default: postgresql://admin:healthcare_ai_secure_2025@hiyori_postgres:5432/healthcare_ai_v2
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://admin:healthcare_ai_secure_2025@hiyori_postgres:5432/healthcare_ai_v2"
)

def wait_for_db(max_retries=30, retry_interval=2):
    """
    Wait for database to be ready (useful for Docker startup)
    Returns True if database is ready, False otherwise
    """
    db_host = DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else 'unknown'
    logger.info(f"🔄 Waiting for database at {db_host}...")
    
    for attempt in range(max_retries):
        try:
            temp_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
            with temp_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ Database is ready!")
            temp_engine.dispose()
            return True
        except OperationalError as e:
            if attempt < max_retries - 1:
                logger.info(f"   Attempt {attempt + 1}/{max_retries}: Database not ready, retrying in {retry_interval}s...")
                time.sleep(retry_interval)
            else:
                logger.error(f"❌ Failed to connect to database after {max_retries} attempts")
                logger.error(f"   Error: {e}")
                return False
    return False

# Lazy initialization - don't block module import
_engine = None
_SessionLocal = None
_initialized = False

def get_engine():
    """Get or create the database engine (lazy initialization)."""
    global _engine, _initialized
    if _engine is None:
        if not _initialized:
            # Only wait for DB when actually needed, with shorter timeout
            wait_for_db(max_retries=5, retry_interval=1)
            _initialized = True
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            echo=False,
            pool_size=10,
            max_overflow=20
        )
    return _engine

def get_session_factory():
    """Get or create the session factory (lazy initialization)."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal

# For backwards compatibility - create on first access
engine = None  # Will be set on first use
SessionLocal = None  # Will be set on first use


def init_db():
    """
    Initialize database - create all tables
    Call this when starting the application
    """
    try:
        Base.metadata.create_all(bind=get_engine())
        logger.info("✅ Custom Live AI database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Error creating Custom Live AI database tables: {e}")
        raise


def get_db() -> Session:
    """
    Dependency for FastAPI endpoints to get database session
    Usage: db: Session = Depends(get_db)
    """
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
