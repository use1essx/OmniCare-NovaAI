#!/usr/bin/env python3
"""
Export Database Data to Seed File
Exports current database data to a Python seed file that can be committed to Git
"""

import sys
import os
import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.database.connection import init_database, get_sync_session
from src.database.models_comprehensive import (
    Base, Organization, User, Live2DModel
)
from src.movement_analysis.models import AssessmentRule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tables to export (in order of dependencies)
EXPORT_TABLES = [
    ('organizations', Organization),
    ('live2d_models', Live2DModel),
    ('assessment_rules', AssessmentRule),
    # Add more tables as needed
]

def serialize_model(obj):
    """Convert SQLAlchemy model to dictionary"""
    data = {}
    for column in obj.__table__.columns:
        value = getattr(obj, column.name)
        # Handle datetime objects
        if isinstance(value, datetime):
            data[column.name] = value.isoformat()
        else:
            data[column.name] = value
    return data

async def export_data():
    """Export database data to seed file"""
    logger.info("🔄 Exporting database data...")
    
    # Initialize database
    await init_database()
    
    exported_data = {}
    
    with get_sync_session() as session:
        for table_name, model_class in EXPORT_TABLES:
            logger.info(f"Exporting {table_name}...")
            
            # Query all records
            records = session.query(model_class).all()
            
            # Serialize records
            serialized = [serialize_model(record) for record in records]
            
            exported_data[table_name] = serialized
            logger.info(f"  ✅ Exported {len(serialized)} records from {table_name}")
    
    # Create output directory
    output_dir = Path("scripts/seed_data")
    output_dir.mkdir(exist_ok=True)
    
    # Write to JSON file
    output_file = output_dir / "default_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(exported_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✅ Data exported to {output_file}")
    
    # Generate Python seed script
    generate_seed_script(exported_data, output_dir)
    
    return exported_data

def generate_seed_script(data, output_dir):
    """Generate Python seed script from exported data"""
    
    script_content = '''#!/usr/bin/env python3
"""
Auto-generated Database Seed Script
Generated on: {timestamp}

This script seeds the database with default data.
Run this after initializing a fresh database.
"""

import sys
import os
import asyncio
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.database.connection import init_database, get_sync_session
from src.database.models_comprehensive import (
    Organization, Live2DModel, AssessmentRule, KBCategory
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Exported data
SEED_DATA = {data_json}

async def seed_database():
    """Seed database with default data"""
    logger.info("🌱 Seeding database with default data...")
    
    # Initialize database
    await init_database()
    
    with get_sync_session() as session:
        # Seed Organizations
        if 'organizations' in SEED_DATA:
            logger.info("Seeding organizations...")
            for org_data in SEED_DATA['organizations']:
                # Remove id to let database auto-generate
                org_data_copy = org_data.copy()
                org_data_copy.pop('id', None)
                
                # Check if exists
                existing = session.query(Organization).filter_by(
                    name=org_data_copy['name']
                ).first()
                
                if not existing:
                    org = Organization(**org_data_copy)
                    session.add(org)
                    logger.info(f"  + Added organization: {{org_data_copy['name']}}")
            
            session.commit()
        
        # Seed Live2D Models
        if 'live2d_models' in SEED_DATA:
            logger.info("Seeding Live2D models...")
            for model_data in SEED_DATA['live2d_models']:
                model_data_copy = model_data.copy()
                model_data_copy.pop('id', None)
                
                existing = session.query(Live2DModel).filter_by(
                    name=model_data_copy['name']
                ).first()
                
                if not existing:
                    model = Live2DModel(**model_data_copy)
                    session.add(model)
                    logger.info(f"  + Added Live2D model: {{model_data_copy['name']}}")
            
            session.commit()
        
        # Seed Assessment Rules
        if 'assessment_rules' in SEED_DATA:
            logger.info("Seeding assessment rules...")
            for rule_data in SEED_DATA['assessment_rules']:
                rule_data_copy = rule_data.copy()
                rule_data_copy.pop('id', None)
                
                existing = session.query(AssessmentRule).filter_by(
                    name=rule_data_copy['name']
                ).first()
                
                if not existing:
                    rule = AssessmentRule(**rule_data_copy)
                    session.add(rule)
                    logger.info(f"  + Added assessment rule: {{rule_data_copy['name']}}")
            
            session.commit()
        
        # Seed KB Categories
        if 'kb_categories' in SEED_DATA:
            logger.info("Seeding knowledge base categories...")
            for cat_data in SEED_DATA['kb_categories']:
                cat_data_copy = cat_data.copy()
                cat_data_copy.pop('id', None)
                
                existing = session.query(KBCategory).filter_by(
                    name=cat_data_copy['name'],
                    level=cat_data_copy['level']
                ).first()
                
                if not existing:
                    category = KBCategory(**cat_data_copy)
                    session.add(category)
                    logger.info(f"  + Added KB category: {{cat_data_copy['name']}}")
            
            session.commit()
        
        # Final count
        org_count = session.query(Organization).count()
        model_count = session.query(Live2DModel).count()
        rule_count = session.query(AssessmentRule).count()
        cat_count = session.query(KBCategory).count()
        
        logger.info("="*60)
        logger.info("✅ Database seeding complete!")
        logger.info(f"  Organizations: {{org_count}}")
        logger.info(f"  Live2D Models: {{model_count}}")
        logger.info(f"  Assessment Rules: {{rule_count}}")
        logger.info(f"  KB Categories: {{cat_count}}")
        logger.info("="*60)

if __name__ == "__main__":
    asyncio.run(seed_database())
'''.format(
        timestamp=datetime.now().isoformat(),
        data_json=json.dumps(data, indent=4)
    )
    
    output_file = output_dir / "seed_default_data.py"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # Make executable
    os.chmod(output_file, 0o755)
    
    logger.info(f"✅ Seed script generated: {output_file}")

async def main():
    try:
        data = await export_data()
        
        logger.info("\n" + "="*60)
        logger.info("✅ Export complete!")
        logger.info("="*60)
        logger.info("\nNext steps:")
        logger.info("1. Review the exported data in scripts/seed_data/")
        logger.info("2. Commit the seed files to Git:")
        logger.info("   git add scripts/seed_data/")
        logger.info("   git commit -m 'Add default database seed data'")
        logger.info("3. On another device, run:")
        logger.info("   python scripts/seed_data/seed_default_data.py")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
