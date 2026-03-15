"""
Category Service for KB Tree Navigation

Provides hierarchical category management and tree navigation for organizing
knowledge base documents.

Features:
- Tree traversal (get children, siblings, path)
- Category detection from user queries (fuzzy matching)
- Document-category relationships
- Caching for performance
"""

import re
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class CategoryService:
    """
    Service for managing KB category tree.
    
    Provides methods for:
    - Tree navigation (children, siblings, path)
    - Category detection from queries
    - Document-category relationships
    """
    
    def __init__(self):
        """Initialize category service with caching"""
        self._cache = {}
        self._cache_ttl = timedelta(minutes=30)  # Cache for 30 minutes
        self._last_cache_clear = datetime.utcnow()
    
    def _clear_cache_if_needed(self):
        """Clear cache if TTL expired"""
        if datetime.utcnow() - self._last_cache_clear > self._cache_ttl:
            self._cache.clear()
            self._last_cache_clear = datetime.utcnow()
            logger.debug("Category cache cleared")
    
    async def get_category_tree(
        self,
        db: AsyncSession,
        parent_id: Optional[int] = None,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Get category tree starting from parent_id.
        
        Args:
            db: Database session
            parent_id: Parent category ID (None for root categories)
            max_depth: Maximum depth to traverse
            
        Returns:
            List of category dicts with nested children
        """
        self._clear_cache_if_needed()
        
        cache_key = f"tree_{parent_id}_{max_depth}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            # Get categories at this level
            if parent_id is None:
                # Get root categories
                result = await db.execute(
                    text("""
                        SELECT 
                            id, name_en, name_zh, slug, icon,
                            description_en, description_zh,
                            level, display_order, parent_id
                        FROM kb_categories
                        WHERE parent_id IS NULL
                        ORDER BY display_order, id
                    """)
                )
            else:
                # Get children of specific parent
                result = await db.execute(
                    text("""
                        SELECT 
                            id, name_en, name_zh, slug, icon,
                            description_en, description_zh,
                            level, display_order, parent_id
                        FROM kb_categories
                        WHERE parent_id = :parent_id
                        ORDER BY display_order, id
                    """),
                    {"parent_id": parent_id}
                )
            
            categories = []
            for row in result:
                cat = {
                    "id": row.id,
                    "name_en": row.name_en,
                    "name_zh": row.name_zh,
                    "slug": row.slug,
                    "icon": row.icon,
                    "description_en": row.description_en,
                    "description_zh": row.description_zh,
                    "level": row.level,
                    "display_order": row.display_order,
                    "parent_id": row.parent_id,
                }
                
                # Recursively get children if not at max depth
                if row.level < max_depth:
                    cat["children"] = await self.get_category_tree(
                        db, row.id, max_depth
                    )
                else:
                    cat["children"] = []
                
                categories.append(cat)
            
            self._cache[cache_key] = categories
            return categories
            
        except Exception as e:
            logger.error(f"Error getting category tree: {e}")
            return []
    
    async def get_category_by_slug(
        self,
        db: AsyncSession,
        slug: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get category by slug.
        
        Args:
            db: Database session
            slug: Category slug (e.g., "elderly-services")
            
        Returns:
            Category dict or None
        """
        cache_key = f"slug_{slug}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            result = await db.execute(
                text("""
                    SELECT 
                        id, name_en, name_zh, slug, icon,
                        description_en, description_zh,
                        level, display_order, parent_id
                    FROM kb_categories
                    WHERE slug = :slug
                """),
                {"slug": slug}
            )
            
            row = result.fetchone()
            if not row:
                return None
            
            category = {
                "id": row.id,
                "name_en": row.name_en,
                "name_zh": row.name_zh,
                "slug": row.slug,
                "icon": row.icon,
                "description_en": row.description_en,
                "description_zh": row.description_zh,
                "level": row.level,
                "display_order": row.display_order,
                "parent_id": row.parent_id,
            }
            
            self._cache[cache_key] = category
            return category
            
        except Exception as e:
            logger.error(f"Error getting category by slug {slug}: {e}")
            return None
    
    async def get_category_by_id(
        self,
        db: AsyncSession,
        category_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get category by ID.
        
        Args:
            db: Database session
            category_id: Category ID
            
        Returns:
            Category dict or None
        """
        cache_key = f"id_{category_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            result = await db.execute(
                text("""
                    SELECT 
                        id, name_en, name_zh, slug, icon,
                        description_en, description_zh,
                        level, display_order, parent_id
                    FROM kb_categories
                    WHERE id = :id
                """),
                {"id": category_id}
            )
            
            row = result.fetchone()
            if not row:
                return None
            
            category = {
                "id": row.id,
                "name_en": row.name_en,
                "name_zh": row.name_zh,
                "slug": row.slug,
                "icon": row.icon,
                "description_en": row.description_en,
                "description_zh": row.description_zh,
                "level": row.level,
                "display_order": row.display_order,
                "parent_id": row.parent_id,
            }
            
            self._cache[cache_key] = category
            return category
            
        except Exception as e:
            logger.error(f"Error getting category by ID {category_id}: {e}")
            return None
    
    async def get_category_children(
        self,
        db: AsyncSession,
        category_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get direct children of a category.
        
        Args:
            db: Database session
            category_id: Parent category ID
            
        Returns:
            List of child category dicts
        """
        cache_key = f"children_{category_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            result = await db.execute(
                text("""
                    SELECT 
                        id, name_en, name_zh, slug, icon,
                        description_en, description_zh,
                        level, display_order, parent_id
                    FROM kb_categories
                    WHERE parent_id = :parent_id
                    ORDER BY display_order, id
                """),
                {"parent_id": category_id}
            )
            
            children = []
            for row in result:
                children.append({
                    "id": row.id,
                    "name_en": row.name_en,
                    "name_zh": row.name_zh,
                    "slug": row.slug,
                    "icon": row.icon,
                    "description_en": row.description_en,
                    "description_zh": row.description_zh,
                    "level": row.level,
                    "display_order": row.display_order,
                    "parent_id": row.parent_id,
                })
            
            self._cache[cache_key] = children
            return children
            
        except Exception as e:
            logger.error(f"Error getting children for category {category_id}: {e}")
            return []
    
    async def get_category_path(
        self,
        db: AsyncSession,
        category_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get full path from root to category (breadcrumb).
        
        Args:
            db: Database session
            category_id: Category ID
            
        Returns:
            List of category dicts from root to target (ordered)
        """
        try:
            # Use recursive CTE to get path
            result = await db.execute(
                text("""
                    WITH RECURSIVE category_path AS (
                        -- Base case: start with target category
                        SELECT 
                            id, name_en, name_zh, slug, icon,
                            description_en, description_zh,
                            level, display_order, parent_id,
                            0 as depth
                        FROM kb_categories
                        WHERE id = :category_id
                        
                        UNION ALL
                        
                        -- Recursive case: get parent
                        SELECT 
                            c.id, c.name_en, c.name_zh, c.slug, c.icon,
                            c.description_en, c.description_zh,
                            c.level, c.display_order, c.parent_id,
                            cp.depth + 1
                        FROM kb_categories c
                        INNER JOIN category_path cp ON c.id = cp.parent_id
                    )
                    SELECT * FROM category_path
                    ORDER BY depth DESC
                """),
                {"category_id": category_id}
            )
            
            path = []
            for row in result:
                path.append({
                    "id": row.id,
                    "name_en": row.name_en,
                    "name_zh": row.name_zh,
                    "slug": row.slug,
                    "icon": row.icon,
                    "description_en": row.description_en,
                    "description_zh": row.description_zh,
                    "level": row.level,
                    "display_order": row.display_order,
                    "parent_id": row.parent_id,
                })
            
            return path
            
        except Exception as e:
            logger.error(f"Error getting path for category {category_id}: {e}")
            return []
    
    async def get_category_siblings(
        self,
        db: AsyncSession,
        category_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get sibling categories (same parent).
        
        Args:
            db: Database session
            category_id: Category ID
            
        Returns:
            List of sibling category dicts (excluding self)
        """
        try:
            # First get the category to find its parent
            category = await self.get_category_by_id(db, category_id)
            if not category:
                return []
            
            parent_id = category["parent_id"]
            
            # Get all children of the same parent (excluding self)
            if parent_id is None:
                # Get root-level siblings
                result = await db.execute(
                    text("""
                        SELECT 
                            id, name_en, name_zh, slug, icon,
                            description_en, description_zh,
                            level, display_order, parent_id
                        FROM kb_categories
                        WHERE parent_id IS NULL AND id != :category_id
                        ORDER BY display_order, id
                    """),
                    {"category_id": category_id}
                )
            else:
                # Get siblings with same parent
                result = await db.execute(
                    text("""
                        SELECT 
                            id, name_en, name_zh, slug, icon,
                            description_en, description_zh,
                            level, display_order, parent_id
                        FROM kb_categories
                        WHERE parent_id = :parent_id AND id != :category_id
                        ORDER BY display_order, id
                    """),
                    {"parent_id": parent_id, "category_id": category_id}
                )
            
            siblings = []
            for row in result:
                siblings.append({
                    "id": row.id,
                    "name_en": row.name_en,
                    "name_zh": row.name_zh,
                    "slug": row.slug,
                    "icon": row.icon,
                    "description_en": row.description_en,
                    "description_zh": row.description_zh,
                    "level": row.level,
                    "display_order": row.display_order,
                    "parent_id": row.parent_id,
                })
            
            return siblings
            
        except Exception as e:
            logger.error(f"Error getting siblings for category {category_id}: {e}")
            return []
    
    async def get_documents_in_category(
        self,
        db: AsyncSession,
        category_id: int,
        include_subcategories: bool = True
    ) -> List[int]:
        """
        Get all document IDs in a category (and optionally subcategories).
        
        Args:
            db: Database session
            category_id: Category ID
            include_subcategories: Include documents from child categories
            
        Returns:
            List of document IDs
        """
        try:
            if include_subcategories:
                # Get all descendant categories using recursive CTE
                result = await db.execute(
                    text("""
                        WITH RECURSIVE category_tree AS (
                            -- Base case: start with target category
                            SELECT id FROM kb_categories WHERE id = :category_id
                            
                            UNION ALL
                            
                            -- Recursive case: get children
                            SELECT c.id
                            FROM kb_categories c
                            INNER JOIN category_tree ct ON c.parent_id = ct.id
                        )
                        SELECT DISTINCT kd.id
                        FROM knowledge_documents kd
                        WHERE kd.category_id IN (SELECT id FROM category_tree)
                           OR EXISTS (
                               SELECT 1 FROM document_category_tags dct
                               WHERE dct.document_id = kd.id
                               AND dct.category_id IN (SELECT id FROM category_tree)
                           )
                    """),
                    {"category_id": category_id}
                )
            else:
                # Just this category
                result = await db.execute(
                    text("""
                        SELECT DISTINCT kd.id
                        FROM knowledge_documents kd
                        WHERE kd.category_id = :category_id
                           OR EXISTS (
                               SELECT 1 FROM document_category_tags dct
                               WHERE dct.document_id = kd.id
                               AND dct.category_id = :category_id
                           )
                    """),
                    {"category_id": category_id}
                )
            
            doc_ids = [row.id for row in result]
            return doc_ids
            
        except Exception as e:
            logger.error(f"Error getting documents for category {category_id}: {e}")
            return []
    
    async def detect_category_from_query(
        self,
        db: AsyncSession,
        query: str,
        language: str = "zh-HK"
    ) -> Optional[Dict[str, Any]]:
        """
        Detect which category the user query is about.
        Uses fuzzy matching on category names and descriptions.
        
        Args:
            db: Database session
            query: User query text
            language: Query language (en or zh-HK)
            
        Returns:
            Best matching category dict or None
        """
        try:
            # Extract keywords from query
            query_lower = query.lower()
            
            # Remove common filler words
            stop_words_en = {"about", "tell", "me", "want", "know", "what", "is", "are", "the", "a", "an"}
            stop_words_zh = {"我", "想", "知道", "關於", "係", "嘅", "啲", "有", "咩"}
            
            # Extract potential category keywords
            # For Chinese: extract 2+ character sequences
            zh_keywords = re.findall(r'[\u4e00-\u9fff]{2,}', query)
            # For English: extract words
            en_keywords = [w for w in re.findall(r'[a-zA-Z]{3,}', query_lower) if w not in stop_words_en]
            
            keywords = zh_keywords + en_keywords
            if not keywords:
                return None
            
            # Search for matching categories
            # Use ILIKE for case-insensitive partial matching
            name_field = "name_zh" if language == "zh-HK" else "name_en"
            desc_field = "description_zh" if language == "zh-HK" else "description_en"
            
            best_match = None
            best_score = 0
            
            for keyword in keywords:
                result = await db.execute(
                    text(f"""
                        SELECT 
                            id, name_en, name_zh, slug, icon,
                            description_en, description_zh,
                            level, display_order, parent_id,
                            CASE
                                WHEN {name_field} ILIKE :exact THEN 100
                                WHEN {name_field} ILIKE :keyword THEN 80
                                WHEN {desc_field} ILIKE :keyword THEN 60
                                WHEN slug ILIKE :keyword THEN 40
                                ELSE 0
                            END as score
                        FROM kb_categories
                        WHERE {name_field} ILIKE :keyword
                           OR {desc_field} ILIKE :keyword
                           OR slug ILIKE :keyword
                        ORDER BY score DESC, level ASC
                        LIMIT 1
                    """),
                    {
                        "keyword": f"%{keyword}%",
                        "exact": keyword
                    }
                )
                
                row = result.fetchone()
                if row and row.score > best_score:
                    best_score = row.score
                    best_match = {
                        "id": row.id,
                        "name_en": row.name_en,
                        "name_zh": row.name_zh,
                        "slug": row.slug,
                        "icon": row.icon,
                        "description_en": row.description_en,
                        "description_zh": row.description_zh,
                        "level": row.level,
                        "display_order": row.display_order,
                        "parent_id": row.parent_id,
                        "match_score": row.score,
                    }
            
            return best_match if best_score >= 40 else None
            
        except Exception as e:
            logger.error(f"Error detecting category from query: {e}")
            return None


# Singleton instance
_category_service = None


def get_category_service() -> CategoryService:
    """Get singleton CategoryService instance"""
    global _category_service
    if _category_service is None:
        _category_service = CategoryService()
    return _category_service
