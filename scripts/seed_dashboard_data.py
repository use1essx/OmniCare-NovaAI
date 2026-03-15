import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.database.connection import init_database, get_sync_session
from src.database.models_comprehensive import Base, Organization, Live2DModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    logger.info("🌱 Seeding dashboard data...")
    
    # Initialize database (creates engines and tables)
    logger.info("Initializing database connection...")
    await init_database()
    
    with get_sync_session() as session:
        # 1. Seed Organizations (Target: 4)
        org_count = session.query(Organization).count()
        logger.info(f"Current Organizations: {org_count}")
        
        if org_count < 4:
            logger.info("Creating sample organizations...")
            orgs_data = [
                {"name": "City General Hospital", "type": "hospital", "description": "Main city hospital serving the downtown area"},
                {"name": "Community Health Clinic", "type": "clinic", "description": "Local community clinic for primary care"},
                {"name": "Mental Wellness Center", "type": "specialist", "description": "Specialized center for mental health services"},
                {"name": "Elderly Care Home", "type": "nursing_home", "description": "Residential care facility for the elderly"}
            ]
            
            for data in orgs_data:
                existing = session.query(Organization).filter_by(name=data["name"]).first()
                if not existing:
                    org = Organization(**data)
                    session.add(org)
                    logger.info(f"  + Added: {data['name']}")
            
            session.commit()
        
        # 2. Seed Live2D Models (Target: 2)
        model_count = session.query(Live2DModel).count()
        logger.info(f"Current Live2D Models: {model_count}")
        
        if model_count < 2:
            logger.info("Creating sample Live2D models...")
            models_data = [
                {"name": "Hiyori", "model_path": "/models/hiyori/hiyori.model3.json", "description": "Standard female avatar for general assistance", "is_default": True},
                {"name": "Natori", "model_path": "/models/natori/natori.model3.json", "description": "Professional male avatar for medical consultations", "is_default": False}
            ]
            
            for data in models_data:
                existing = session.query(Live2DModel).filter_by(name=data["name"]).first()
                if not existing:
                    model = Live2DModel(**data)
                    session.add(model)
                    logger.info(f"  + Added: {data['name']}")
            
            session.commit()
            
        # Final Verification
        final_orgs = session.query(Organization).count()
        final_models = session.query(Live2DModel).count()
        
        logger.info("="*40)
        logger.info(f"✅ Seeding Complete")
        logger.info(f"  Organizations: {final_orgs}")
        logger.info(f"  Live2D Models: {final_models}")
        logger.info("="*40)

if __name__ == "__main__":
    asyncio.run(main())
