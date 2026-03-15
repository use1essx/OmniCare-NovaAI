"""
Seed KB Categories - Fixed Version
Simplified script that only seeds categories without trying to clear non-existent columns
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.database.connection import init_database, get_async_session_context


async def seed_categories():
    """Seed the kb_categories table with simple 3-level structure"""
    
    # Initialize database
    await init_database()
    
    async with get_async_session_context() as db:
        try:
            # Check if categories already exist
            result = await db.execute(text("SELECT COUNT(*) FROM kb_categories"))
            count = result.scalar()
            
            if count > 0:
                print(f"⚠️  Categories already exist ({count} categories). Skipping seed.")
                return
            
            print("Seeding KB categories...")
            
            # Level 1: Age Groups
            age_groups = [
                {
                    "name_en": "Elderly",
                    "name_zh": "長者",
                    "slug": "elderly",
                    "icon": "👴",
                    "description_en": "Services and information for elderly citizens",
                    "description_zh": "長者服務及資訊",
                    "level": 1,
                    "display_order": 1,
                    "parent_id": None
                },
                {
                    "name_en": "Child",
                    "name_zh": "兒童",
                    "slug": "child",
                    "icon": "👶",
                    "description_en": "Services and information for children",
                    "description_zh": "兒童服務及資訊",
                    "level": 1,
                    "display_order": 2,
                    "parent_id": None
                },
                {
                    "name_en": "Teen",
                    "name_zh": "青少年",
                    "slug": "teen",
                    "icon": "🧑",
                    "description_en": "Services and information for teenagers",
                    "description_zh": "青少年服務及資訊",
                    "level": 1,
                    "display_order": 3,
                    "parent_id": None
                },
                {
                    "name_en": "Adult",
                    "name_zh": "成人",
                    "slug": "adult",
                    "icon": "👨",
                    "description_en": "Services and information for adults",
                    "description_zh": "成人服務及資訊",
                    "level": 1,
                    "display_order": 4,
                    "parent_id": None
                }
            ]
            
            age_group_ids = {}
            for ag in age_groups:
                result = await db.execute(
                    text("""
                        INSERT INTO kb_categories 
                        (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                        VALUES (:name_en, :name_zh, :slug, :icon, :description_en, :description_zh, :level, :display_order, :parent_id)
                        RETURNING id
                    """),
                    ag
                )
                age_group_id = result.fetchone()[0]
                age_group_ids[ag["slug"]] = age_group_id
                print(f"  ✅ {ag['name_en']} (ID: {age_group_id})")
            
            await db.commit()
            
            # Level 2: Categories under Elderly
            elderly_categories = [
                {
                    "name_en": "Elderly Discount",
                    "name_zh": "長者優惠",
                    "slug": "elderly-discount",
                    "icon": "💳",
                    "description_en": "Discount cards and benefits for elderly",
                    "description_zh": "長者優惠卡及福利",
                    "level": 2,
                    "display_order": 1,
                    "parent_id": age_group_ids["elderly"]
                },
                {
                    "name_en": "Health",
                    "name_zh": "健康",
                    "slug": "health",
                    "icon": "🏥",
                    "description_en": "Health services and medical care",
                    "description_zh": "健康服務及醫療護理",
                    "level": 2,
                    "display_order": 2,
                    "parent_id": age_group_ids["elderly"]
                }
            ]
            
            category_ids = {}
            for cat in elderly_categories:
                result = await db.execute(
                    text("""
                        INSERT INTO kb_categories 
                        (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                        VALUES (:name_en, :name_zh, :slug, :icon, :description_en, :description_zh, :level, :display_order, :parent_id)
                        RETURNING id
                    """),
                    cat
                )
                category_id = result.fetchone()[0]
                category_ids[cat["slug"]] = category_id
                print(f"  ✅ {cat['name_en']} (ID: {category_id})")
            
            await db.commit()
            
            # Level 3: Topics under Categories
            topics = [
                # Topics under Elderly Discount
                {
                    "name_en": "Elder Card",
                    "name_zh": "長者卡",
                    "slug": "elder-card",
                    "icon": "🎫",
                    "description_en": "Elder card application and usage",
                    "description_zh": "長者卡申請及使用",
                    "level": 3,
                    "display_order": 1,
                    "parent_id": category_ids["elderly-discount"]
                },
                # Topics under Health
                {
                    "name_en": "Self-Care",
                    "name_zh": "自我照顧",
                    "slug": "self-care",
                    "icon": "🧘",
                    "description_en": "Self-care tips and practices",
                    "description_zh": "自我照顧貼士及實踐",
                    "level": 3,
                    "display_order": 1,
                    "parent_id": category_ids["health"]
                },
                {
                    "name_en": "Health Life",
                    "name_zh": "健康生活",
                    "slug": "health-life",
                    "icon": "🍎",
                    "description_en": "Healthy lifestyle and wellness",
                    "description_zh": "健康生活方式及養生",
                    "level": 3,
                    "display_order": 2,
                    "parent_id": category_ids["health"]
                }
            ]
            
            for topic in topics:
                result = await db.execute(
                    text("""
                        INSERT INTO kb_categories 
                        (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                        VALUES (:name_en, :name_zh, :slug, :icon, :description_en, :description_zh, :level, :display_order, :parent_id)
                        RETURNING id
                    """),
                    topic
                )
                topic_id = result.fetchone()[0]
                print(f"  ✅ {topic['name_en']} (ID: {topic_id})")
            
            await db.commit()
            
            # Verify counts
            result = await db.execute(text("SELECT COUNT(*) FROM kb_categories"))
            total = result.fetchone()[0]
            
            print(f"\n{'='*60}")
            print(f"✅ Successfully seeded {total} categories!")
            print(f"{'='*60}")
            
        except Exception as e:
            print(f"❌ Error seeding categories: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    print("="*60)
    print("KB Categories Seeding - Fixed Version")
    print("="*60)
    asyncio.run(seed_categories())
