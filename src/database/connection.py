"""
Healthcare AI V2 - Database Connection Management
Handles PostgreSQL connections with SQLAlchemy async and sync engines
"""

import logging
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from src.core.config import settings

# Create declarative base for models
Base = declarative_base()

# Global engine instances
async_engine: Optional[AsyncEngine] = None
sync_engine = None
AsyncSessionLocal: Optional[async_sessionmaker] = None
SessionLocal = None

logger = logging.getLogger(__name__)


def create_database_engines():
    """
    Create both async and sync database engines with proper configuration
    """
    global async_engine, sync_engine, AsyncSessionLocal, SessionLocal
    
    # Async Engine Configuration
    async_engine_kwargs = {
        "url": settings.database_url_str,
        "echo": settings.log_database_queries,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout": settings.database_pool_timeout,
        "pool_recycle": settings.database_pool_recycle,
        "pool_pre_ping": True,  # Validate connections before use
    }
    
    # Use NullPool for testing to avoid connection issues
    if settings.is_testing:
        async_engine_kwargs.update({
            "poolclass": NullPool,
        })
        # Remove pool parameters for NullPool
        for key in ["pool_size", "max_overflow", "pool_timeout", "pool_recycle"]:
            async_engine_kwargs.pop(key, None)
    
    async_engine = create_async_engine(**async_engine_kwargs)
    
    # Sync Engine Configuration (for migrations and admin tasks)
    sync_engine_kwargs = {
        "url": settings.database_sync_url_str,
        "echo": settings.log_database_queries,
        "pool_size": settings.database_pool_size,
        "max_overflow": settings.database_max_overflow,
        "pool_timeout": settings.database_pool_timeout,
        "pool_recycle": settings.database_pool_recycle,
        "pool_pre_ping": True,
        "poolclass": QueuePool if not settings.is_testing else NullPool,
    }
    
    if settings.is_testing:
        sync_engine_kwargs["poolclass"] = NullPool
        sync_engine_kwargs.pop("pool_size", None)
        sync_engine_kwargs.pop("max_overflow", None)
        sync_engine_kwargs.pop("pool_timeout", None)
        sync_engine_kwargs.pop("pool_recycle", None)
    
    sync_engine = create_engine(**sync_engine_kwargs)
    
    # Create session factories
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    SessionLocal = sessionmaker(
        sync_engine,
        autocommit=False,
        autoflush=False,
    )
    
    # Add connection pool event listeners
    setup_engine_events()
    
    logger.info("Database engines created successfully")


def setup_engine_events():
    """
    Setup SQLAlchemy engine events for monitoring and optimization
    """
    if async_engine is None or sync_engine is None:
        return
    
    @event.listens_for(sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Set PostgreSQL connection parameters"""
        if hasattr(dbapi_connection, 'execute'):
            # Set timezone to UTC
            cursor = dbapi_connection.cursor()
            cursor.execute("SET timezone='UTC'")
            cursor.close()
    
    @event.listens_for(sync_engine, "checkout")
    def receive_checkout(dbapi_connection, connection_record, connection_proxy):
        """Log when connection is checked out from pool"""
        if settings.log_database_queries:
            logger.debug("Connection checked out from pool")
    
    @event.listens_for(sync_engine, "checkin")
    def receive_checkin(dbapi_connection, connection_record):
        """Log when connection is returned to pool"""
        if settings.log_database_queries:
            logger.debug("Connection returned to pool")


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions
    Ensures proper session cleanup and error handling
    """
    if AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()

# Alias for backward compatibility with import scripts
get_async_db_session = get_async_session


@asynccontextmanager
async def get_async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions - for use in background tasks
    Does not auto-commit to allow caller control
    """
    if AsyncSessionLocal is None:
        # Initialize database if not yet done (for background tasks)
        create_database_engines()
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error in context: {e}")
            raise
        finally:
            await session.close()


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """
    Sync context manager for database sessions
    Used for migrations and admin tasks
    """
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for async database sessions
    """
    async with get_async_session() as session:
        yield session


def get_sync_db() -> Generator[Session, None, None]:
    """
    Dependency for sync database sessions
    """
    with get_sync_session() as session:
        yield session


async def init_database():
    """
    Initialize database connections and create tables
    """
    try:
        create_database_engines()
        
        # Test async connection
        async with get_async_session() as session:
            await session.execute(text("SELECT 1"))
            logger.info("Async database connection successful")
        
        # Test sync connection
        with get_sync_session() as session:
            session.execute(text("SELECT 1"))
            logger.info("Sync database connection successful")
        
        # Create all tables
        logger.info("Creating database tables...")
        try:
            # Import models to ensure they're registered with Base
            
            # Create tables using sync engine
            Base.metadata.create_all(bind=sync_engine)
            logger.info("Database tables created successfully")
            
            # Verify tables were created
            with get_sync_session() as session:
                result = session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
                tables = [row[0] for row in result.fetchall()]
                logger.info(f"Created tables: {tables}")
                
        except Exception as table_error:
            logger.error(f"Table creation failed: {table_error}")
            # Don't raise - allow system to continue without tables for now
        
        logger.info("Database initialization completed")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def close_database():
    """
    Close database connections
    """
    global async_engine, sync_engine
    
    try:
        if async_engine:
            await async_engine.dispose()
            logger.info("Async database engine disposed")
        
        if sync_engine:
            sync_engine.dispose()
            logger.info("Sync database engine disposed")
        
        logger.info("Database connections closed")
        
    except Exception as e:
        logger.error(f"Error closing database connections: {e}")


async def create_tables():
    """
    Create all database tables
    Used for testing and initial setup
    """
    if async_engine is None:
        raise RuntimeError("Database not initialized")
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created")


async def drop_tables():
    """
    Drop all database tables
    Used for testing cleanup
    """
    if async_engine is None:
        raise RuntimeError("Database not initialized")
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("Database tables dropped")


async def check_database_health() -> dict:
    """
    Check database health and return status information
    """
    health_status = {
        "status": "healthy",
        "async_engine": False,
        "sync_engine": False,
        "async_connection": False,
        "sync_connection": False,
        "pool_info": {},
        "errors": []
    }
    
    try:
        # Check engines exist
        if async_engine is not None:
            health_status["async_engine"] = True
        
        if sync_engine is not None:
            health_status["sync_engine"] = True
            
            # Get pool information
            pool_info = sync_engine.pool
            if hasattr(pool_info, 'size'):
                health_status["pool_info"] = {
                    "size": pool_info.size(),
                    "checked_in": pool_info.checkedin(),
                    "checked_out": pool_info.checkedout(),
                    "overflow": pool_info.overflow(),
                }
        
        # Test async connection
        if async_engine:
            try:
                async with get_async_session() as session:
                    await session.execute(text("SELECT 1"))
                health_status["async_connection"] = True
            except Exception as e:
                health_status["errors"].append(f"Async connection failed: {str(e)}")
        
        # Test sync connection
        if sync_engine:
            try:
                with get_sync_session() as session:
                    session.execute(text("SELECT 1"))
                health_status["sync_connection"] = True
            except Exception as e:
                health_status["errors"].append(f"Sync connection failed: {str(e)}")
        
        # Determine overall status
        if not health_status["async_connection"] or not health_status["sync_connection"]:
            health_status["status"] = "unhealthy"
        elif health_status["errors"]:
            health_status["status"] = "degraded"
    
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["errors"].append(f"Health check failed: {str(e)}")
    
    return health_status


# Database utilities for testing
class DatabaseTestUtils:
    """Utilities for database testing"""
    
    @staticmethod
    async def reset_database():
        """Reset database for testing"""
        await drop_tables()
        await create_tables()
    
    @staticmethod
    async def create_test_session() -> AsyncSession:
        """Create a test database session"""
        if AsyncSessionLocal is None:
            await init_database()
        
        return AsyncSessionLocal()
    
    @staticmethod
    @asynccontextmanager
    async def test_transaction():
        """Context manager for test transactions that are always rolled back"""
        async with get_async_session() as session:
            transaction = await session.begin()
            try:
                yield session
            finally:
                await transaction.rollback()


# Export commonly used items
__all__ = [
    "Base",
    "async_engine",
    "sync_engine",
    "AsyncSessionLocal",
    "SessionLocal",
    "get_async_session",
    "get_async_session_context",
    "get_sync_session",
    "get_async_db",
    "get_sync_db",
    "init_database",
    "close_database",
    "create_tables",
    "drop_tables",
    "check_database_health",
    "DatabaseTestUtils",
]
