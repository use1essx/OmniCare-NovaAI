"""
Case Manager for Social Worker Hub

Handles CRUD operations for case files including:
- Case creation with auto-generated case numbers
- Risk level management
- Status updates
- Assignment tracking
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import CaseFile, CaseNote
from ..database.connection import get_async_db

logger = logging.getLogger(__name__)


class CaseManager:
    """
    Manages case files for social workers.
    
    Features:
    - CRUD operations
    - Case number generation
    - Risk level calculation
    - Status transitions
    - Assignment management
    """
    
    async def create_case(
        self,
        child_id: int,
        summary: str,
        presenting_concerns: str,
        social_worker_id: Optional[int] = None,
        priority: str = "medium",
        initial_risk_level: Optional[int] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> CaseFile:
        """
        Create a new case file.
        
        Args:
            child_id: ID of the child
            summary: Case summary
            presenting_concerns: Initial concerns
            social_worker_id: Assigned social worker
            priority: Priority level
            initial_risk_level: Initial risk score (0-100)
            tags: Case tags
            metadata: Additional metadata
            
        Returns:
            Created CaseFile
        """
        async for session in get_async_db():
            try:
                # Generate case number
                case_number = await self._generate_case_number(session)
                
                # Calculate risk category if score provided
                risk_category = None
                if initial_risk_level is not None:
                    risk_category = self._get_risk_category(initial_risk_level)
                
                # Create case
                case = CaseFile(
                    case_number=case_number,
                    child_id=child_id,
                    social_worker_id=social_worker_id,
                    status='open' if social_worker_id else 'pending_assignment',
                    priority=priority,
                    risk_level=initial_risk_level,
                    risk_category=risk_category,
                    summary=summary,
                    presenting_concerns=presenting_concerns,
                    tags=tags or [],
                    metadata=metadata or {},
                    opened_at=datetime.utcnow(),
                    assigned_at=datetime.utcnow() if social_worker_id else None
                )
                
                session.add(case)
                await session.commit()
                await session.refresh(case)
                
                logger.info(f"Created case {case_number} for child {child_id}")
                return case
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating case: {e}")
                raise
    
    async def get_case(self, case_id: int) -> Optional[CaseFile]:
        """Get a case by ID"""
        async for session in get_async_db():
            result = await session.execute(
                select(CaseFile).where(CaseFile.id == case_id)
            )
            return result.scalar_one_or_none()
    
    async def get_case_by_number(self, case_number: str) -> Optional[CaseFile]:
        """Get a case by case number"""
        async for session in get_async_db():
            result = await session.execute(
                select(CaseFile).where(CaseFile.case_number == case_number)
            )
            return result.scalar_one_or_none()
    
    async def get_cases_for_social_worker(
        self,
        social_worker_id: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[CaseFile]:
        """Get all cases assigned to a social worker"""
        async for session in get_async_db():
            query = select(CaseFile).where(
                CaseFile.social_worker_id == social_worker_id
            )
            
            if status:
                query = query.where(CaseFile.status == status)
            if priority:
                query = query.where(CaseFile.priority == priority)
            
            query = query.order_by(
                CaseFile.priority.desc(),
                CaseFile.updated_at.desc()
            ).offset(offset).limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_high_risk_cases(
        self,
        min_risk_level: int = 60,
        limit: int = 20
    ) -> List[CaseFile]:
        """Get high-risk cases that need attention"""
        async for session in get_async_db():
            result = await session.execute(
                select(CaseFile).where(
                    and_(
                        CaseFile.risk_level >= min_risk_level,
                        CaseFile.status.in_(['open', 'monitoring', 'escalated'])
                    )
                ).order_by(CaseFile.risk_level.desc()).limit(limit)
            )
            return list(result.scalars().all())
    
    async def update_case(
        self,
        case_id: int,
        updates: Dict[str, Any]
    ) -> Optional[CaseFile]:
        """
        Update a case file.
        
        Args:
            case_id: Case ID
            updates: Dictionary of fields to update
            
        Returns:
            Updated CaseFile or None
        """
        async for session in get_async_db():
            try:
                result = await session.execute(
                    select(CaseFile).where(CaseFile.id == case_id)
                )
                case = result.scalar_one_or_none()
                
                if not case:
                    return None
                
                # Apply updates
                for key, value in updates.items():
                    if hasattr(case, key):
                        setattr(case, key, value)
                
                # Update risk category if risk level changed
                if 'risk_level' in updates and updates['risk_level'] is not None:
                    case.risk_category = self._get_risk_category(updates['risk_level'])
                    case.last_risk_assessment = datetime.utcnow()
                
                await session.commit()
                await session.refresh(case)
                
                logger.info(f"Updated case {case.case_number}")
                return case
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating case: {e}")
                raise
    
    async def update_risk_level(
        self,
        case_id: int,
        risk_level: int,
        assessment_notes: Optional[str] = None
    ) -> Optional[CaseFile]:
        """Update risk level for a case"""
        updates = {
            'risk_level': risk_level,
            'risk_category': self._get_risk_category(risk_level),
            'last_risk_assessment': datetime.utcnow()
        }
        
        # Add assessment to notes if provided
        if assessment_notes:
            async for session in get_async_db():
                result = await session.execute(
                    select(CaseFile).where(CaseFile.id == case_id)
                )
                case = result.scalar_one_or_none()
                
                if case:
                    notes = case.notes or []
                    notes.append({
                        'type': 'risk_assessment',
                        'content': assessment_notes,
                        'risk_level': risk_level,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    updates['notes'] = notes
        
        return await self.update_case(case_id, updates)
    
    async def assign_case(
        self,
        case_id: int,
        social_worker_id: int,
        reason: Optional[str] = None
    ) -> Optional[CaseFile]:
        """Assign or reassign a case to a social worker"""
        async for session in get_async_db():
            try:
                result = await session.execute(
                    select(CaseFile).where(CaseFile.id == case_id)
                )
                case = result.scalar_one_or_none()
                
                if not case:
                    return None
                
                # Track reassignment
                if case.social_worker_id and case.social_worker_id != social_worker_id:
                    history = case.reassignment_history or []
                    history.append({
                        'from_id': case.social_worker_id,
                        'to_id': social_worker_id,
                        'reason': reason,
                        'timestamp': datetime.utcnow().isoformat()
                    })
                    case.reassignment_history = history
                
                case.social_worker_id = social_worker_id
                case.assigned_at = datetime.utcnow()
                
                if case.status == 'pending_assignment':
                    case.status = 'open'
                
                await session.commit()
                await session.refresh(case)
                
                logger.info(f"Assigned case {case.case_number} to SW {social_worker_id}")
                return case
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error assigning case: {e}")
                raise
    
    async def close_case(
        self,
        case_id: int,
        closure_reason: str,
        outcomes: Optional[Dict] = None
    ) -> Optional[CaseFile]:
        """Close a case"""
        updates = {
            'status': 'closed',
            'closed_at': datetime.utcnow(),
            'closure_reason': closure_reason,
        }
        
        if outcomes:
            updates['outcomes'] = outcomes
        
        return await self.update_case(case_id, updates)
    
    async def add_note(
        self,
        case_id: int,
        note_type: str,
        content: str,
        author_id: int,
        title: Optional[str] = None,
        contact_type: Optional[str] = None,
        contact_with: Optional[str] = None
    ) -> CaseNote:
        """Add a note to a case"""
        async for session in get_async_db():
            try:
                note = CaseNote(
                    case_id=case_id,
                    note_type=note_type,
                    title=title,
                    content=content,
                    author_id=author_id,
                    contact_type=contact_type,
                    contact_with=contact_with,
                    contact_date=datetime.utcnow() if contact_type else None
                )
                
                session.add(note)
                await session.commit()
                await session.refresh(note)
                
                return note
                
            except Exception as e:
                await session.rollback()
                logger.error(f"Error adding note: {e}")
                raise
    
    async def get_case_stats(
        self,
        social_worker_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get case statistics"""
        async for session in get_async_db():
            base_query = select(CaseFile)
            
            if social_worker_id:
                base_query = base_query.where(
                    CaseFile.social_worker_id == social_worker_id
                )
            
            # Get counts by status
            status_counts = {}
            for status in ['open', 'monitoring', 'review', 'escalated', 'closed']:
                result = await session.execute(
                    select(func.count(CaseFile.id)).where(
                        and_(
                            CaseFile.status == status,
                            CaseFile.social_worker_id == social_worker_id if social_worker_id else True
                        )
                    )
                )
                status_counts[status] = result.scalar() or 0
            
            # Get high risk count
            result = await session.execute(
                select(func.count(CaseFile.id)).where(
                    and_(
                        CaseFile.risk_level >= 60,
                        CaseFile.status.in_(['open', 'monitoring', 'escalated']),
                        CaseFile.social_worker_id == social_worker_id if social_worker_id else True
                    )
                )
            )
            high_risk_count = result.scalar() or 0
            
            return {
                'status_counts': status_counts,
                'high_risk_count': high_risk_count,
                'total_active': sum(
                    status_counts[s] for s in ['open', 'monitoring', 'escalated']
                )
            }
    
    async def _generate_case_number(self, session: AsyncSession) -> str:
        """Generate unique case number"""
        year = datetime.utcnow().year
        prefix = f"CASE-{year}-"
        
        # Get max sequence for this year
        result = await session.execute(
            select(func.max(CaseFile.case_number)).where(
                CaseFile.case_number.like(f"{prefix}%")
            )
        )
        max_number = result.scalar()
        
        if max_number:
            # Extract sequence number
            seq = int(max_number.split('-')[-1]) + 1
        else:
            seq = 1
        
        return f"{prefix}{seq:04d}"
    
    def _get_risk_category(self, risk_level: int) -> str:
        """Get risk category from risk level"""
        if risk_level >= 80:
            return 'critical_risk'
        elif risk_level >= 60:
            return 'high_risk'
        elif risk_level >= 40:
            return 'moderate_risk'
        else:
            return 'low_risk'


# Singleton
_case_manager: Optional[CaseManager] = None


def get_case_manager() -> CaseManager:
    """Get or create case manager singleton"""
    global _case_manager
    if _case_manager is None:
        _case_manager = CaseManager()
    return _case_manager

