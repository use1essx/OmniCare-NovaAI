"""
Category Navigator for KB Tree Navigation

Intelligent category navigation for conversational AI.
Detects user intent and navigates the category tree to provide
natural clarification questions without exposing KB structure.

CRITICAL RULES:
- NEVER expose document counts to users
- NEVER reveal KB structure or category IDs
- NEVER say "I found X documents"
- Ask natural clarification questions based on category hierarchy
- Suggest related topics naturally
"""

import re
from typing import Optional, Dict, Any, List
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_base.category_service import get_category_service, CategoryService

logger = logging.getLogger(__name__)


class CategoryNavigator:
    """
    Intelligent category navigation for conversational AI.
    Detects user intent and navigates the category tree.
    """
    
    def __init__(self, category_service: Optional[CategoryService] = None):
        """
        Initialize category navigator.
        
        Args:
            category_service: CategoryService instance (uses singleton if None)
        """
        self.category_service = category_service or get_category_service()
    
    async def analyze_query(
        self,
        query: str,
        language: str,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """
        Analyze user query and determine navigation strategy.
        
        Args:
            query: User query text
            language: Query language (en or zh-HK)
            db: Database session
            
        Returns:
            {
                "query_type": "vague" | "parent_category" | "specific_topic" | "general",
                "detected_category": {...} or None,
                "suggested_action": "overview" | "list_children" | "answer" | "clarify",
                "children": [...],
                "siblings": [...],
                "parent": {...} or None
            }
        """
        try:
            # Detect category from query
            category = await self.category_service.detect_category_from_query(
                db, query, language
            )
            
            if not category:
                logger.debug(f"No category detected for query: {query}")
                return {
                    "query_type": "general",
                    "detected_category": None,
                    "suggested_action": "answer",
                    "children": [],
                    "siblings": [],
                    "parent": None
                }
            
            logger.info(f"Detected category: {category['name_zh']} (ID: {category['id']})")
            
            # Get category context
            children = await self.category_service.get_category_children(
                db, category["id"]
            )
            
            # Determine query type based on category level and children
            if len(children) > 0:
                # Parent category with children
                if self._is_very_vague(query):
                    logger.debug(f"Very vague query detected: {query}")
                    return {
                        "query_type": "vague",
                        "detected_category": category,
                        "suggested_action": "overview",
                        "children": children,
                        "siblings": [],
                        "parent": None
                    }
                else:
                    logger.debug(f"Parent category query detected: {query}")
                    return {
                        "query_type": "parent_category",
                        "detected_category": category,
                        "suggested_action": "list_children",
                        "children": children,
                        "siblings": [],
                        "parent": None
                    }
            else:
                # Leaf category (specific topic)
                path = await self.category_service.get_category_path(
                    db, category["id"]
                )
                siblings = await self.category_service.get_category_siblings(
                    db, category["id"]
                )
                
                parent = path[-2] if len(path) > 1 else None
                
                logger.debug(f"Specific topic query detected: {query}")
                return {
                    "query_type": "specific_topic",
                    "detected_category": category,
                    "suggested_action": "answer",
                    "children": [],
                    "siblings": siblings,
                    "parent": parent
                }
                
        except Exception as e:
            logger.error(f"Error analyzing query: {e}", exc_info=True)
            return {
                "query_type": "general",
                "detected_category": None,
                "suggested_action": "answer",
                "children": [],
                "siblings": [],
                "parent": None
            }
    
    def _is_very_vague(self, query: str) -> bool:
        """
        Detect if query is very vague (e.g., "我想知道長者" vs "我想知道長者服務").
        
        Very vague queries are short and lack specific keywords.
        
        Args:
            query: User query text
            
        Returns:
            True if query is very vague, False otherwise
        """
        # Very short queries without specific keywords
        vague_patterns = [
            r"^我想知道\s*[\u4e00-\u9fff]{1,3}$",  # "我想知道X" where X is 1-3 chars
            r"^tell me about\s+\w{1,10}$",  # "tell me about X" where X is short
            r"^關於\s*[\u4e00-\u9fff]{1,3}$",  # "關於X"
            r"^about\s+\w{1,10}$",  # "about X"
            r"^[\u4e00-\u9fff]{1,3}$",  # Just 1-3 Chinese characters
            r"^\w{1,10}$",  # Just 1-10 English characters
        ]
        
        query_stripped = query.strip()
        
        for pattern in vague_patterns:
            if re.search(pattern, query_stripped, re.IGNORECASE):
                return True
        
        return False
    
    def generate_clarification_prompt(
        self,
        navigation_result: Dict[str, Any],
        language: str
    ) -> str:
        """
        Generate natural clarification question based on navigation result.
        
        IMPORTANT: Never expose KB structure or document counts!
        
        Args:
            navigation_result: Result from analyze_query()
            language: Response language (en or zh-HK)
            
        Returns:
            Natural clarification prompt (empty string if no clarification needed)
        """
        query_type = navigation_result["query_type"]
        category = navigation_result.get("detected_category")
        children = navigation_result.get("children", [])
        
        if not category:
            return ""
        
        try:
            if query_type == "vague":
                # Very vague query → overview + list options
                return self._generate_overview_prompt(category, children, language)
            
            elif query_type == "parent_category":
                # Parent category → list children
                return self._generate_list_children_prompt(category, children, language)
            
            elif query_type == "specific_topic":
                # Specific topic → suggest parent or siblings
                parent = navigation_result.get("parent")
                siblings = navigation_result.get("siblings", [])
                return self._generate_related_topics_prompt(category, parent, siblings, language)
            
            return ""
            
        except Exception as e:
            logger.error(f"Error generating clarification prompt: {e}", exc_info=True)
            return ""
    
    def _generate_overview_prompt(
        self,
        category: Dict[str, Any],
        children: List[Dict[str, Any]],
        language: str
    ) -> str:
        """Generate overview prompt for very vague queries"""
        if language == "zh-HK":
            category_name = category["name_zh"]
            desc = category.get("description_zh", "")
            
            # Build overview
            if desc:
                overview = f"{category_name}{desc}，包括多種政府服務同福利。\n\n你想知道更多關於："
            else:
                overview = f"{category_name}可以享用多種政府服務同福利，包括醫療、交通、經濟援助等等。\n\n你想知道更多關於："
            
            # List options (limit to 5)
            options = []
            for child in children[:5]:
                name = child["name_zh"]
                desc = child.get("description_zh", "")
                icon = child.get("icon", "")
                
                if desc:
                    options.append(f"{icon} {name}（{desc}）")
                else:
                    options.append(f"{icon} {name}")
            
            return overview + "\n- " + "\n- ".join(options) + "\n\n邊一方面？"
        
        else:
            # English version
            category_name = category["name_en"]
            desc = category.get("description_en", "")
            
            if desc:
                overview = f"{category_name} {desc}. There are various government services and benefits available.\n\nWhich aspect would you like to know more about:"
            else:
                overview = f"There are various government services and benefits available for {category_name.lower()}, including medical, transportation, financial assistance, and more.\n\nWhich aspect would you like to know more about:"
            
            options = []
            for child in children[:5]:
                name = child["name_en"]
                desc = child.get("description_en", "")
                icon = child.get("icon", "")
                
                if desc:
                    options.append(f"{icon} {name} ({desc})")
                else:
                    options.append(f"{icon} {name}")
            
            return overview + "\n- " + "\n- ".join(options)
    
    def _generate_list_children_prompt(
        self,
        category: Dict[str, Any],
        children: List[Dict[str, Any]],
        language: str
    ) -> str:
        """Generate prompt listing child categories"""
        if language == "zh-HK":
            child_names = [c["name_zh"] for c in children[:4]]
            
            if len(children) > 4:
                return f"你想知道更多關於{child_names[0]}、{child_names[1]}、{child_names[2]}定係其他？"
            elif len(children) == 3:
                return f"你想知道更多關於{child_names[0]}、{child_names[1]}定係{child_names[2]}？"
            elif len(children) == 2:
                return f"你想知道更多關於{child_names[0]}定係{child_names[1]}？"
            else:
                return f"你想知道更多關於{child_names[0]}嗎？"
        
        else:
            # English version
            child_names = [c["name_en"] for c in children[:4]]
            
            if len(children) > 4:
                return f"Would you like to know more about {', '.join(child_names[:-1])}, {child_names[-1]}, or others?"
            elif len(children) == 3:
                return f"Would you like to know more about {child_names[0]}, {child_names[1]}, or {child_names[2]}?"
            elif len(children) == 2:
                return f"Would you like to know more about {child_names[0]} or {child_names[1]}?"
            else:
                return f"Would you like to know more about {child_names[0]}?"
    
    def _generate_related_topics_prompt(
        self,
        category: Dict[str, Any],
        parent: Optional[Dict[str, Any]],
        siblings: List[Dict[str, Any]],
        language: str
    ) -> str:
        """Generate prompt suggesting related topics"""
        # For specific topics, suggest parent or siblings
        if parent and language == "zh-HK":
            return f"\n\n你想知道更多關於{parent['name_zh']}嗎？"
        elif parent:
            return f"\n\nWould you like to know more about {parent['name_en']}?"
        
        # If no parent but has siblings, suggest siblings
        if siblings and language == "zh-HK":
            sibling_names = [s["name_zh"] for s in siblings[:3]]
            if len(sibling_names) > 1:
                return f"\n\n你可能都想知道{sibling_names[0]}或者{sibling_names[1]}？"
            else:
                return f"\n\n你可能都想知道{sibling_names[0]}？"
        elif siblings:
            sibling_names = [s["name_en"] for s in siblings[:3]]
            if len(sibling_names) > 1:
                return f"\n\nYou might also be interested in {sibling_names[0]} or {sibling_names[1]}?"
            else:
                return f"\n\nYou might also be interested in {sibling_names[0]}?"
        
        return ""


# Singleton instance
_category_navigator = None


def get_category_navigator() -> CategoryNavigator:
    """Get singleton CategoryNavigator instance"""
    global _category_navigator
    if _category_navigator is None:
        _category_navigator = CategoryNavigator()
    return _category_navigator
