"""
Healthcare AI V2 - Movement Analysis Rules Service
Business logic for managing movement analysis rules
"""

import logging
from typing import Dict, Any, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models_comprehensive import User
from .models import AssessmentRule
from .schemas import AssessmentRuleCreate, AssessmentRuleUpdate
from .access_control import can_manage_assessment_rules, is_super_admin, is_org_admin

logger = logging.getLogger(__name__)


class AssessmentRulesService:
    """
    Service for managing assessment rules CRUD operations
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_rule(
        self,
        rule_data: AssessmentRuleCreate,
        current_user: User
    ) -> AssessmentRule:
        """
        Create a new assessment rule
        
        Args:
            rule_data: Rule creation data
            current_user: User creating the rule
            
        Returns:
            Created AssessmentRule
            
        Raises:
            PermissionError: If user cannot create rules
            ValueError: If validation fails
        """
        if not can_manage_assessment_rules(current_user):
            raise PermissionError("You don't have permission to create assessment rules")
        
        # Check for duplicate index_code
        if rule_data.index_code:
            existing = await self.db.execute(
                select(AssessmentRule).where(AssessmentRule.index_code == rule_data.index_code)
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Rule with index_code '{rule_data.index_code}' already exists")
        
        # Determine organization_id
        org_id = None
        if not is_super_admin(current_user):
            # Non-super admins create org-scoped rules
            org_id = getattr(current_user, "organization_id", None)
        
        rule = AssessmentRule(
            index_code=rule_data.index_code,
            category=rule_data.category,
            description=rule_data.description,
            ai_role=rule_data.ai_role,
            reference_video_url=rule_data.reference_video_url,
            reference_description=rule_data.reference_description,
            text_standards=rule_data.text_standards,
            analysis_instruction=rule_data.analysis_instruction,
            response_template=rule_data.response_template,
            is_active=rule_data.is_active,
            created_by=current_user.id,
            organization_id=org_id
        )
        
        self.db.add(rule)
        await self.db.commit()
        await self.db.refresh(rule)
        
        logger.info(f"Created assessment rule {rule.id}: {rule.category} by user {current_user.id}")
        return rule
    
    async def update_rule(
        self,
        rule_id: int,
        rule_data: AssessmentRuleUpdate,
        current_user: User
    ) -> Optional[AssessmentRule]:
        """
        Update an existing assessment rule
        
        Args:
            rule_id: Rule ID to update
            rule_data: Update data
            current_user: User making the update
            
        Returns:
            Updated AssessmentRule or None if not found
            
        Raises:
            PermissionError: If user cannot update this rule
        """
        if not can_manage_assessment_rules(current_user):
            raise PermissionError("You don't have permission to update assessment rules")
        
        rule = await self._get_rule_with_access_check(rule_id, current_user)
        if not rule:
            return None
        
        # Update fields that are provided
        update_data = rule_data.model_dump(exclude_unset=True)
        
        # Check for duplicate index_code if being changed
        if "index_code" in update_data and update_data["index_code"] != rule.index_code:
            existing = await self.db.execute(
                select(AssessmentRule).where(
                    AssessmentRule.index_code == update_data["index_code"],
                    AssessmentRule.id != rule_id
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError(f"Rule with index_code '{update_data['index_code']}' already exists")
        
        for field, value in update_data.items():
            setattr(rule, field, value)
        
        await self.db.commit()
        await self.db.refresh(rule)
        
        logger.info(f"Updated assessment rule {rule_id} by user {current_user.id}")
        return rule
    
    async def delete_rule(
        self,
        rule_id: int,
        current_user: User
    ) -> bool:
        """
        Delete an assessment rule
        
        Args:
            rule_id: Rule ID to delete
            current_user: User making the deletion
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            PermissionError: If user cannot delete this rule
        """
        if not can_manage_assessment_rules(current_user):
            raise PermissionError("You don't have permission to delete assessment rules")
        
        rule = await self._get_rule_with_access_check(rule_id, current_user)
        if not rule:
            return False
        
        await self.db.delete(rule)
        await self.db.commit()
        
        logger.info(f"Deleted assessment rule {rule_id} by user {current_user.id}")
        return True
    
    async def get_rule(
        self,
        rule_id: int,
        current_user: Optional[User] = None
    ) -> Optional[AssessmentRule]:
        """
        Get a single rule by ID
        
        Args:
            rule_id: Rule ID
            current_user: Optional user for access check
            
        Returns:
            AssessmentRule or None
        """
        result = await self.db.execute(
            select(AssessmentRule).where(AssessmentRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if not rule:
            return None
        
        # Check visibility
        if current_user and not await self._can_view_rule(rule, current_user):
            return None
        
        return rule
    
    async def list_rules(
        self,
        current_user: Optional[User] = None,
        page: int = 1,
        limit: int = 50,
        active_only: bool = True,
        category_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List assessment rules with pagination
        
        Args:
            current_user: User making request (for access control)
            page: Page number (1-indexed)
            limit: Items per page
            active_only: Only return active rules
            category_filter: Filter by category
            
        Returns:
            Paginated list of rules
        """
        # Build query
        query = select(AssessmentRule)
        
        # Apply filters
        conditions = []
        
        if active_only:
            conditions.append(AssessmentRule.is_active)
        
        if category_filter:
            conditions.append(AssessmentRule.category.ilike(f"%{category_filter}%"))
        
        # Apply organization scoping
        if current_user:
            if not is_super_admin(current_user):
                org_id = getattr(current_user, "organization_id", None)
                # Show system-wide rules (org_id=NULL) + org-specific rules
                from sqlalchemy import or_
                conditions.append(
                    or_(
                        AssessmentRule.organization_id.is_(None),
                        AssessmentRule.organization_id == org_id
                    )
                )
        else:
            # Anonymous: only system-wide rules
            conditions.append(AssessmentRule.organization_id.is_(None))
        
        for condition in conditions:
            query = query.where(condition)
        
        # Order by category
        query = query.order_by(AssessmentRule.category, AssessmentRule.index_code)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)
        
        # Execute
        result = await self.db.execute(query)
        rules = result.scalars().all()
        
        return {
            "rules": [rule.to_dict() for rule in rules],
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit if total > 0 else 0
        }
    
    async def get_active_rules(
        self,
        current_user: Optional[User] = None
    ) -> List[AssessmentRule]:
        """
        Get all active rules (for dropdown selection)
        
        Args:
            current_user: User for access control
            
        Returns:
            List of active rules
        """
        query = select(AssessmentRule).where(AssessmentRule.is_active)
        
        # Apply organization scoping
        if current_user and not is_super_admin(current_user):
            from sqlalchemy import or_
            org_id = getattr(current_user, "organization_id", None)
            query = query.where(
                or_(
                    AssessmentRule.organization_id.is_(None),
                    AssessmentRule.organization_id == org_id
                )
            )
        elif not current_user:
            query = query.where(AssessmentRule.organization_id.is_(None))
        
        query = query.order_by(AssessmentRule.category)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def toggle_rule_active(
        self,
        rule_id: int,
        is_active: bool,
        current_user: User
    ) -> Optional[AssessmentRule]:
        """
        Toggle rule active status
        
        Args:
            rule_id: Rule ID
            is_active: New active status
            current_user: User making the change
            
        Returns:
            Updated rule or None if not found
        """
        if not can_manage_assessment_rules(current_user):
            raise PermissionError("You don't have permission to modify assessment rules")
        
        rule = await self._get_rule_with_access_check(rule_id, current_user)
        if not rule:
            return None
        
        rule.is_active = is_active
        await self.db.commit()
        await self.db.refresh(rule)
        
        logger.info(f"{'Activated' if is_active else 'Deactivated'} rule {rule_id} by user {current_user.id}")
        return rule
    
    async def _get_rule_with_access_check(
        self,
        rule_id: int,
        current_user: User
    ) -> Optional[AssessmentRule]:
        """
        Get rule with permission check for editing
        """
        result = await self.db.execute(
            select(AssessmentRule).where(AssessmentRule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if not rule:
            return None
        
        # Super admin can edit any rule
        if is_super_admin(current_user):
            return rule
        
        # Org admin can edit their org's rules and system rules
        if is_org_admin(current_user):
            if rule.organization_id is None or rule.organization_id == current_user.organization_id:
                return rule
        
        # Staff can only edit rules they created
        if rule.created_by == current_user.id:
            return rule
        
        # Cannot edit other org's rules
        raise PermissionError("You don't have permission to edit this rule")
    
    async def _can_view_rule(
        self,
        rule: AssessmentRule,
        current_user: User
    ) -> bool:
        """
        Check if user can view a rule
        """
        # Super admin sees all
        if is_super_admin(current_user):
            return True
        
        # System-wide rules are visible to all
        if rule.organization_id is None:
            return True
        
        # Org-specific rules visible to same org
        user_org = getattr(current_user, "organization_id", None)
        return rule.organization_id == user_org

