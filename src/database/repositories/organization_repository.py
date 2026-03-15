"""
Organization Repository
Handles database operations for Organization model
"""

from typing import Optional, List
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models_comprehensive import Organization, User
from src.database.repositories.base_repository import BaseRepository

class OrganizationRepository(BaseRepository[Organization]):
    """Repository for Organization model"""
    
    def __init__(self):
        super().__init__(Organization)
    
    async def get_by_name(self, name: str, session: AsyncSession) -> Optional[Organization]:
        """Get organization by name"""
        return await self._get_by_field(session, "name", name)
    
    async def search(
        self, 
        query: str, 
        limit: int = 20, 
        offset: int = 0,
        session: Optional[AsyncSession] = None
    ) -> List[Organization]:
        """Search organizations by name or description"""
        if session is None:
            # This pattern is slightly different from BaseRepository but follows the same logic
            # However, BaseRepository methods usually handle session creation if None
            # Here we need to implement the search logic
            # For simplicity, let's assume session is passed or we use the internal helper if we had one for search
            # But BaseRepository doesn't have a generic search.
            # So we should probably enforce session or use get_async_session context manager
            from src.database.connection import get_async_session
            async with get_async_session() as session:
                return await self._search(session, query, limit, offset)
        return await self._search(session, query, limit, offset)

    async def _search(
        self,
        session: AsyncSession,
        query: str,
        limit: int,
        offset: int
    ) -> List[Organization]:
        """Internal search method"""
        stmt = select(self.model).where(
            or_(
                self.model.name.ilike(f"%{query}%"),
                self.model.description.ilike(f"%{query}%")
            )
        ).limit(limit).offset(offset)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    
    async def get_all_with_user_counts(
        self,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "name",
        session: Optional[AsyncSession] = None
    ) -> List[dict]:
        """Get all organizations with user counts"""
        if session is None:
            from src.database.connection import get_async_session
            async with get_async_session() as session:
                return await self._get_all_with_user_counts(session, limit, offset, order_by)
        return await self._get_all_with_user_counts(session, limit, offset, order_by)
    
    async def _get_all_with_user_counts(
        self,
        session: AsyncSession,
        limit: int,
        offset: int,
        order_by: str
    ) -> List[dict]:
        """Internal method to get organizations with user counts"""
        # Query organizations with user count
        stmt = (
            select(
                Organization,
                func.count(User.id).label('user_count')
            )
            .outerjoin(User, User.organization_id == Organization.id)
            .group_by(Organization.id)
            .order_by(getattr(Organization, order_by, Organization.name))
            .limit(limit)
            .offset(offset)
        )
        
        result = await session.execute(stmt)
        rows = result.all()
        
        # Convert to list of dicts with organization data + user_count
        orgs_with_counts = []
        for org, user_count in rows:
            org_dict = {
                'id': org.id,
                'name': org.name,
                'type': org.type,
                'description': org.description,
                'email': org.email,
                'phone': org.phone,
                'address': org.address,
                'website': org.website,
                'max_users': org.max_users,
                'max_admins': org.max_admins,
                'is_active': org.is_active,
                'created_at': org.created_at,
                'updated_at': org.updated_at,
                'user_count': user_count
            }
            orgs_with_counts.append(org_dict)
        
        return orgs_with_counts
