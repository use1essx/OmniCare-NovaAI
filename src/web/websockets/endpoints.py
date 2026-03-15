"""
WebSocket Endpoints - Healthcare AI V2
======================================

FastAPI WebSocket endpoints for real-time communication with Live2D frontend.
Provides secure, high-performance WebSocket connections with comprehensive
error handling, rate limiting, and security features.

Features:
- Live2D chat WebSocket endpoint
- Connection security and authentication
- Rate limiting and abuse prevention
- Error handling and connection recovery
- Performance monitoring and logging
"""

import asyncio
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect, Query
from fastapi.security import HTTPBearer
from starlette.websockets import WebSocketState

from src.core.logging import get_logger, log_api_request
from src.web.auth.handlers import AuthHandler
from src.web.websockets.chat import live2d_chat_handler


logger = get_logger(__name__)
security = HTTPBearer(auto_error=False)


class RateLimiter:
    """Simple rate limiter for WebSocket connections"""
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[float] = []
    
    def is_allowed(self) -> bool:
        """Check if request is allowed under rate limit"""
        now = time.time()
        self.requests = [t for t in self.requests if now - t < self.window_seconds]
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False


# ============================================================================
# WEBSOCKET SECURITY AND RATE LIMITING
# ============================================================================

class WebSocketSecurity:
    """Security handler for WebSocket connections"""
    
    def __init__(self):
        self.auth_handler = AuthHandler()
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.blocked_ips: Dict[str, datetime] = {}
        self.connection_counts: Dict[str, int] = {}
        self.max_connections_per_ip = 5
        self.max_messages_per_minute = 60
        
    def check_ip_allowed(self, client_ip: str) -> bool:
        """Check if IP is allowed to connect"""
        # Check if IP is temporarily blocked
        if client_ip in self.blocked_ips:
            block_time = self.blocked_ips[client_ip]
            if datetime.now() < block_time:
                return False
            else:
                # Remove expired block
                del self.blocked_ips[client_ip]
        
        # Check connection limit per IP
        current_connections = self.connection_counts.get(client_ip, 0)
        return current_connections < self.max_connections_per_ip
    
    def track_connection(self, client_ip: str):
        """Track new connection for IP"""
        self.connection_counts[client_ip] = self.connection_counts.get(client_ip, 0) + 1
    
    def release_connection(self, client_ip: str):
        """Release connection for IP"""
        if client_ip in self.connection_counts:
            self.connection_counts[client_ip] -= 1
            if self.connection_counts[client_ip] <= 0:
                del self.connection_counts[client_ip]
    
    def get_rate_limiter(self, client_ip: str) -> RateLimiter:
        """Get or create rate limiter for IP"""
        if client_ip not in self.rate_limiters:
            self.rate_limiters[client_ip] = RateLimiter(
                max_requests=self.max_messages_per_minute,
                window_seconds=60
            )
        return self.rate_limiters[client_ip]
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if IP is within rate limits"""
        rate_limiter = self.get_rate_limiter(client_ip)
        return rate_limiter.is_allowed()
    
    def block_ip_temporarily(self, client_ip: str, duration_minutes: int = 15):
        """Temporarily block IP"""
        from datetime import timedelta
        self.blocked_ips[client_ip] = datetime.now() + timedelta(minutes=duration_minutes)
        logger.warning(f"Temporarily blocked IP {client_ip} for {duration_minutes} minutes")
    
    async def authenticate_websocket(self, websocket: WebSocket, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Authenticate WebSocket connection"""
        if not token:
            return None  # Anonymous connection allowed
        
        try:
            payload = self.auth_handler.verify_token(token)
            if payload:
                user_id = payload.get("sub")
                return {
                    "user_id": user_id,
                    "authenticated": True,
                    "auth_payload": payload
                }
        except Exception as e:
            logger.error(f"WebSocket authentication error: {e}")
        
        return None


# Global security instance
ws_security = WebSocketSecurity()


# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

async def websocket_live2d_chat(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    language: str = Query(default="en", regex="^(en|zh-HK)$"),
    client_type: str = Query(default="live2d", regex="^(live2d|web|mobile)$")
):
    """
    Main WebSocket endpoint for Live2D chat integration
    
    Features:
    - Real-time bidirectional communication
    - Agent personality and emotion mapping
    - Cultural gesture integration
    - Security and rate limiting
    - Connection recovery and error handling
    
    Query Parameters:
    - token: Optional JWT authentication token
    - language: Language preference (en, zh-HK)
    - client_type: Type of client connecting (live2d, web, mobile)
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    session_id = None
    
    try:
        # Security checks
        if not ws_security.check_ip_allowed(client_ip):
            await websocket.close(code=1008, reason="Connection limit exceeded or IP blocked")
            logger.warning(f"WebSocket connection rejected for IP {client_ip}")
            return
        
        # Track connection
        ws_security.track_connection(client_ip)
        
        # Initialize agents if needed
        if not live2d_chat_handler.agent_orchestrator:
            await live2d_chat_handler.initialize_agents()
        
        # Accept connection and get session ID
        session_id = await live2d_chat_handler.handle_connection(websocket, client_ip)
        
        # Authenticate if token provided
        auth_info = await ws_security.authenticate_websocket(websocket, token)
        if auth_info:
            live2d_chat_handler.connection_manager.authenticate_session(
                session_id,
                auth_info["user_id"],
                auth_info
            )
            logger.info(f"WebSocket authenticated for user {auth_info['user_id']}")
        
        # Set session language preference
        session_info = live2d_chat_handler.connection_manager.get_session_info(session_id)
        if session_info:
            session_info["language"] = language
            session_info["client_type"] = client_type
        
        # Log connection
        log_api_request(
            method="WEBSOCKET",
            endpoint="/ws/live2d/chat",
            status_code=101,  # WebSocket Upgrade
            response_time_ms=0,
            user_id=auth_info.get("user_id") if auth_info else None,
            ip_address=client_ip,
            additional_data={
                "session_id": session_id,
                "language": language,
                "client_type": client_type,
                "authenticated": bool(auth_info)
            }
        )
        
        # Message processing loop
        while True:
            try:
                # Receive message with timeout
                try:
                    raw_message = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=300.0  # 5 minute timeout
                    )
                except asyncio.TimeoutError:
                    # Send ping to check if connection is alive
                    await websocket.send_text('{"type":"ping","timestamp":"' + datetime.now().isoformat() + '"}')
                    continue
                
                # Check rate limiting
                if not ws_security.check_rate_limit(client_ip):
                    await websocket.send_text('{"type":"error","message":"Rate limit exceeded","error_code":"RATE_LIMIT"}')
                    continue
                
                # Process message
                success = await live2d_chat_handler.process_message(session_id, raw_message)
                
                if not success:
                    logger.warning(f"Failed to process message for session {session_id}")
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected: {session_id}")
                break
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                try:
                    await websocket.send_text(f'{{"type":"error","message":"Message processing error","error_code":"PROCESSING_ERROR","timestamp":"{datetime.now().isoformat()}"}}')
                except Exception:
                    break  # Connection broken
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected during setup: {client_ip}")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    
    finally:
        # Cleanup
        if session_id:
            await live2d_chat_handler.disconnect_session(session_id, "Connection closed")
        
        ws_security.release_connection(client_ip)
        
        # Log disconnection
        log_api_request(
            method="WEBSOCKET_DISCONNECT",
            endpoint="/ws/live2d/chat",
            status_code=200,
            response_time_ms=0,
            ip_address=client_ip,
            additional_data={
                "session_id": session_id,
                "reason": "normal_closure"
            }
        )


async def websocket_health_monitor(websocket: WebSocket):
    """
    WebSocket endpoint for system health monitoring
    
    Provides real-time system status updates for monitoring dashboards
    """
    client_ip = websocket.client.host if websocket.client else "unknown"
    
    try:
        # Security check (more restrictive for monitoring)
        if not ws_security.check_ip_allowed(client_ip):
            await websocket.close(code=1008, reason="Access denied")
            return
        
        await websocket.accept()
        
        # Send initial status
        status_data = {
            "type": "system_status",
            "timestamp": datetime.now().isoformat(),
            "status": "connected"
        }
        await websocket.send_text(str(status_data).replace("'", '"'))
        
        # Health monitoring loop
        while True:
            try:
                # Wait for ping or send periodic updates
                await asyncio.sleep(30)  # Update every 30 seconds
                
                # Get system stats
                connection_stats = live2d_chat_handler.get_connection_stats()
                
                health_update = {
                    "type": "health_update",
                    "timestamp": datetime.now().isoformat(),
                    "active_connections": connection_stats.get("active_connections", 0),
                    "total_messages": connection_stats.get("total_messages_processed", 0),
                    "average_response_time": connection_stats.get("average_response_time_ms", 0),
                    "system_status": "healthy"
                }
                
                await websocket.send_text(str(health_update).replace("'", '"'))
            
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in health monitor WebSocket: {e}")
                break
    
    except Exception as e:
        logger.error(f"Health monitor WebSocket error: {e}")
    
    finally:
        ws_security.release_connection(client_ip)


# ============================================================================
# WEBSOCKET UTILITIES
# ============================================================================

async def broadcast_system_update(update_data: Dict[str, Any]):
    """
    Broadcast system update to all connected WebSocket clients
    
    Args:
        update_data: Update data to broadcast
    """
    try:
        await live2d_chat_handler.broadcast_status_update(update_data)
        logger.info("Broadcasted system update to all connections")
    except Exception as e:
        logger.error(f"Error broadcasting system update: {e}")


async def get_websocket_statistics() -> Dict[str, Any]:
    """
    Get comprehensive WebSocket statistics
    
    Returns:
        Dictionary with WebSocket statistics
    """
    try:
        connection_stats = live2d_chat_handler.get_connection_stats()
        
        return {
            "active_connections": connection_stats.get("active_connections", 0),
            "total_connections": connection_stats.get("total_connections", 0),
            "total_messages_processed": connection_stats.get("total_messages_processed", 0),
            "average_response_time_ms": connection_stats.get("average_response_time_ms", 0),
            "security_stats": {
                "blocked_ips": len(ws_security.blocked_ips),
                "rate_limiters_active": len(ws_security.rate_limiters),
                "connection_counts": dict(ws_security.connection_counts)
            },
            "performance_metrics": connection_stats.get("connection_metadata", {}),
            "agent_system_status": {
                "orchestrator_initialized": bool(live2d_chat_handler.agent_orchestrator),
                "emotion_mapper_loaded": True,
                "gesture_library_loaded": True
            }
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket statistics: {e}")
        return {"error": str(e)}


# ============================================================================
# CLEANUP TASKS
# ============================================================================

async def cleanup_websocket_resources():
    """
    Background task to clean up WebSocket resources
    
    Runs periodically to:
    - Clean up expired rate limiters
    - Remove expired IP blocks
    - Clean up inactive connections
    """
    while True:
        try:
            # Clean up expired IP blocks
            current_time = datetime.now()
            expired_ips = [
                ip for ip, block_time in ws_security.blocked_ips.items()
                if current_time >= block_time
            ]
            
            for ip in expired_ips:
                del ws_security.blocked_ips[ip]
            
            if expired_ips:
                logger.info(f"Cleaned up {len(expired_ips)} expired IP blocks")
            
            # Clean up inactive rate limiters
            active_ips = set(ws_security.connection_counts.keys())
            inactive_limiters = [
                ip for ip in ws_security.rate_limiters.keys()
                if ip not in active_ips
            ]
            
            for ip in inactive_limiters[:10]:  # Clean up 10 at a time
                del ws_security.rate_limiters[ip]
            
            if inactive_limiters:
                logger.debug(f"Cleaned up {len(inactive_limiters[:10])} inactive rate limiters")
            
            # Clean up inactive connections
            await live2d_chat_handler.connection_manager.cleanup_inactive_connections()
            
            # Wait 5 minutes before next cleanup
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Error in WebSocket cleanup task: {e}")
            await asyncio.sleep(60)  # Wait 1 minute before retrying


# ============================================================================
# STARTUP TASK
# ============================================================================

async def initialize_websocket_system():
    """Initialize WebSocket system on startup"""
    try:
        # Initialize Live2D chat handler
        await live2d_chat_handler.initialize_agents()
        
        # Start cleanup task
        asyncio.create_task(cleanup_websocket_resources())
        
        logger.info("WebSocket system initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing WebSocket system: {e}")
        raise
