"""
Healthcare AI V2 Admin User Service
Business logic for user management operations
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from sqlalchemy import text, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models_comprehensive import User
from src.security.auth import get_password_hash

logger = logging.getLogger(__name__)


class UserService:
    """Service for user management operations"""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
    
    async def list_users(
        self, 
        page: int = 1, 
        limit: int = 10, 
        search: Optional[str] = None,
        role_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        organization_id: Optional[int] = None,
        requesting_user: Optional[User] = None
    ) -> Dict[str, Any]:
        """List users with pagination, filtering, and org scoping"""
        try:
            # Build base query
            query = select(User)
            
            # Apply filters
            conditions = []
            
            # Organization scoping - CRITICAL SECURITY FILTER
            if organization_id is not None:
                conditions.append(User.organization_id == organization_id)
            
            if search:
                search_condition = text("""
                    username ILIKE :search OR 
                    email ILIKE :search OR 
                    full_name ILIKE :search
                """)
                conditions.append(search_condition)
            
            if role_filter:
                conditions.append(User.role == role_filter)
            
            if status_filter:
                if status_filter == "active":
                    conditions.append(User.is_active)
                elif status_filter == "inactive":
                    conditions.append(not User.is_active)
            
            # Apply conditions
            for condition in conditions:
                query = query.where(condition)
            
            # Apply sorting
            if hasattr(User, sort_by):
                sort_column = getattr(User, sort_by)
                if sort_order.lower() == "desc":
                    query = query.order_by(sort_column.desc())
                else:
                    query = query.order_by(sort_column.asc())
            
            # Get total count
            count_query = select(text("COUNT(*)")).select_from(User)
            for condition in conditions:
                count_query = count_query.where(condition)
            
            total_result = await self.db.execute(count_query)
            total = total_result.scalar()
            
            # Apply pagination
            offset = (page - 1) * limit
            query = query.offset(offset).limit(limit)
            
            # Execute query
            result = await self.db.execute(query)
            users = result.scalars().all()
            
            # Format response
            user_data = []
            for user in users:
                user_data.append({
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                    "is_active": user.is_active,
                    "is_admin": getattr(user, 'is_admin', False),
                    "is_super_admin": getattr(user, 'is_super_admin', False),
                    "organization_id": user.organization_id,
                    "organization_name": user.organization.name if user.organization else None,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None
                })
            
            return {
                "users": user_data,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit
                }
            }
            
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            raise
    
    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            query = select(User).where(User.id == user_id)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                return None
            
            # Get organization name if organization_id exists
            org_name = None
            if user.organization_id:
                try:
                    from src.database.models_comprehensive import Organization
                    org_query = select(Organization).where(Organization.id == user.organization_id)
                    org_result = await self.db.execute(org_query)
                    org = org_result.scalar_one_or_none()
                    if org:
                        org_name = org.name
                except Exception as e:
                    logger.warning(f"Could not fetch organization name for user {user_id}: {e}")
            
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "is_admin": getattr(user, 'is_admin', False),
                "is_super_admin": getattr(user, 'is_super_admin', False),
                "organization_id": user.organization_id,
                "organization_name": org_name,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            raise
    
    async def create_user(
        self,
        user_data: Dict[str, Any],
        requesting_user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Create a new user with organization scoping"""
        try:
            # Validate required fields
            required_fields = ["username", "email", "password", "full_name", "role"]
            for field in required_fields:
                if not user_data.get(field):
                    raise ValueError(f"Missing required field: {field}")
            
            # Security: Validate organization assignment
            target_org_id = user_data.get("organization_id")
            if requesting_user and not self._is_super_admin(requesting_user):
                # Org admins can only create users in their organization
                if target_org_id and target_org_id != requesting_user.organization_id:
                    raise ValueError("Cannot create users in other organizations")
                # Force organization to requesting user's org
                user_data["organization_id"] = requesting_user.organization_id
                
                # Org admins cannot create super admins
                if user_data.get("role") == "super_admin":
                    raise ValueError("Only super admins can create super admin users")
                if user_data.get("is_super_admin"):
                    raise ValueError("Only super admins can grant super admin privileges")
            
            # Check if username or email already exists
            existing_user = await self.db.execute(
                select(User).where(
                    (User.username == user_data["username"]) | 
                    (User.email == user_data["email"])
                )
            )
            if existing_user.scalar_one_or_none():
                raise ValueError("Username or email already exists")
            
            # Hash password
            hashed_password = get_password_hash(user_data["password"])
            
            # Create user
            new_user = User(
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=hashed_password,
                full_name=user_data["full_name"],
                role=user_data["role"],
                is_active=user_data.get("is_active", True),
                organization_id=user_data.get("organization_id"),
                created_at=datetime.utcnow()
            )
            
            self.db.add(new_user)
            await self.db.commit()
            await self.db.refresh(new_user)
            
            return {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "role": new_user.role,
                "is_active": new_user.is_active,
                "organization_id": new_user.organization_id,
                "created_at": new_user.created_at.isoformat()
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating user: {e}")
            raise
    
    async def update_user(
        self,
        user_id: int,
        update_data: Dict[str, Any],
        requesting_user: Optional[User] = None
    ) -> Dict[str, Any]:
        """Update user information with organization scoping"""
        try:
            # Get existing user
            query = select(User).where(User.id == user_id)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            # Security: Validate organization access
            if requesting_user and not self._is_super_admin(requesting_user):
                # Org admins can only edit users in their organization
                if user.organization_id != requesting_user.organization_id:
                    raise ValueError("Cannot edit users in other organizations")
                
                # Org admins cannot edit super admins
                if user.role == "super_admin" or getattr(user, "is_super_admin", False):
                    raise ValueError("Cannot edit super admin users")
                
                # Prevent privilege escalation
                if update_data.get("role") == "super_admin":
                    raise ValueError("Cannot assign super admin role")
                if update_data.get("is_super_admin"):
                    raise ValueError("Cannot grant super admin privileges")
                
                # Prevent organization transfer
                if "organization_id" in update_data and update_data["organization_id"] != user.organization_id:
                    raise ValueError("Cannot transfer users to other organizations")
            
            # Check if it's a super admin (protect from modification)
            if user.role == "super_admin":
                # Only allow certain fields to be updated
                allowed_fields = ["full_name", "email"]
                update_data = {k: v for k, v in update_data.items() if k in allowed_fields}
            
            # Update fields
            for field, value in update_data.items():
                if hasattr(user, field) and field != "id":
                    if field == "password" and value:
                        # Hash new password
                        setattr(user, "hashed_password", get_password_hash(value))
                    else:
                        setattr(user, field, value)
            
            user.updated_at = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(user)
            
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "organization_id": user.organization_id,
                "updated_at": user.updated_at.isoformat()
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating user {user_id}: {e}")
            raise
    
    async def delete_user(
        self,
        user_id: int,
        requesting_user: Optional[User] = None
    ) -> bool:
        """Delete a user with organization scoping"""
        try:
            # Get user to check if it's a super admin
            query = select(User).where(User.id == user_id)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()
            
            if not user:
                raise ValueError("User not found")
            
            # Security: Validate organization access
            if requesting_user and not self._is_super_admin(requesting_user):
                # Org admins can only delete users in their organization
                if user.organization_id != requesting_user.organization_id:
                    raise ValueError("Cannot delete users in other organizations")
                
                # Org admins cannot delete super admins
                if user.role == "super_admin" or getattr(user, "is_super_admin", False):
                    raise ValueError("Cannot delete super admin users")
            
            # Prevent deletion of super admin
            if user.role == "super_admin":
                raise ValueError("Cannot delete super admin user")
            
            # Delete user
            delete_query = delete(User).where(User.id == user_id)
            await self.db.execute(delete_query)
            await self.db.commit()
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting user {user_id}: {e}")
            raise
    
    def _is_super_admin(self, user: User) -> bool:
        """Helper to check if user is super admin"""
        return (getattr(user, "is_super_admin", False) or 
                (getattr(user, "role", "") or "").lower() == "super_admin")
    
    async def get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics"""
        try:
            # Total users
            total_query = select(text("COUNT(*)")).select_from(User)
            total_result = await self.db.execute(total_query)
            total_users = total_result.scalar()
            
            # Active users
            active_query = select(text("COUNT(*)")).select_from(User).where(User.is_active)
            active_result = await self.db.execute(active_query)
            active_users = active_result.scalar()
            
            # Admin users
            admin_query = select(text("COUNT(*)")).select_from(User).where(
                (User.is_admin) | (User.role.in_(["admin", "super_admin"]))
            )
            admin_result = await self.db.execute(admin_query)
            admin_users = admin_result.scalar()
            
            # New users today
            today_query = select(text("COUNT(*)")).select_from(User).where(
                text("DATE(created_at) = CURRENT_DATE")
            )
            today_result = await self.db.execute(today_query)
            new_today = today_result.scalar()
            
            # Users by role
            role_query = select(User.role, text("COUNT(*)")).group_by(User.role)
            role_result = await self.db.execute(role_query)
            users_by_role = {row[0]: row[1] for row in role_result}
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "admin_users": admin_users,
                "new_today": new_today,
                "users_by_role": users_by_role
            }
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            raise
    
    async def bulk_update_users(self, user_ids: List[int], update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Bulk update multiple users"""
        try:
            # Validate that we're not trying to modify super admins
            super_admin_query = select(User.id).where(
                (User.id.in_(user_ids)) & (User.role == "super_admin")
            )
            result = await self.db.execute(super_admin_query)
            super_admin_ids = [row[0] for row in result]
            
            if super_admin_ids:
                raise ValueError(f"Cannot modify super admin users: {super_admin_ids}")
            
            # Update users
            update_query = update(User).where(User.id.in_(user_ids)).values(
                **update_data,
                updated_at=datetime.utcnow()
            )
            
            result = await self.db.execute(update_query)
            await self.db.commit()
            
            return {
                "updated_count": result.rowcount,
                "user_ids": user_ids
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error bulk updating users: {e}")
            raise
    
    async def bulk_delete_users(self, user_ids: List[int]) -> Dict[str, Any]:
        """Bulk delete multiple users"""
        try:
            # Validate that we're not trying to delete super admins
            super_admin_query = select(User.id).where(
                (User.id.in_(user_ids)) & (User.role == "super_admin")
            )
            result = await self.db.execute(super_admin_query)
            super_admin_ids = [row[0] for row in result]
            
            if super_admin_ids:
                raise ValueError(f"Cannot delete super admin users: {super_admin_ids}")
            
            # Delete users
            delete_query = delete(User).where(User.id.in_(user_ids))
            result = await self.db.execute(delete_query)
            await self.db.commit()
            
            return {
                "deleted_count": result.rowcount,
                "user_ids": user_ids
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error bulk deleting users: {e}")
            raise
