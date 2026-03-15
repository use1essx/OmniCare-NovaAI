"""
Healthcare AI V2 - User Repository
Repository for user management operations
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models_comprehensive import User, UserSession, UserPermission, Permission
from src.database.repositories.base_repository import BaseRepository
from src.database.connection import get_async_session


class UserRepository(BaseRepository[User]):
    """Repository for user operations"""
    
    def __init__(self):
        super().__init__(User)
    
    async def get_by_email(self, email: str, session: Optional[AsyncSession] = None) -> Optional[User]:
        """Get user by email address"""
        return await self.get_by_field("email", email, session)
    
    async def get_by_username(self, username: str, session: Optional[AsyncSession] = None) -> Optional[User]:
        """Get user by username"""
        return await self.get_by_field("username", username, session)
    
    async def get_with_permissions(
        self, 
        user_id: int, 
        session: Optional[AsyncSession] = None
    ) -> Optional[User]:
        """Get user with their permissions loaded"""
        if session is None:
            async with get_async_session() as session:
                return await self._get_with_permissions(session, user_id)
        return await self._get_with_permissions(session, user_id)
    
    async def _get_with_permissions(self, session: AsyncSession, user_id: int) -> Optional[User]:
        """Internal method to get user with permissions"""
        stmt = (
            select(User)
            .options(selectinload(User.permissions).selectinload(UserPermission.permission))
            .where(User.id == user_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def create_user(
        self,
        email: str,
        username: str,
        hashed_password: str,
        full_name: Optional[str] = None,
        role: str = "user",
        **kwargs
    ) -> User:
        """Create a new user"""
        user_data = {
            "email": email,
            "username": username,
            "hashed_password": hashed_password,
            "full_name": full_name,
            "role": role,
            **kwargs
        }
        return await self.create(user_data)
    
    async def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp"""
        result = await self.update(user_id, {"last_login": datetime.utcnow()})
        return result is not None
    
    async def increment_failed_attempts(self, user_id: int) -> Optional[User]:
        """Increment failed login attempts and lock account if necessary"""
        async with get_async_session() as session:
            user = await self._get_by_id(session, user_id)
            if not user:
                return None
            
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts for 30 minutes
            if user.failed_login_attempts >= 5:
                user.account_locked_until = datetime.utcnow() + timedelta(minutes=30)
            
            await session.commit()
            await session.refresh(user)
            return user
    
    async def reset_failed_attempts(self, user_id: int) -> bool:
        """Reset failed login attempts"""
        result = await self.update(user_id, {
            "failed_login_attempts": 0,
            "account_locked_until": None
        })
        return result is not None
    
    async def is_account_locked(self, user_id: int) -> bool:
        """Check if user account is currently locked"""
        user = await self.get_by_id(user_id)
        if not user or not user.account_locked_until:
            return False
        return user.account_locked_until > datetime.utcnow()
    
    async def unlock_account(self, user_id: int) -> bool:
        """Manually unlock a user account"""
        result = await self.update(user_id, {
            "account_locked_until": None,
            "failed_login_attempts": 0
        })
        return result is not None
    
    async def activate_user(self, user_id: int) -> bool:
        """Activate a user account"""
        result = await self.update(user_id, {"is_active": True})
        return result is not None
    
    async def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user account"""
        result = await self.update(user_id, {"is_active": False})
        return result is not None
    
    async def verify_user(self, user_id: int) -> bool:
        """Mark user as verified"""
        result = await self.update(user_id, {"is_verified": True})
        return result is not None
    
    async def change_password(self, user_id: int, new_hashed_password: str) -> bool:
        """Change user password"""
        result = await self.update(user_id, {
            "hashed_password": new_hashed_password,
            "password_changed_at": datetime.utcnow()
        })
        return result is not None
    
    async def update_preferences(
        self, 
        user_id: int, 
        language: Optional[str] = None,
        timezone: Optional[str] = None,
        notifications: Optional[Dict] = None
    ) -> Optional[User]:
        """Update user preferences"""
        updates = {}
        if language:
            updates["language_preference"] = language
        if timezone:
            updates["timezone"] = timezone
        if notifications:
            updates["notification_preferences"] = notifications
        
        if updates:
            return await self.update(user_id, updates)
        return await self.get_by_id(user_id)
    
    async def get_by_role(self, role: str, active_only: bool = True) -> List[User]:
        """Get users by role"""
        filters = {"role": role}
        if active_only:
            filters["is_active"] = True
        return await self.get_filtered(filters)
    
    async def get_admins(self, active_only: bool = True) -> List[User]:
        """Get all admin users"""
        async with get_async_session() as session:
            stmt = select(User).where(
                or_(User.is_admin, User.is_super_admin)
            )
            if active_only:
                stmt = stmt.where(User.is_active)
            
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def search_users(
        self,
        search_term: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[User]:
        """Search users by email, username, or full name"""
        async with get_async_session() as session:
            search_pattern = f"%{search_term}%"
            stmt = (
                select(User)
                .where(
                    or_(
                        User.email.ilike(search_pattern),
                        User.username.ilike(search_pattern),
                        User.full_name.ilike(search_pattern)
                    )
                )
                .limit(limit)
                .offset(offset)
                .order_by(User.full_name, User.username)
            )
            
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def get_users_with_permission(self, permission_name: str) -> List[User]:
        """Get all users with a specific permission"""
        async with get_async_session() as session:
            stmt = (
                select(User)
                .join(UserPermission)
                .join(Permission)
                .where(
                    and_(
                        Permission.name == permission_name,
                        Permission.is_active,
                        User.is_active,
                        or_(
                            UserPermission.expires_at.is_(None),
                            UserPermission.expires_at > datetime.utcnow()
                        ),
                        UserPermission.revoked_at.is_(None)
                    )
                )
                .order_by(User.full_name, User.username)
            )
            
            result = await session.execute(stmt)
            return result.scalars().all()
    
    async def get_user_statistics(self) -> Dict:
        """Get user statistics"""
        async with get_async_session() as session:
            # Total users
            total_users = await self._count(session)
            
            # Active users
            active_users = await self._count(session, {"is_active": True})
            
            # Users by role
            role_stats = {}
            for role in ["user", "admin", "medical_reviewer", "data_manager", "super_admin"]:
                count = await self._count(session, {"role": role, "is_active": True})
                role_stats[role] = count
            
            # Recent registrations (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            stmt = (
                select(func.count(User.id))
                .where(
                    and_(
                        User.created_at >= thirty_days_ago,
                        User.is_active
                    )
                )
            )
            result = await session.execute(stmt)
            recent_registrations = result.scalar()
            
            # Users with recent activity (last 7 days)
            seven_days_ago = datetime.utcnow() - timedelta(days=7)
            stmt = (
                select(func.count(User.id))
                .where(
                    and_(
                        User.last_login >= seven_days_ago,
                        User.is_active
                    )
                )
            )
            result = await session.execute(stmt)
            active_last_week = result.scalar()
            
            return {
                "total_users": total_users,
                "active_users": active_users,
                "inactive_users": total_users - active_users,
                "role_distribution": role_stats,
                "recent_registrations": recent_registrations,
                "active_last_week": active_last_week
            }


class UserSessionRepository(BaseRepository[UserSession]):
    """Repository for user session operations"""
    
    def __init__(self):
        super().__init__(UserSession)
    
    async def create_session(
        self,
        user_id: int,
        session_token: str,
        expires_at: datetime,
        ip_address: str,
        user_agent: str,
        refresh_token: Optional[str] = None
    ) -> UserSession:
        """Create a new user session"""
        session_data = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "refresh_token": refresh_token
        }
        return await self.create(session_data)
    
    async def get_by_token(self, token: str) -> Optional[UserSession]:
        """Get session by token"""
        return await self.get_by_field("session_token", token)
    
    async def get_active_sessions(self, user_id: int) -> List[UserSession]:
        """Get all active sessions for a user"""
        filters = {
            "user_id": user_id,
            "is_active": True
        }
        return await self.get_filtered(
            filters,
            order_by="last_activity",
            order_desc=True
        )
    
    async def revoke_session(self, session_id: int, reason: str = "logout") -> bool:
        """Revoke a session"""
        result = await self.update(session_id, {
            "is_active": False,
            "revoked_at": datetime.utcnow(),
            "revoked_reason": reason
        })
        return result is not None
    
    async def revoke_all_sessions(self, user_id: int, except_session_id: Optional[int] = None) -> int:
        """Revoke all sessions for a user except optionally one"""
        async with get_async_session() as session:
            from sqlalchemy import update
            
            stmt = (
                update(UserSession)
                .where(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.is_active
                    )
                )
                .values(
                    is_active=False,
                    revoked_at=datetime.utcnow(),
                    revoked_reason="bulk_revoke"
                )
            )
            
            if except_session_id:
                stmt = stmt.where(UserSession.id != except_session_id)
            
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
    
    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions"""
        async with get_async_session() as session:
            from sqlalchemy import delete
            
            stmt = delete(UserSession).where(UserSession.expires_at < datetime.utcnow())
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
    
    async def update_activity(self, session_id: int) -> bool:
        """Update last activity timestamp for a session"""
        result = await self.update(session_id, {"last_activity": datetime.utcnow()})
        return result is not None
