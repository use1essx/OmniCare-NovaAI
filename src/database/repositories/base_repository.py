"""
Healthcare AI V2 - Base Repository
Base repository class with common CRUD operations
"""

from abc import ABC
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from datetime import datetime

from sqlalchemy import desc, asc, func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import Select

from src.database.connection import get_async_session

T = TypeVar("T", bound=DeclarativeBase)


class BaseRepository(Generic[T], ABC):
    """
    Base repository class providing common CRUD operations
    """
    
    def __init__(self, model: Type[T]):
        self.model = model
    
    async def get_by_id(self, id: int, session: Optional[AsyncSession] = None) -> Optional[T]:
        """Get a single record by ID"""
        if session is None:
            async with get_async_session() as session:
                return await self._get_by_id(session, id)
        return await self._get_by_id(session, id)
    
    async def _get_by_id(self, session: AsyncSession, id: int) -> Optional[T]:
        """Internal method to get by ID with existing session"""
        stmt = select(self.model).where(self.model.id == id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_field(
        self, 
        field_name: str, 
        value: Any, 
        session: Optional[AsyncSession] = None
    ) -> Optional[T]:
        """Get a single record by any field"""
        if session is None:
            async with get_async_session() as session:
                return await self._get_by_field(session, field_name, value)
        return await self._get_by_field(session, field_name, value)
    
    async def _get_by_field(
        self, 
        session: AsyncSession, 
        field_name: str, 
        value: Any
    ) -> Optional[T]:
        """Internal method to get by field with existing session"""
        field = getattr(self.model, field_name)
        stmt = select(self.model).where(field == value)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        session: Optional[AsyncSession] = None
    ) -> List[T]:
        """Get all records with optional pagination and ordering"""
        if session is None:
            async with get_async_session() as session:
                return await self._get_all(session, limit, offset, order_by, order_desc)
        return await self._get_all(session, limit, offset, order_by, order_desc)
    
    async def _get_all(
        self,
        session: AsyncSession,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[T]:
        """Internal method to get all with existing session"""
        stmt = select(self.model)
        
        # Add ordering
        if order_by:
            order_field = getattr(self.model, order_by)
            if order_desc:
                stmt = stmt.order_by(desc(order_field))
            else:
                stmt = stmt.order_by(asc(order_field))
        
        # Add pagination
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    
    async def get_filtered(
        self,
        filters: Dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        session: Optional[AsyncSession] = None
    ) -> List[T]:
        """Get records with filtering"""
        if session is None:
            async with get_async_session() as session:
                return await self._get_filtered(session, filters, limit, offset, order_by, order_desc)
        return await self._get_filtered(session, filters, limit, offset, order_by, order_desc)
    
    async def _get_filtered(
        self,
        session: AsyncSession,
        filters: Dict[str, Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> List[T]:
        """Internal method to get filtered with existing session"""
        stmt = select(self.model)
        
        # Apply filters
        for field_name, value in filters.items():
            if value is not None:
                field = getattr(self.model, field_name)
                stmt = stmt.where(field == value)
        
        # Add ordering
        if order_by:
            order_field = getattr(self.model, order_by)
            if order_desc:
                stmt = stmt.order_by(desc(order_field))
            else:
                stmt = stmt.order_by(asc(order_field))
        
        # Add pagination
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        
        result = await session.execute(stmt)
        return result.scalars().all()
    
    async def count(
        self, 
        filters: Optional[Dict[str, Any]] = None,
        session: Optional[AsyncSession] = None
    ) -> int:
        """Count records with optional filtering"""
        if session is None:
            async with get_async_session() as session:
                return await self._count(session, filters)
        return await self._count(session, filters)
    
    async def _count(
        self, 
        session: AsyncSession,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """Internal method to count with existing session"""
        stmt = select(func.count(self.model.id))
        
        # Apply filters
        if filters:
            for field_name, value in filters.items():
                if value is not None:
                    field = getattr(self.model, field_name)
                    stmt = stmt.where(field == value)
        
        result = await session.execute(stmt)
        return result.scalar()
    
    async def create(
        self, 
        data: Dict[str, Any],
        session: Optional[AsyncSession] = None
    ) -> T:
        """Create a new record"""
        if session is None:
            async with get_async_session() as session:
                return await self._create(session, data)
        return await self._create(session, data)
    
    async def _create(self, session: AsyncSession, data: Dict[str, Any]) -> T:
        """Internal method to create with existing session"""
        # Add timestamp fields if they exist
        if hasattr(self.model, 'created_at') and 'created_at' not in data:
            data['created_at'] = datetime.utcnow()
        if hasattr(self.model, 'updated_at') and 'updated_at' not in data:
            data['updated_at'] = datetime.utcnow()
        
        instance = self.model(**data)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)
        return instance
    
    async def update(
        self,
        id: int,
        data: Dict[str, Any],
        session: Optional[AsyncSession] = None
    ) -> Optional[T]:
        """Update a record by ID"""
        if session is None:
            async with get_async_session() as session:
                return await self._update(session, id, data)
        return await self._update(session, id, data)
    
    async def _update(
        self, 
        session: AsyncSession,
        id: int, 
        data: Dict[str, Any]
    ) -> Optional[T]:
        """Internal method to update with existing session"""
        # Add updated timestamp if it exists
        if hasattr(self.model, 'updated_at'):
            data['updated_at'] = datetime.utcnow()
        
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**data)
            .returning(self.model)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.scalar_one_or_none()
    
    async def delete(
        self, 
        id: int,
        session: Optional[AsyncSession] = None
    ) -> bool:
        """Delete a record by ID"""
        if session is None:
            async with get_async_session() as session:
                return await self._delete(session, id)
        return await self._delete(session, id)
    
    async def _delete(self, session: AsyncSession, id: int) -> bool:
        """Internal method to delete with existing session"""
        stmt = delete(self.model).where(self.model.id == id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0
    
    async def bulk_create(
        self,
        data_list: List[Dict[str, Any]],
        session: Optional[AsyncSession] = None
    ) -> List[T]:
        """Create multiple records in bulk"""
        if session is None:
            async with get_async_session() as session:
                return await self._bulk_create(session, data_list)
        return await self._bulk_create(session, data_list)
    
    async def _bulk_create(
        self, 
        session: AsyncSession,
        data_list: List[Dict[str, Any]]
    ) -> List[T]:
        """Internal method to bulk create with existing session"""
        instances = []
        current_time = datetime.utcnow()
        
        for data in data_list:
            # Add timestamp fields if they exist
            if hasattr(self.model, 'created_at') and 'created_at' not in data:
                data['created_at'] = current_time
            if hasattr(self.model, 'updated_at') and 'updated_at' not in data:
                data['updated_at'] = current_time
            
            instance = self.model(**data)
            instances.append(instance)
        
        session.add_all(instances)
        await session.commit()
        
        # Refresh all instances to get IDs
        for instance in instances:
            await session.refresh(instance)
        
        return instances
    
    async def exists(
        self,
        filters: Dict[str, Any],
        session: Optional[AsyncSession] = None
    ) -> bool:
        """Check if a record exists with given filters"""
        if session is None:
            async with get_async_session() as session:
                return await self._exists(session, filters)
        return await self._exists(session, filters)
    
    async def _exists(
        self,
        session: AsyncSession,
        filters: Dict[str, Any]
    ) -> bool:
        """Internal method to check existence with existing session"""
        stmt = select(self.model.id)
        
        # Apply filters
        for field_name, value in filters.items():
            if value is not None:
                field = getattr(self.model, field_name)
                stmt = stmt.where(field == value)
        
        stmt = stmt.limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None
    
    def build_query(self) -> Select:
        """Build a base query for custom operations"""
        return select(self.model)
    
    async def execute_query(
        self,
        stmt: Select,
        session: Optional[AsyncSession] = None
    ) -> List[T]:
        """Execute a custom query"""
        if session is None:
            async with get_async_session() as session:
                return await self._execute_query(session, stmt)
        return await self._execute_query(session, stmt)
    
    async def _execute_query(
        self,
        session: AsyncSession,
        stmt: Select
    ) -> List[T]:
        """Internal method to execute query with existing session"""
        result = await session.execute(stmt)
        return result.scalars().all()
    
    async def get_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """Get paginated results with metadata"""
        if session is None:
            async with get_async_session() as session:
                return await self._get_paginated(session, page, page_size, filters, order_by, order_desc)
        return await self._get_paginated(session, page, page_size, filters, order_by, order_desc)
    
    async def _get_paginated(
        self,
        session: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = False
    ) -> Dict[str, Any]:
        """Internal method for pagination with existing session"""
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get total count
        total_count = await self._count(session, filters)
        
        # Get items
        items = await self._get_filtered(
            session, 
            filters or {}, 
            limit=page_size, 
            offset=offset,
            order_by=order_by,
            order_desc=order_desc
        )
        
        # Calculate pagination metadata
        total_pages = (total_count + page_size - 1) // page_size
        has_next = page < total_pages
        has_prev = page > 1
        
        return {
            "items": items,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": has_next,
                "has_prev": has_prev
            }
        }
