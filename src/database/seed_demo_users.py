"""
Database Seeding - Demo Users and Super Admin
Automatically creates super admin and demo users on application startup
"""

import logging
import os
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.connection import get_sync_session
from src.security.auth import get_password_hash

logger = logging.getLogger(__name__)


async def ensure_super_admin() -> bool:
    """
    Ensure super admin user exists in the database.
    Creates or updates the super admin user with credentials from environment variables.
    
    Returns:
        bool: True if super admin was created/updated, False if error occurred
    """
    try:
        # Get credentials from environment or use defaults
        username = os.getenv('SUPER_ADMIN_USERNAME', 'admin')
        password = os.getenv('SUPER_ADMIN_PASSWORD', 'admin')
        email = os.getenv('SUPER_ADMIN_EMAIL', f'{username}@healthcare.ai')
        
        # Generate password hash
        hashed_password = get_password_hash(password)
        
        with get_sync_session() as db:
            # Check if super admin exists
            result = db.execute(
                text("SELECT id, username FROM users WHERE username = :username"),
                {"username": username}
            )
            existing_user = result.fetchone()
            
            if existing_user:
                # Update existing super admin
                db.execute(
                    text("""
                        UPDATE users SET
                            hashed_password = :hashed_password,
                            email = :email,
                            is_active = true,
                            is_verified = true,
                            is_admin = true,
                            is_super_admin = true,
                            role = 'super_admin',
                            failed_login_attempts = 0,
                            account_locked_until = NULL,
                            organization_id = 1,
                            updated_at = NOW()
                        WHERE username = :username
                    """),
                    {
                        "hashed_password": hashed_password,
                        "email": email,
                        "username": username
                    }
                )
                db.commit()
                logger.info(f"✅ Super admin updated: {username}")
            else:
                # Create new super admin
                db.execute(
                    text("""
                        INSERT INTO users (
                            email, username, hashed_password, full_name,
                            is_active, is_verified, is_admin, is_super_admin,
                            role, organization_id, failed_login_attempts,
                            created_at, updated_at
                        ) VALUES (
                            :email, :username, :hashed_password, 'System Administrator',
                            true, true, true, true,
                            'super_admin', 1, 0,
                            NOW(), NOW()
                        )
                    """),
                    {
                        "email": email,
                        "username": username,
                        "hashed_password": hashed_password
                    }
                )
                db.commit()
                logger.info(f"✅ Super admin created: {username}")
            
            # Display credentials (development only)
            if os.getenv('ENVIRONMENT', 'development') == 'development':
                logger.info("")
                logger.info("═" * 50)
                logger.info("  🔐 SUPER ADMIN CREDENTIALS")
                logger.info("═" * 50)
                logger.info(f"  Username: {username}")
                logger.info(f"  Email:    {email}")
                logger.info(f"  Password: {password}")
                logger.info(f"  URL:      http://localhost:8000/live2d/auth")
                logger.info("")
                logger.info("  ⚠️  IMPORTANT: Change password in production!")
                logger.info("═" * 50)
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to ensure super admin exists: {e}")
        return False


async def seed_demo_users(force: bool = False) -> bool:
    """
    Seed demo users for testing and development.
    
    Args:
        force: If True, recreate users even if they exist
        
    Returns:
        bool: True if users were seeded, False if they already exist or error occurred
    """
    try:
        with get_sync_session() as db:
            # Check if demo users already exist
            result = db.execute(
                text("SELECT COUNT(*) FROM users WHERE username IN ('doctor1', 'nurse1', 'patient1')")
            )
            existing_count = result.scalar()
            
            if existing_count > 0 and not force:
                logger.info("Demo users already exist, skipping seed")
                return False
            
            # Demo user data
            demo_users = [
                {
                    "username": "doctor1",
                    "email": "doctor1@general-hospital.hk",
                    "password": "doctor123",
                    "full_name": "Dr. John Smith",
                    "role": "caregiver",
                    "organization_id": 2,  # General Hospital
                    "department": "General Medicine"
                },
                {
                    "username": "nurse1",
                    "email": "nurse1@general-hospital.hk",
                    "password": "nurse123",
                    "full_name": "Nurse Mary Johnson",
                    "role": "caregiver",
                    "organization_id": 2,  # General Hospital
                    "department": "Emergency"
                },
                {
                    "username": "patient1",
                    "email": "patient1@example.com",
                    "password": "patient123",
                    "full_name": "Patient Test User",
                    "role": "patient",
                    "organization_id": 2,  # General Hospital
                    "assigned_caregiver_id": None  # Will be set after doctor is created
                }
            ]
            
            # Create demo users
            for user_data in demo_users:
                hashed_password = get_password_hash(user_data["password"])
                
                db.execute(
                    text("""
                        INSERT INTO users (
                            email, username, hashed_password, full_name,
                            role, organization_id, department,
                            is_active, is_verified, is_admin, is_super_admin,
                            failed_login_attempts, created_at, updated_at
                        ) VALUES (
                            :email, :username, :hashed_password, :full_name,
                            :role, :organization_id, :department,
                            true, true, false, false,
                            0, NOW(), NOW()
                        )
                        ON CONFLICT (username) DO UPDATE SET
                            hashed_password = EXCLUDED.hashed_password,
                            updated_at = NOW()
                    """),
                    {
                        "email": user_data["email"],
                        "username": user_data["username"],
                        "hashed_password": hashed_password,
                        "full_name": user_data["full_name"],
                        "role": user_data["role"],
                        "organization_id": user_data["organization_id"],
                        "department": user_data.get("department")
                    }
                )
            
            db.commit()
            logger.info(f"✅ Demo users seeded: {len(demo_users)} users")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to seed demo users: {e}")
        return False


async def seed_assessment_rules() -> bool:
    """
    Seed default assessment rules for movement analysis from default_data.json.
    Creates system-wide rules (organization_id = NULL) that persist across rebuilds.
    
    Returns:
        bool: True if rules were seeded, False if they already exist or error occurred
    """
    try:
        import json
        from pathlib import Path
        from sqlalchemy import select
        from src.database.connection import get_async_session_context
        from src.movement_analysis.models import AssessmentRule
        
        # Load default rules from JSON file
        default_data_path = Path(__file__).parent.parent.parent / "scripts" / "seed_data" / "default_data.json"
        
        if not default_data_path.exists():
            logger.warning(f"Default data file not found: {default_data_path}")
            return False
        
        with open(default_data_path, 'r', encoding='utf-8') as f:
            default_data = json.load(f)
        
        rules_data = default_data.get("assessment_rules", [])
        
        if not rules_data:
            logger.info("No assessment rules found in default_data.json")
            return False
        
        async with get_async_session_context() as db:
            created_count = 0
            skipped_count = 0
            
            for rule_json in rules_data:
                # Check if rule already exists by category (system-wide rules)
                result = await db.execute(
                    select(AssessmentRule).where(
                        AssessmentRule.category == rule_json["category"],
                        AssessmentRule.organization_id.is_(None)
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Create new system-wide rule
                new_rule = AssessmentRule(
                    index_code=rule_json.get("index_code"),
                    category=rule_json["category"],
                    description=rule_json.get("description"),
                    ai_role=rule_json.get("ai_role"),
                    reference_video_url=rule_json.get("reference_video_url"),
                    reference_description=rule_json.get("reference_description"),
                    text_standards=rule_json.get("text_standards"),
                    analysis_instruction=rule_json.get("analysis_instruction"),
                    response_template=rule_json.get("response_template"),
                    is_active=rule_json.get("is_active", True),
                    created_by=rule_json.get("created_by"),  # Usually 1 (admin) or None (system)
                    organization_id=None  # System-wide rule
                )
                
                db.add(new_rule)
                created_count += 1
                logger.info(f"✅ Created assessment rule: {rule_json['category']}")
            
            await db.commit()
            
            if created_count > 0:
                logger.info(f"✅ Assessment rules seeded: {created_count} created, {skipped_count} skipped")
                return True
            else:
                logger.info(f"Assessment rules already exist ({skipped_count} rules), skipping seed")
                return False
                
    except Exception as e:
        logger.error(f"❌ Failed to seed assessment rules: {e}", exc_info=True)
        return False


async def seed_kb_categories() -> bool:
    """
    Seed KB categories (Age Groups, Categories, Topics) on startup.
    Creates the 3-level category structure if it doesn't exist.
    
    Returns:
        bool: True if categories were seeded, False if they already exist or error occurred
    """
    try:
        # Use sync session since we're doing simple inserts
        from src.database.connection import get_sync_session
        
        with get_sync_session() as db:
            # Check if categories already exist
            result = db.execute(
                text("SELECT COUNT(*) FROM kb_categories WHERE level = 1")
            )
            existing_count = result.scalar()
            
            if existing_count > 0:
                logger.info(f"KB categories already exist ({existing_count} age groups), skipping seed")
                return False
            
            logger.info("🌱 Seeding KB categories...")
            
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
                result = db.execute(
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
            
            # Level 2: Categories under Elderly (example structure)
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
                result = db.execute(
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
            
            # Level 3: Topics under Categories (example structure)
            topics = [
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
                db.execute(
                    text("""
                        INSERT INTO kb_categories 
                        (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                        VALUES (:name_en, :name_zh, :slug, :icon, :description_en, :description_zh, :level, :display_order, :parent_id)
                    """),
                    topic
                )
            
            db.commit()
            
            # Verify counts
            result = db.execute(text("SELECT COUNT(*) FROM kb_categories"))
            total = result.scalar()
            
            logger.info(f"✅ KB categories seeded: {total} categories (4 age groups, 2 categories, 3 topics)")
            return True
            
    except Exception as e:
        logger.error(f"❌ Failed to seed KB categories: {e}", exc_info=True)
        return False



async def seed_kb_documents() -> bool:
    """
    Seed default KB documents from kb_default_data.json.
    Creates categories and uploads documents with proper metadata.
    
    Returns:
        bool: True if documents were seeded, False if error occurred
    """
    try:
        import json
        from pathlib import Path
        from sqlalchemy import select, text
        from src.database.connection import get_async_session_context
        from src.knowledge_base.document_ingestion import DocumentIngestionService
        from src.knowledge_base.extractors import detect_and_extract
        
        # Load KB default data from JSON file
        kb_data_path = Path(__file__).parent.parent.parent / "scripts" / "seed_data" / "kb_default_data.json"
        
        if not kb_data_path.exists():
            logger.warning(f"KB default data file not found: {kb_data_path}")
            return False
        
        with open(kb_data_path, 'r', encoding='utf-8') as f:
            kb_data = json.load(f)
        
        categories_data = kb_data.get("kb_categories", [])
        documents_data = kb_data.get("kb_documents", [])
        
        if not categories_data and not documents_data:
            logger.info("No KB data found in kb_default_data.json")
            return False
        
        async with get_async_session_context() as db:
            # Step 1: Create categories
            category_id_map = {}  # slug -> id mapping
            created_categories = 0
            skipped_categories = 0
            
            # First, get existing "Elderly" parent category ID
            result = await db.execute(
                text("SELECT id FROM kb_categories WHERE slug = 'elderly' AND level = 1")
            )
            elderly_parent = result.fetchone()
            if not elderly_parent:
                logger.error("Elderly parent category not found. Run seed_kb_categories() first.")
                return False
            
            elderly_parent_id = elderly_parent[0]
            
            for cat_data in categories_data:
                slug = cat_data["slug"]
                
                # Check if category already exists
                result = await db.execute(
                    text("SELECT id FROM kb_categories WHERE slug = :slug"),
                    {"slug": slug}
                )
                existing = result.fetchone()
                
                if existing:
                    category_id_map[slug] = existing[0]
                    skipped_categories += 1
                    continue
                
                # Determine parent_id
                parent_id = None
                if cat_data["level"] == 2:
                    parent_id = elderly_parent_id
                elif cat_data["level"] == 3:
                    parent_slug = cat_data.get("parent_slug")
                    if parent_slug and parent_slug in category_id_map:
                        parent_id = category_id_map[parent_slug]
                    else:
                        # Try to find parent by slug
                        result = await db.execute(
                            text("SELECT id FROM kb_categories WHERE slug = :slug"),
                            {"slug": parent_slug}
                        )
                        parent_row = result.fetchone()
                        if parent_row:
                            parent_id = parent_row[0]
                            category_id_map[parent_slug] = parent_id
                
                # Get next display order
                result = await db.execute(
                    text("""
                        SELECT COALESCE(MAX(display_order), 0) + 1 as next_order
                        FROM kb_categories
                        WHERE parent_id = :parent_id OR (parent_id IS NULL AND :parent_id IS NULL)
                    """),
                    {"parent_id": parent_id}
                )
                next_order = result.scalar()
                
                # Create category
                result = await db.execute(
                    text("""
                        INSERT INTO kb_categories 
                        (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                        VALUES (:name_en, :name_zh, :slug, :icon, :description_en, :description_zh, :level, :display_order, :parent_id)
                        RETURNING id
                    """),
                    {
                        "name_en": cat_data["name_en"],
                        "name_zh": cat_data["name_zh"],
                        "slug": slug,
                        "icon": cat_data.get("icon", "📄"),
                        "description_en": cat_data.get("description_en", ""),
                        "description_zh": cat_data.get("description_zh", ""),
                        "level": cat_data["level"],
                        "display_order": next_order,
                        "parent_id": parent_id
                    }
                )
                new_id = result.fetchone()[0]
                category_id_map[slug] = new_id
                created_categories += 1
                logger.info(f"✅ Created KB category: {cat_data['name_zh']} ({slug})")
            
            await db.commit()
            
            if created_categories > 0:
                logger.info(f"✅ KB categories seeded: {created_categories} created, {skipped_categories} skipped")
            else:
                logger.info(f"KB categories already exist ({skipped_categories} categories), skipping")
            
            # Step 2: Upload documents
            ingestion_service = DocumentIngestionService()
            uploaded_count = 0
            skipped_count = 0
            error_count = 0
            
            for doc_data in documents_data:
                try:
                    file_path = Path(doc_data["file_path"])
                    
                    # Check if file exists
                    if not file_path.exists():
                        logger.warning(f"⚠️  File not found: {file_path}")
                        error_count += 1
                        continue
                    
                    # Get category ID
                    category_slug = doc_data.get("category_slug")
                    category_id = category_id_map.get(category_slug) if category_slug else None
                    
                    # Check if document already exists by title
                    result = await db.execute(
                        text("SELECT id FROM uploaded_documents WHERE title = :title"),
                        {"title": doc_data["title"]}
                    )
                    existing_doc = result.fetchone()
                    
                    if existing_doc:
                        skipped_count += 1
                        continue
                    
                    # Extract text from PDF
                    with open(file_path, 'rb') as f:
                        file_bytes = f.read()
                    
                    # detect_and_extract expects (filename: str, data: bytes)
                    extracted_text, metadata = detect_and_extract(file_path.name, file_bytes)
                    
                    if not extracted_text or len(extracted_text.strip()) < 50:
                        logger.warning(f"⚠️  Insufficient text extracted from: {file_path.name}")
                        error_count += 1
                        continue
                    
                    # Parse tags
                    tags_str = doc_data.get("tags", "")
                    tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                    
                    # BUGFIX: Detect form documents and add form metadata
                    # Check if document is a form by looking for form-related keywords in title, tags, or filename
                    is_form = False
                    form_type = None
                    
                    # Form detection keywords
                    form_keywords_en = ["form", "application", "registration"]
                    form_keywords_zh = ["表格", "申請表", "登記表"]
                    
                    # Check title
                    title_lower = doc_data["title"].lower()
                    if any(keyword in title_lower for keyword in form_keywords_en + form_keywords_zh):
                        is_form = True
                    
                    # Check tags
                    tags_lower = tags_str.lower()
                    if any(keyword in tags_lower for keyword in form_keywords_en + form_keywords_zh):
                        is_form = True
                    
                    # Check filename
                    filename_lower = file_path.name.lower()
                    if any(keyword in filename_lower for keyword in form_keywords_en + form_keywords_zh):
                        is_form = True
                    
                    # Determine form type based on category or title
                    if is_form:
                        if "elder" in title_lower or "樂悠" in doc_data["title"]:
                            form_type = "elder_card"
                        elif "cssa" in tags_lower or "綜援" in doc_data["title"]:
                            form_type = "cssa"
                        elif "voucher" in tags_lower or "服務券" in doc_data["title"]:
                            form_type = "care_voucher"
                        elif "allowance" in tags_lower or "津貼" in doc_data["title"]:
                            form_type = "allowance"
                        else:
                            form_type = "general"
                        
                        logger.info(f"📋 Detected form document: {doc_data['title']} (type: {form_type})")
                    
                    # Ingest document
                    result = await ingestion_service.ingest_document(
                        title=doc_data["title"],
                        content=extracted_text,
                        category=category_slug or "general",
                        category_id=category_id,
                        language=doc_data.get("language", "zh-HK"),
                        tags=tags_list,
                        auto_tag=False,
                        auto_summary=False,
                        visibility=doc_data.get("visibility", "public"),
                        organization_id=doc_data.get("organization_id"),
                        source=f"Seed: {file_path.name}",
                        metadata={
                            "title_en": doc_data.get("title_en", ""),
                            "description": doc_data.get("description", ""),
                            "file_path": str(file_path),
                            "filename": file_path.name,
                            "file_size": len(file_bytes),
                            "content_type": "application/pdf",
                            # BUGFIX: Add form metadata for form delivery
                            "is_form": is_form,
                            "form_type": form_type if is_form else None
                        }
                    )
                    
                    uploaded_count += 1
                    logger.info(f"✅ Uploaded document: {doc_data['title']}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to upload {doc_data.get('title', 'unknown')}: {e}")
                    error_count += 1
                    continue
            
            await db.commit()
            
            logger.info(f"✅ KB documents seeded: {uploaded_count} uploaded, {skipped_count} skipped, {error_count} errors")
            return uploaded_count > 0
                
    except Exception as e:
        logger.error(f"❌ Failed to seed KB documents: {e}", exc_info=True)
        return False
