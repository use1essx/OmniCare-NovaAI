from typing import Optional, List, Dict, Any

from sqlalchemy import delete, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.repositories.base_repository import BaseRepository
from src.database.models_comprehensive import Conversation
from src.database.connection import get_async_session


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for conversation storage and cleanup."""

    def __init__(self):
        super().__init__(Conversation)

    async def delete_session_history(
        self,
        session_id: str,
        user_id: Optional[int] = None,
        session: Optional[AsyncSession] = None,
    ) -> int:
        """Delete conversation rows for a session_id (optionally scoped to user_id).

        Returns number of rows deleted.
        """
        if session is None:
            async with get_async_session() as db:
                return await self._delete_session_history(db, session_id, user_id)
        return await self._delete_session_history(session, session_id, user_id)

    async def _delete_session_history(
        self, db: AsyncSession, session_id: str, user_id: Optional[int]
    ) -> int:
        stmt = delete(Conversation).where(Conversation.session_id == session_id)
        if user_id is not None:
            stmt = stmt.where(Conversation.user_id == user_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0

    async def get_user_conversation_history(
        self,
        user_id: int,
        limit: int = 50,
        session: Optional[AsyncSession] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent conversation history for a user.
        
        Returns list of conversation entries in chronological order.
        """
        if session is None:
            async with get_async_session() as db:
                return await self._get_user_history(db, user_id, limit)
        return await self._get_user_history(session, user_id, limit)

    async def _get_user_history(
        self, db: AsyncSession, user_id: int, limit: int
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        conversations = result.scalars().all()
        
        # Return in chronological order with user/assistant pairs
        history = []
        for conv in reversed(conversations):  # Oldest first
            # Add user message
            if conv.user_input:
                history.append({
                    "role": "user",
                    "content": conv.user_input,
                    "timestamp": conv.created_at.isoformat() if conv.created_at else None,
                })
            # Add assistant response
            if conv.agent_response:
                history.append({
                    "role": "assistant", 
                    "content": conv.agent_response,
                    "agent_type": conv.agent_type,
                    "timestamp": conv.created_at.isoformat() if conv.created_at else None,
                })
        
        return history

    async def delete_user_history(
        self,
        user_id: int,
        session: Optional[AsyncSession] = None,
    ) -> int:
        """Delete ALL conversation history for a user.
        
        Returns number of rows deleted.
        """
        if session is None:
            async with get_async_session() as db:
                return await self._delete_user_history(db, user_id)
        return await self._delete_user_history(session, user_id)

    async def _delete_user_history(self, db: AsyncSession, user_id: int) -> int:
        stmt = delete(Conversation).where(Conversation.user_id == user_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0


