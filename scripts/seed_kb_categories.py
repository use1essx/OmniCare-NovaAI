"""
Seed KB Categories
==================
Populate the kb_categories table with initial category structure based on
the fyp_長者 folder structure.

Usage:
    python scripts/seed_kb_categories.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.database.connection import get_async_db
from src.core.logging import get_logger

logger = get_logger(__name__)


# Initial category structure based on fyp_長者 folder
INITIAL_CATEGORIES = [
    {
        "name_en": "Elderly Services",
        "name_zh": "長者服務",
        "slug": "elderly-services",
        "icon": "👴",
        "description_en": "Government services and benefits for elderly citizens",
        "description_zh": "政府為長者提供的服務和福利",
        "level": 0,
        "display_order": 1,
        "children": [
            {
                "name_en": "Medical Vouchers",
                "name_zh": "長者醫療券計劃",
                "slug": "medical-vouchers",
                "icon": "🏥",
                "description_en": "Medical subsidy for elderly",
                "description_zh": "睇醫生資助",
                "level": 1,
                "display_order": 1,
            },
            {
                "name_en": "CSSA",
                "name_zh": "綜援",
                "slug": "cssa",
                "icon": "💰",
                "description_en": "Comprehensive Social Security Assistance",
                "description_zh": "綜合社會保障援助計劃",
                "level": 1,
                "display_order": 2,
            },
            {
                "name_en": "Elder Card",
                "name_zh": "樂悠咭",
                "slug": "elder-card",
                "icon": "🚌",
                "description_en": "Transportation benefits for elderly",
                "description_zh": "$2交通優惠",
                "level": 1,
                "display_order": 3,
            },
            {
                "name_en": "Elderly Dental Services",
                "name_zh": "長者牙科服務資助",
                "slug": "elderly-dental",
                "icon": "🦷",
                "description_en": "Dental service subsidies for elderly",
                "description_zh": "牙科服務資助",
                "level": 1,
                "display_order": 4,
            },
            {
                "name_en": "Community Care Service Voucher",
                "name_zh": "長者社區照顧服務券計劃",
                "slug": "community-care-voucher",
                "icon": "🏘️",
                "description_en": "Community care service vouchers",
                "description_zh": "社區照顧服務券",
                "level": 1,
                "display_order": 5,
            },
            {
                "name_en": "Residential Care Service Voucher",
                "name_zh": "長者院舍照顧服務券計劃",
                "slug": "residential-care-voucher",
                "icon": "🏠",
                "description_en": "Residential care service vouchers",
                "description_zh": "院舍照顧服務券",
                "level": 1,
                "display_order": 6,
            },
            {
                "name_en": "Old Age Allowance & Disability Allowance",
                "name_zh": "高齡津貼、傷殘津貼及長者生活津貼",
                "slug": "old-age-allowance",
                "icon": "💵",
                "description_en": "Old age and disability allowances",
                "description_zh": "高齡津貼和傷殘津貼",
                "level": 1,
                "display_order": 7,
            },
            {
                "name_en": "Medical Fee Waiver",
                "name_zh": "醫療費用減免",
                "slug": "medical-fee-waiver",
                "icon": "🏥",
                "description_en": "Medical fee waiver for low-income elderly",
                "description_zh": "醫療費用減免",
                "level": 1,
                "display_order": 8,
            },
        ],
    },
    {
        "name_en": "Children Services",
        "name_zh": "兒童服務",
        "slug": "children-services",
        "icon": "👶",
        "description_en": "Government services and benefits for children",
        "description_zh": "政府為兒童提供的服務和福利",
        "level": 0,
        "display_order": 2,
        "children": [
            {
                "name_en": "Vaccination",
                "name_zh": "疫苗接種",
                "slug": "vaccination",
                "icon": "💉",
                "description_en": "Childhood vaccination programs",
                "description_zh": "兒童疫苗接種計劃",
                "level": 1,
                "display_order": 1,
            },
            {
                "name_en": "Preschool Education",
                "name_zh": "學前教育",
                "slug": "preschool",
                "icon": "🎓",
                "description_en": "Preschool education services",
                "description_zh": "學前教育服務",
                "level": 1,
                "display_order": 2,
            },
            {
                "name_en": "Child Development",
                "name_zh": "兒童發展",
                "slug": "child-development",
                "icon": "🧸",
                "description_en": "Child development assessment and support",
                "description_zh": "兒童發展評估和支援",
                "level": 1,
                "display_order": 3,
            },
        ],
    },
    {
        "name_en": "Youth Services",
        "name_zh": "青少年服務",
        "slug": "youth-services",
        "icon": "🧑",
        "description_en": "Government services and benefits for youth",
        "description_zh": "政府為青少年提供的服務和福利",
        "level": 0,
        "display_order": 3,
        "children": [
            {
                "name_en": "Education Guidance",
                "name_zh": "升學輔導",
                "slug": "education-guidance",
                "icon": "📚",
                "description_en": "Education and career guidance",
                "description_zh": "升學及就業輔導",
                "level": 1,
                "display_order": 1,
            },
            {
                "name_en": "Employment Support",
                "name_zh": "就業支援",
                "slug": "employment-support",
                "icon": "💼",
                "description_en": "Youth employment support programs",
                "description_zh": "青少年就業支援計劃",
                "level": 1,
                "display_order": 2,
            },
            {
                "name_en": "Mental Health",
                "name_zh": "心理健康",
                "slug": "mental-health",
                "icon": "🧠",
                "description_en": "Mental health support for youth",
                "description_zh": "青少年心理健康支援",
                "level": 1,
                "display_order": 3,
            },
        ],
    },
]


async def seed_categories():
    """Seed initial categories into database"""
    logger.info("🌱 Starting KB categories seeding...")
    
    async for db in get_async_db():
        try:
            # Check if categories already exist
            result = await db.execute(text("SELECT COUNT(*) FROM kb_categories"))
            count = result.scalar()
            
            if count > 0:
                logger.warning(f"⚠️  Categories already exist ({count} categories). Skipping seed.")
                logger.info("To re-seed, first run: DELETE FROM kb_categories;")
                return
            
            # Insert categories
            inserted_count = 0
            
            for parent_cat in INITIAL_CATEGORIES:
                # Insert parent category
                parent_result = await db.execute(
                    text("""
                        INSERT INTO kb_categories 
                        (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                        VALUES (:name_en, :name_zh, :slug, :icon, :description_en, :description_zh, :level, :display_order, NULL)
                        RETURNING id
                    """),
                    {
                        "name_en": parent_cat["name_en"],
                        "name_zh": parent_cat["name_zh"],
                        "slug": parent_cat["slug"],
                        "icon": parent_cat["icon"],
                        "description_en": parent_cat.get("description_en"),
                        "description_zh": parent_cat.get("description_zh"),
                        "level": parent_cat["level"],
                        "display_order": parent_cat["display_order"],
                    }
                )
                parent_id = parent_result.scalar()
                inserted_count += 1
                logger.info(f"✅ Created parent category: {parent_cat['name_zh']} (ID: {parent_id})")
                
                # Insert child categories
                for child_cat in parent_cat.get("children", []):
                    await db.execute(
                        text("""
                            INSERT INTO kb_categories 
                            (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                            VALUES (:name_en, :name_zh, :slug, :icon, :description_en, :description_zh, :level, :display_order, :parent_id)
                        """),
                        {
                            "name_en": child_cat["name_en"],
                            "name_zh": child_cat["name_zh"],
                            "slug": child_cat["slug"],
                            "icon": child_cat["icon"],
                            "description_en": child_cat.get("description_en"),
                            "description_zh": child_cat.get("description_zh"),
                            "level": child_cat["level"],
                            "display_order": child_cat["display_order"],
                            "parent_id": parent_id,
                        }
                    )
                    inserted_count += 1
                    logger.info(f"  ✅ Created child category: {child_cat['name_zh']}")
            
            await db.commit()
            logger.info(f"🎉 Successfully seeded {inserted_count} categories!")
            
            # Display category tree
            logger.info("\n📊 Category Tree:")
            result = await db.execute(
                text("""
                    SELECT 
                        c.id,
                        c.name_zh,
                        c.icon,
                        c.level,
                        p.name_zh as parent_name
                    FROM kb_categories c
                    LEFT JOIN kb_categories p ON c.parent_id = p.id
                    ORDER BY c.level, c.display_order
                """)
            )
            
            for row in result:
                indent = "  " * row.level
                parent_info = f" (under {row.parent_name})" if row.parent_name else ""
                logger.info(f"{indent}{row.icon} {row.name_zh}{parent_info}")
            
        except Exception as e:
            logger.error(f"❌ Error seeding categories: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(seed_categories())
