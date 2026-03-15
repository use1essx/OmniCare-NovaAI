"""
Database Session Manager - Healthcare AI V2
==========================================

Database-backed session management for conversation persistence.
Handles both anonymous (temporary) and authenticated (persistent) sessions.

Features:
- PostgreSQL for production database
- Automatic cleanup of expired sessions
- Separate storage for anonymous vs authenticated users
"""

import logging
import os
import psycopg2
import psycopg2.extras
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import json

from .conversation_models import ConversationMemory, ConversationState


class DatabaseSessionManager:
    """Database-backed session management for conversations."""
    
    def __init__(self):
        """Initialize database session manager."""
        self.logger = logging.getLogger("agents.db_session_manager")
        self.session_timeout = timedelta(hours=24)
        
        # PostgreSQL connection parameters from centralized settings
        from src.core.config import settings
        self.db_config = {
            'host': settings.database_host,
            'port': settings.database_port,
            'database': settings.database_name,
            'user': settings.database_user,
            'password': settings.database_password
        }
        
        # Initialize database
        self._init_database()
    
    def _get_connection(self):
        """Get PostgreSQL database connection."""
        return psycopg2.connect(**self.db_config)
    
    def _init_database(self):
        """Initialize database tables for session management."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Conversation sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    id SERIAL PRIMARY KEY,
                    session_key TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    is_authenticated BOOLEAN DEFAULT FALSE,
                    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    conversation_state TEXT DEFAULT 'active',
                    active_agent TEXT,
                    language_preference TEXT DEFAULT 'en',
                    health_topics JSONB,
                    conversation_data JSONB
                )
            """)
            
            # Conversation messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id SERIAL PRIMARY KEY,
                    session_key TEXT NOT NULL,
                    message_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    agent_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB,
                    FOREIGN KEY (session_key) REFERENCES conversation_sessions(session_key) ON DELETE CASCADE
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_key ON conversation_sessions(session_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_session ON conversation_sessions(user_id, session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_activity ON conversation_sessions(last_activity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON conversation_messages(session_key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages(timestamp)")
            
            conn.commit()
            conn.close()
            self.logger.info("✅ PostgreSQL database session manager initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize PostgreSQL database: {e}")
            # Don't raise, just log. Operations will fail gracefully later if DB is down.
            pass
    
    def get_session_key(self, user_id: str, session_id: str) -> str:
        """Generate session key for database storage."""
        return f"{user_id}:{session_id}"
    
    def is_authenticated_user(self, user_id: str) -> bool:
        """Check if user is authenticated (not anonymous)."""
        return not user_id.startswith("anonymous_") and not user_id.startswith("ws_anonymous_")
    
    def get_or_create_conversation_memory(self, user_id: str, session_id: str) -> ConversationMemory:
        """Get existing conversation memory or create new session."""
        session_key = self.get_session_key(user_id, session_id)
        is_authenticated = self.is_authenticated_user(user_id)
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            # Check if session exists
            cursor.execute("""
                SELECT * FROM conversation_sessions 
                WHERE session_key = %s AND last_activity > %s
            """, (session_key, datetime.now() - self.session_timeout))
            
            row = cursor.fetchone()
            
            if row:
                # Load existing session
                memory = self._load_conversation_memory(cursor, session_key, dict(row))
                self.logger.info(f"Loaded existing session: {session_key}")
            else:
                # Create new session
                memory = ConversationMemory(
                    session_id=session_id,
                    user_id=user_id
                )
                self._save_conversation_memory(cursor, session_key, memory, is_authenticated)
                self.logger.info(f"Created new {'persistent' if is_authenticated else 'temporary'} session: {session_key}")
            
            conn.commit()
            conn.close()
            return memory
            
        except Exception as e:
            self.logger.error(f"Error managing conversation memory: {e}")
            # Fallback to in-memory session
            return ConversationMemory(session_id=session_id, user_id=user_id)
    
    def _load_conversation_memory(self, cursor, session_key: str, session_data: Dict) -> ConversationMemory:
        """Load conversation memory from database."""
        # Create base memory object
        memory = ConversationMemory(
            session_id=session_data['session_id'],
            user_id=session_data['user_id']
        )
        
        # Load session metadata
        memory.session_start = session_data['session_start'] if isinstance(session_data['session_start'], datetime) else datetime.fromisoformat(str(session_data['session_start']))
        memory.last_activity = session_data['last_activity'] if isinstance(session_data['last_activity'], datetime) else datetime.fromisoformat(str(session_data['last_activity']))
        memory.active_agent = session_data['active_agent']
        memory.conversation_state = ConversationState(session_data['conversation_state'])
        
        # Load health topics
        if session_data['health_topics']:
            memory.health_topics_discussed = session_data['health_topics']  # Already parsed as JSONB
        
        # Load conversation history
        cursor.execute("""
            SELECT role, content, agent_id, timestamp, metadata
            FROM conversation_messages 
            WHERE session_key = %s
            ORDER BY message_index ASC
        """, (session_key,))
        
        messages = cursor.fetchall()
        memory.conversation_history = []
        
        for msg in messages:
            message_data = {
                "role": msg['role'],
                "content": msg['content'],
                "timestamp": msg['timestamp'],
                "agent_id": msg['agent_id']
            }
            if msg['metadata']:
                message_data.update(msg['metadata'])  # Already parsed as JSONB
            memory.conversation_history.append(message_data)
        
        return memory
    
    def _save_conversation_memory(self, cursor, session_key: str, memory: ConversationMemory, is_authenticated: bool):
        """Save conversation memory to database."""
        # Insert or update session using PostgreSQL UPSERT
        cursor.execute("""
            INSERT INTO conversation_sessions (
                session_key, user_id, session_id, is_authenticated,
                session_start, last_activity, conversation_state,
                active_agent, health_topics
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_key) DO UPDATE SET
                last_activity = EXCLUDED.last_activity,
                conversation_state = EXCLUDED.conversation_state,
                active_agent = EXCLUDED.active_agent,
                health_topics = EXCLUDED.health_topics
        """, (
            session_key,
            memory.user_id,
            memory.session_id,
            is_authenticated,
            memory.session_start,
            memory.last_activity,
            memory.conversation_state.value,
            memory.active_agent,
            json.dumps(memory.health_topics_discussed)
        ))
    
    def update_conversation_history(self, user_id: str, session_id: str, content: str, role: str, agent_id: Optional[str] = None, metadata: Optional[Dict] = None):
        """Update conversation history with new message."""
        session_key = self.get_session_key(user_id, session_id)
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get current message count for this session
            cursor.execute("SELECT COUNT(*) FROM conversation_messages WHERE session_key = %s", (session_key,))
            message_index = cursor.fetchone()[0]
            
            # Insert new message
            cursor.execute("""
                INSERT INTO conversation_messages (
                    session_key, message_index, role, content, agent_id, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                session_key,
                message_index,
                role,
                content[:1000],  # Limit message length
                agent_id,
                json.dumps(metadata) if metadata else None
            ))
            
            # Update session last activity
            cursor.execute("""
                UPDATE conversation_sessions 
                SET last_activity = CURRENT_TIMESTAMP 
                WHERE session_key = %s
            """, (session_key,))
            
            conn.commit()
            conn.close()
            self.logger.debug(f"Updated conversation history for {session_key}")
            
        except Exception as e:
            self.logger.error(f"Error updating conversation history: {e}")
    
    def clear_temporary_session(self, user_id: str, session_id: str) -> bool:
        """Clear a temporary session (for anonymous users)."""
        if self.is_authenticated_user(user_id):
            return False
        
        session_key = self.get_session_key(user_id, session_id)
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Delete messages first (foreign key constraint)
            cursor.execute("DELETE FROM conversation_messages WHERE session_key = %s", (session_key,))
            
            # Delete session
            cursor.execute("DELETE FROM conversation_sessions WHERE session_key = %s AND is_authenticated = FALSE", (session_key,))
            
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            if deleted:
                self.logger.info(f"Cleared temporary session: {session_key}")
            return deleted
            
        except Exception as e:
            self.logger.error(f"Error clearing temporary session: {e}")
            return False
    
    def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Find expired sessions
            expired_cutoff = datetime.now() - self.session_timeout
            cursor.execute("""
                SELECT session_key FROM conversation_sessions 
                WHERE last_activity < %s
            """, (expired_cutoff,))
            
            expired_sessions = [row[0] for row in cursor.fetchall()]
            
            if expired_sessions:
                # Delete messages for expired sessions
                for session_key in expired_sessions:
                    cursor.execute("DELETE FROM conversation_messages WHERE session_key = %s", (session_key,))
                
                # Delete expired sessions
                cursor.execute("""
                    DELETE FROM conversation_sessions 
                    WHERE last_activity < %s
                """, (expired_cutoff,))
                
                conn.commit()
                self.logger.info(f"Cleaned up {len(expired_sessions)} expired sessions")
            
            conn.close()
            return len(expired_sessions)
            
        except Exception as e:
            self.logger.error(f"Error cleaning up expired sessions: {e}")
            return 0
    
    def get_session_info(self, user_id: str, session_id: str) -> Dict[str, Any]:
        """Get information about a session."""
        session_key = self.get_session_key(user_id, session_id)
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute("""
                SELECT s.*, COUNT(m.id) as message_count
                FROM conversation_sessions s
                LEFT JOIN conversation_messages m ON s.session_key = m.session_key
                WHERE s.session_key = %s
                GROUP BY s.id, s.session_key, s.user_id, s.session_id, s.is_authenticated, 
                         s.session_start, s.last_activity, s.conversation_state, 
                         s.active_agent, s.language_preference, s.health_topics, s.conversation_data
            """, (session_key,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "session_id": row['session_id'],
                    "user_id": row['user_id'],
                    "is_persistent": bool(row['is_authenticated']),
                    "created": row['session_start'],
                    "last_activity": row['last_activity'],
                    "message_count": row['message_count'],
                    "health_topics": row['health_topics'] if row['health_topics'] else [],
                    "active_agent": row['active_agent'],
                    "exists": True
                }
            
            return {"exists": False}
            
        except Exception as e:
            self.logger.error(f"Error getting session info: {e}")
            return {"exists": False, "error": str(e)}
