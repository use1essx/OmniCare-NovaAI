#!/usr/bin/env python3
"""
User Manager for Live2D Chatbot
Handles user authentication, profile management, and chat history integration
"""

import json
import asyncio
import aiohttp
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class UserManager:
    """
    Manages user authentication, profiles, and chat history for Live2D chatbot
    """
    
    def __init__(self, healthcare_api_url: str = None):
        import os
        if healthcare_api_url is None:
            healthcare_api_url = os.getenv('HEALTHCARE_AI_URL', 'http://172.21.0.5:8000')
        self.healthcare_api_url = healthcare_api_url.rstrip('/')
        
        # Local SQLite database for caching user data and chat history
        self.db_path = Path(__file__).parent / "user_data.db"
        self.init_local_db()
        
    def init_local_db(self):
        """Initialize local SQLite database for offline functionality"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # User cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    email TEXT,
                    username TEXT,
                    full_name TEXT,
                    language_preference TEXT DEFAULT 'en',
                    last_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    auth_token TEXT,
                    health_profile TEXT,
                    UNIQUE(user_id)
                )
            """)
            
            # Chat history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    session_id TEXT,
                    user_message TEXT,
                    agent_response TEXT,
                    agent_type TEXT,
                    urgency_level TEXT,
                    language TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    live2d_data TEXT,
                    health_context_used TEXT
                )
            """)
            
            # Create indexes separately
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_user_session ON chat_history(user_id, session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_timestamp ON chat_history(timestamp)")
            
            # User sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    session_id TEXT UNIQUE,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    guest_mode INTEGER DEFAULT 0
                )
            """)
            
            # Create indexes separately
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_session ON user_sessions(session_id)")
            
            conn.commit()
            conn.close()
            logger.info("✅ Local user database initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize local database: {e}")
    
    async def validate_token(self, token: str) -> Optional[Dict]:
        """Validate user token with Healthcare AI backend"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.healthcare_api_url}/api/v1/auth/me",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        
                        # Cache user data locally
                        await self.cache_user_data(user_data, token)
                        
                        return user_data
                    else:
                        logger.warning(f"Token validation failed: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            return None
    
    async def cache_user_data(self, user_data: Dict, token: str):
        """Cache user data locally for offline access"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, email, username, full_name, language_preference, 
                 last_sync, auth_token)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_data.get('id'),
                user_data.get('email'),
                user_data.get('username'),
                user_data.get('full_name'),
                user_data.get('language_preference', 'en'),
                datetime.now(),
                token
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to cache user data: {e}")
    
    async def get_user_health_profile(self, user_id: int, token: str) -> Optional[Dict]:
        """Get user's health profile from Healthcare AI backend"""
        try:
            headers = {"Authorization": f"Bearer {token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.healthcare_api_url}/api/v1/auth/health-profile",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        health_profile = await response.json()
                        
                        # Cache health profile locally
                        await self.cache_health_profile(user_id, health_profile)
                        
                        return health_profile
                    elif response.status == 404:
                        # No health profile exists yet
                        return None
                    else:
                        logger.warning(f"Health profile fetch failed: {response.status}")
                        return await self.get_cached_health_profile(user_id)
                        
        except Exception as e:
            logger.error(f"Health profile fetch error: {e}")
            return await self.get_cached_health_profile(user_id)
    
    async def cache_health_profile(self, user_id: int, health_profile: Dict):
        """Cache health profile locally"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE users SET health_profile = ? WHERE user_id = ?
            """, (json.dumps(health_profile), user_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to cache health profile: {e}")
    
    async def get_cached_health_profile(self, user_id: int) -> Optional[Dict]:
        """Get cached health profile"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT health_profile FROM users WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                return json.loads(result[0])
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached health profile: {e}")
            return None
    
    async def save_chat_history(self, user_id: Optional[int], session_id: str, 
                               user_message: str, agent_response: str, 
                               agent_data: Dict, live2d_data: Dict):
        """Save chat interaction to local database and sync with backend"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO chat_history 
                (user_id, session_id, user_message, agent_response, agent_type, 
                 urgency_level, language, live2d_data, health_context_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                session_id,
                user_message,
                agent_response,
                agent_data.get('agent_type', 'unknown'),
                agent_data.get('urgency_level', 'low'),
                agent_data.get('language', 'en'),
                json.dumps(live2d_data),
                json.dumps(agent_data.get('health_context_used', {}))
            ))
            
            conn.commit()
            conn.close()
            
            # Asynchronously sync with backend if user is authenticated
            if user_id:
                asyncio.create_task(self.sync_chat_to_backend(user_id, session_id, 
                                                            user_message, agent_response, agent_data))
            
        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")
    
    async def sync_chat_to_backend(self, user_id: int, session_id: str, 
                                  user_message: str, agent_response: str, agent_data: Dict):
        """Sync chat history to Healthcare AI backend"""
        try:
            # Get user token from cache
            token = await self.get_cached_user_token(user_id)
            if not token:
                return
            
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            
            conversation_data = {
                "session_id": session_id,
                "user_input": user_message,
                "agent_response": agent_response,
                "agent_type": agent_data.get('agent_type'),
                "agent_confidence": agent_data.get('confidence', 0.8),
                "urgency_level": agent_data.get('urgency_level'),
                "language": agent_data.get('language'),
                "hk_data_used": agent_data.get('hk_data_used', []),
                "processing_time_ms": agent_data.get('processing_time_ms', 1000)
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.healthcare_api_url}/api/v1/agents/conversations",
                    headers=headers,
                    json=conversation_data
                ) as response:
                    if response.status == 201:
                        logger.info("✅ Chat synced to backend")
                    else:
                        logger.warning(f"Chat sync failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"Failed to sync chat to backend: {e}")
    
    async def get_cached_user_token(self, user_id: int) -> Optional[str]:
        """Get cached user token"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT auth_token FROM users WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else None
            
        except Exception as e:
            logger.error(f"Failed to get cached token: {e}")
            return None
    
    async def get_chat_history(self, user_id: Optional[int], session_id: str, 
                              limit: int = 10) -> List[Dict]:
        """Get recent chat history for context"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if user_id:
                # Get user's chat history across all sessions
                cursor.execute("""
                    SELECT user_message, agent_response, agent_type, urgency_level, 
                           language, timestamp, live2d_data, health_context_used
                    FROM chat_history 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (user_id, limit))
            else:
                # Get session-specific history for guest users
                cursor.execute("""
                    SELECT user_message, agent_response, agent_type, urgency_level, 
                           language, timestamp, live2d_data, health_context_used
                    FROM chat_history 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                """, (session_id, limit))
            
            results = cursor.fetchall()
            conn.close()
            
            history = []
            for row in results:
                history.append({
                    'user_message': row[0],
                    'agent_response': row[1],
                    'agent_type': row[2],
                    'urgency_level': row[3],
                    'language': row[4],
                    'timestamp': row[5],
                    'live2d_data': json.loads(row[6]) if row[6] else {},
                    'health_context_used': json.loads(row[7]) if row[7] else {}
                })
            
            return list(reversed(history))  # Return in chronological order
            
        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            return []
    
    async def create_session(self, user_id: Optional[int], session_id: str, 
                           guest_mode: bool = False):
        """Create or update user session"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO user_sessions 
                (user_id, session_id, started_at, last_activity, is_active, guest_mode)
                VALUES (?, ?, ?, ?, 1, ?)
            """, (user_id, session_id, datetime.now(), datetime.now(), int(guest_mode)))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
    
    async def update_session_activity(self, session_id: str):
        """Update session last activity"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE user_sessions 
                SET last_activity = ? 
                WHERE session_id = ?
            """, (datetime.now(), session_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update session activity: {e}")
    
    async def get_user_context(self, user_id: Optional[int], token: Optional[str]) -> Dict:
        """Get comprehensive user context for personalized responses"""
        context = {
            'user_id': user_id,
            'is_authenticated': user_id is not None,
            'health_profile': None,
            'preferences': {
                'language': 'en',
                'interaction_style': 'professional',
                'urgency_sensitivity': 'normal'
            },
            'health_context': {
                'chronic_conditions': [],
                'current_medications': [],
                'allergies': [],
                'health_goals': []
            }
        }
        
        if user_id and token:
            try:
                # Get user data
                user_data = await self.validate_token(token)
                if user_data:
                    context['preferences']['language'] = user_data.get('language_preference', 'en')
                
                # Get health profile
                health_profile = await self.get_user_health_profile(user_id, token)
                if health_profile:
                    context['health_profile'] = health_profile
                    context['health_context'].update({
                        'chronic_conditions': health_profile.get('chronic_conditions', []),
                        'current_medications': health_profile.get('current_medications', []),
                        'allergies': health_profile.get('allergies', []),
                        'health_goals': health_profile.get('health_goals', [])
                    })
                    context['preferences'].update({
                        'interaction_style': health_profile.get('interaction_style', 'professional'),
                        'urgency_sensitivity': health_profile.get('urgency_sensitivity', 'normal')
                    })
                
            except Exception as e:
                logger.error(f"Failed to get user context: {e}")
        
        return context
    
    def get_personalized_prompt_context(self, user_context: Dict, 
                                       chat_history: List[Dict]) -> str:
        """Generate personalized context for AI prompts"""
        context_parts = []
        
        if user_context['is_authenticated']:
            context_parts.append("User is authenticated and has a health profile.")
            
            health_profile = user_context.get('health_profile')
            if health_profile:
                age = health_profile.get('age')
                if age:
                    context_parts.append(f"User age: {age}")
                
                conditions = user_context['health_context'].get('chronic_conditions', [])
                if conditions:
                    context_parts.append(f"Known conditions: {', '.join(conditions)}")
                
                medications = user_context['health_context'].get('current_medications', [])
                if medications:
                    med_names = [med.get('name', str(med)) for med in medications if med]
                    context_parts.append(f"Current medications: {', '.join(med_names[:3])}")
                
                allergies = user_context['health_context'].get('allergies', [])
                if allergies:
                    context_parts.append(f"Known allergies: {', '.join(allergies[:3])}")
        
        # Add recent conversation context
        if chat_history:
            recent_topics = []
            for chat in chat_history[-3:]:  # Last 3 conversations
                if chat.get('health_context_used'):
                    topics = chat['health_context_used'].get('topics', [])
                    recent_topics.extend(topics)
            
            if recent_topics:
                unique_topics = list(set(recent_topics))
                context_parts.append(f"Recent topics discussed: {', '.join(unique_topics[:3])}")
        
        return " ".join(context_parts) if context_parts else "No specific user context available."


# Global user manager instance
user_manager = None

def get_user_manager():
    """Get or create the global user manager instance"""
    global user_manager
    if user_manager is None:
        user_manager = UserManager()
    return user_manager
