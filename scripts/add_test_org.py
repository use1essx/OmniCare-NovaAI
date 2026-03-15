import sys
import os
import asyncio
import logging
import uuid

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.database.connection import init_database, get_sync_session
from src.database.models_comprehensive import Organization
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("🧪 Adding Test Organization...")
    
    # Initialize database
    await init_database()
    
    with get_sync_session() as session:
        # Check current count
        initial_count = session.query(Organization).count()
        logger.info(f"Current Organizations: {initial_count}")
        
        # Reset sequence to max id to avoid unique constraint errors
        try:
            session.execute(text("SELECT setval('organizations_id_seq', (SELECT MAX(id) FROM organizations));"))
            session.commit()
            logger.info("Sequence reset successfully")
        except Exception as e:
            logger.warning(f"Could not reset sequence: {e}")
            session.rollback()
        
        # Add new organization
        new_org_name = f"Test Clinic {uuid.uuid4().hex[:8]}"
        logger.info(f"Adding: {new_org_name}")
        
        org = Organization(
            name=new_org_name,
            type="clinic",
            description="Temporary test organization for live update verification"
        )
        session.add(org)
        session.commit()
        
        # Check new count
        final_count = session.query(Organization).count()
        logger.info(f"New Organizations Count: {final_count}")
        
        if final_count == initial_count + 1:
            logger.info("✅ SUCCESS: Organization added!")
        else:
            logger.error("❌ FAILURE: Count did not increase.")

if __name__ == "__main__":
    asyncio.run(main())
