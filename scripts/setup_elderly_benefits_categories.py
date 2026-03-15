#!/usr/bin/env python3
"""
Setup Elderly Benefits Category Structure

Creates the proper category hierarchy for elderly benefits based on the folder structure.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.database.connection import get_async_db


async def setup_elderly_benefits():
    """Create elderly benefits category structure"""
    
    # Initialize database first
    from src.database.connection import init_database
    await init_database()
    
    async for db in get_async_db():
        try:
            # Step 1: Get the Elderly age group ID
            result = await db.execute(
                text("SELECT id FROM kb_categories WHERE slug = 'elderly' AND level = 1")
            )
            elderly_row = result.fetchone()
            if not elderly_row:
                print("❌ Error: Elderly age group not found!")
                return
            
            elderly_id = elderly_row[0]
            print(f"✅ Found Elderly age group (ID: {elderly_id})")
            
            # Step 2: Create Level 2 category "長者福利" (Elderly Benefits)
            result = await db.execute(
                text("""
                    INSERT INTO kb_categories 
                    (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                    VALUES 
                    ('Elderly Benefits', '長者福利', 'elderly-benefits', '💰', 
                     'Government benefits and services for elderly citizens',
                     '政府為長者提供的福利及服務',
                     2, 1, :parent_id)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                """),
                {"parent_id": elderly_id}
            )
            await db.commit()
            
            benefits_row = result.fetchone()
            if benefits_row:
                benefits_id = benefits_row[0]
                print(f"✅ Created '長者福利' category (ID: {benefits_id})")
            else:
                # Category already exists, get its ID
                result = await db.execute(
                    text("SELECT id FROM kb_categories WHERE slug = 'elderly-benefits' AND level = 2")
                )
                benefits_id = result.fetchone()[0]
                print(f"ℹ️  '長者福利' category already exists (ID: {benefits_id})")
            
            # Step 3: Create Level 3 topics
            topics = [
                ("Elderly Octopus Card", "樂悠咭", "elderly-octopus-card", "🚇", 
                 "Concessionary travel scheme for elderly", "長者交通優惠計劃"),
                
                ("CSSA", "綜援", "cssa", "💵", 
                 "Comprehensive Social Security Assistance", "綜合社會保障援助計劃"),
                
                ("Medical Fee Waiver", "醫療費用減免", "medical-fee-waiver", "🏥", 
                 "Medical fee waiver for elderly", "長者醫療費用減免"),
                
                ("Elderly Dental Assistance", "長者牙科服務資助", "elderly-dental-assistance", "🦷", 
                 "Dental care subsidy for elderly", "長者牙科服務資助計劃"),
                
                ("Community Care Service Voucher", "長者社區照顧服務券計劃", "community-care-voucher", "🏘️", 
                 "Community care service voucher scheme", "長者社區照顧服務券計劃"),
                
                ("Elderly Health Care Voucher", "長者醫療券計劃", "elderly-health-voucher", "💊", 
                 "Health care voucher scheme for elderly", "長者醫療券計劃"),
                
                ("Residential Care Service Voucher", "長者院舍照顧服務券計劃", "residential-care-voucher", "🏠", 
                 "Residential care service voucher scheme", "長者院舍照顧服務券計劃"),
                
                ("Old Age Allowance", "高齡津貼、傷殘津貼及長者生活津貼", "old-age-allowance", "💰", 
                 "Old age allowance, disability allowance and old age living allowance", 
                 "高齡津貼、傷殘津貼及長者生活津貼"),
            ]
            
            for i, (name_en, name_zh, slug, icon, desc_en, desc_zh) in enumerate(topics, start=1):
                result = await db.execute(
                    text("""
                        INSERT INTO kb_categories 
                        (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                        VALUES 
                        (:name_en, :name_zh, :slug, :icon, :desc_en, :desc_zh, 3, :order, :parent_id)
                        ON CONFLICT DO NOTHING
                        RETURNING id
                    """),
                    {
                        "name_en": name_en,
                        "name_zh": name_zh,
                        "slug": slug,
                        "icon": icon,
                        "desc_en": desc_en,
                        "desc_zh": desc_zh,
                        "order": i,
                        "parent_id": benefits_id
                    }
                )
                await db.commit()
                
                topic_row = result.fetchone()
                if topic_row:
                    print(f"  ✅ Created topic: {name_zh} (ID: {topic_row[0]})")
                else:
                    print(f"  ℹ️  Topic already exists: {name_zh}")
            
            # Clear cache
            print("\n🔄 Clearing category cache...")
            from src.knowledge_base.category_service import get_category_service
            category_service = get_category_service()
            category_service._cache.clear()
            print("✅ Cache cleared!")
            
            print("\n✅ Setup complete! Refresh the KB Sandbox to see the new structure.")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()


if __name__ == "__main__":
    asyncio.run(setup_elderly_benefits())
