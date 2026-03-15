"""
Healthcare AI V2 - pgAdmin Integration Module
Provides seamless integration between Healthcare AI admin interface and pgAdmin
"""

import hashlib
import hmac
import time
from typing import Dict, Optional, Any

import aiohttp
import logging
from datetime import datetime, timedelta

try:
    import jwt
except ImportError:  # pragma: no cover - dependency guard
    jwt = None  # type: ignore[assignment]

from fastapi import HTTPException, status
from src.core.config import settings
from src.database.repositories.user_repository import UserRepository
from src.security.auth import get_password_hash, verify_password

# Create PasswordHasher-like object for backward compatibility
PasswordHasher = type('PasswordHasher', (), {
    'hash_password': lambda self, pwd: get_password_hash(pwd),
    'verify_password': lambda self, plain, hashed: verify_password(plain, hashed)
})


logger = logging.getLogger(__name__)
JWT_ALGORITHM = "HS256"
JWT_DEPENDENCY_ERROR = (
    "PyJWT is required for pgAdmin single sign-on but is not installed on the server."
)


class PgAdminIntegration:
    """
    Handles authentication bridge and integration between Healthcare AI admin and pgAdmin
    """
    
    def __init__(self):
        import os
        self.pgadmin_url = f"http://localhost:{os.getenv('PGADMIN_PORT', '5050')}"
        self.pgadmin_email = os.getenv('PGADMIN_EMAIL', 'admin@healthcare-ai.com')
        # IMPORTANT: Change this password in production via PGADMIN_PASSWORD env var
        self.pgadmin_password = os.getenv('PGADMIN_PASSWORD', 'CHANGE_THIS_IN_PRODUCTION')
        self.user_repo = UserRepository()
        self.session_cache = {}  # In production, use Redis
        
    async def create_sso_token(self, user_id: int, user_email: str) -> str:
        """
        Create a secure SSO token for pgAdmin authentication
        """
        try:
            if jwt is None:
                logger.error("PyJWT dependency missing while creating SSO token")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=JWT_DEPENDENCY_ERROR
                )
            
            # Create JWT token with user info and expiration
            payload = {
                'user_id': user_id,
                'email': user_email,
                'pgadmin_access': True,
                'iat': datetime.utcnow(),
                'exp': datetime.utcnow() + timedelta(hours=8),  # 8 hour session
                'iss': 'healthcare_ai_v2'
            }
            
            token = jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)
            
            # Cache token for validation
            self.session_cache[token] = {
                'user_id': user_id,
                'email': user_email,
                'created_at': datetime.utcnow()
            }
            
            logger.info(f"Created SSO token for user {user_email}")
            return token
            
        except Exception as e:
            logger.error(f"Error creating SSO token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create authentication token"
            )
    
    async def validate_sso_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate SSO token and return user information
        """
        try:
            if jwt is None:
                logger.error("PyJWT dependency missing while validating SSO token")
                return None
            
            # Decode and validate JWT
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALGORITHM])
            
            # Check if token is in cache (for additional security)
            if token not in self.session_cache:
                logger.warning(f"Token not found in session cache: {token[:20]}...")
                return None
            
            # Verify user still exists and is active
            user = await self.user_repo.get_by_id(payload['user_id'])
            if not user or not user.is_active:
                logger.warning(f"User not found or inactive: {payload['user_id']}")
                return None
            
            # Check if user has admin privileges
            if not (user.is_admin or user.role in ['admin', 'medical_reviewer', 'data_manager']):
                logger.warning(f"User lacks admin privileges: {user.email}")
                return None
            
            return {
                'user_id': user.id,
                'email': user.email,
                'role': user.role,
                'full_name': user.full_name
            }
            
        except jwt.ExpiredSignatureError:
            logger.warning("SSO token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid SSO token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error validating SSO token: {e}")
            return None
    
    async def generate_pgadmin_redirect_url(self, user_info: Dict[str, Any]) -> str:
        """
        Generate pgAdmin redirect URL with authentication
        """
        try:
            # Create secure parameters for pgAdmin authentication
            timestamp = str(int(time.time()))
            
            # Create HMAC signature for security
            message = f"{user_info['email']}:{timestamp}"
            signature = hmac.new(
                settings.SECRET_KEY.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Build redirect URL with authentication parameters
            redirect_url = (
                f"{self.pgadmin_url}/browser/"
                f"?sso_email={user_info['email']}"
                f"&timestamp={timestamp}"
                f"&signature={signature}"
                f"&healthcare_ai_session=true"
            )
            
            logger.info(f"Generated pgAdmin redirect URL for {user_info['email']}")
            return redirect_url
            
        except Exception as e:
            logger.error(f"Error generating pgAdmin redirect URL: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate pgAdmin access URL"
            )
    
    async def authenticate_user_for_pgadmin(
        self, 
        user_id: int, 
        password: str
    ) -> Dict[str, Any]:
        """
        Authenticate user and prepare for pgAdmin access
        """
        try:
            # Get user from database
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found"
                )
            
            # Verify password
            password_hasher = PasswordHasher()
            if not password_hasher.verify_password(password, user.hashed_password):
                # Log failed attempt
                logger.warning(f"Failed pgAdmin access attempt for user {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials"
                )
            
            # Check if user has admin privileges
            if not (user.is_admin or user.role in ['admin', 'medical_reviewer', 'data_manager']):
                logger.warning(f"Unauthorized pgAdmin access attempt by {user.email}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient privileges for database access"
                )
            
            # Create SSO token
            sso_token = await self.create_sso_token(user.id, user.email)
            
            # Generate pgAdmin redirect URL
            user_info = {
                'user_id': user.id,
                'email': user.email,
                'role': user.role,
                'full_name': user.full_name
            }
            
            redirect_url = await self.generate_pgadmin_redirect_url(user_info)
            
            # Log successful authentication
            logger.info(f"Successful pgAdmin authentication for {user.email}")
            
            return {
                'sso_token': sso_token,
                'redirect_url': redirect_url,
                'user_info': user_info,
                'expires_at': (datetime.utcnow() + timedelta(hours=8)).isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in pgAdmin authentication: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication failed"
            )
    
    async def revoke_sso_session(self, token: str) -> bool:
        """
        Revoke SSO session (logout from pgAdmin)
        """
        try:
            # Remove from session cache
            if token in self.session_cache:
                user_email = self.session_cache[token].get('email', 'unknown')
                del self.session_cache[token]
                logger.info(f"Revoked pgAdmin SSO session for {user_email}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error revoking SSO session: {e}")
            return False
    
    async def get_active_pgadmin_sessions(self) -> list:
        """
        Get list of active pgAdmin sessions
        """
        try:
            current_time = datetime.utcnow()
            active_sessions = []
            
            for token, session_data in self.session_cache.items():
                # Check if session is still valid (not expired)
                created_at = session_data['created_at']
                if current_time - created_at < timedelta(hours=8):
                    active_sessions.append({
                        'user_id': session_data['user_id'],
                        'email': session_data['email'],
                        'created_at': created_at.isoformat(),
                        'token_preview': token[:20] + '...'
                    })
            
            return active_sessions
            
        except Exception as e:
            logger.error(f"Error getting active pgAdmin sessions: {e}")
            return []
    
    async def check_pgadmin_health(self) -> Dict[str, Any]:
        """
        Check pgAdmin service health and connectivity
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Check if pgAdmin is responding
                async with session.get(
                    f"{self.pgadmin_url}/misc/ping",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        return {
                            'status': 'healthy',
                            'url': self.pgadmin_url,
                            'response_time_ms': 0,  # Could measure this
                            'version': 'pgAdmin 4',
                            'active_sessions': len(self.session_cache)
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'error': f"HTTP {response.status}",
                            'url': self.pgadmin_url
                        }
                        
        except aiohttp.ClientError as e:
            logger.error(f"pgAdmin health check failed: {e}")
            return {
                'status': 'unavailable',
                'error': str(e),
                'url': self.pgadmin_url
            }
        except Exception as e:
            logger.error(f"Error checking pgAdmin health: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    async def cleanup_expired_sessions(self):
        """
        Clean up expired SSO sessions (background task)
        """
        try:
            current_time = datetime.utcnow()
            expired_tokens = []
            
            for token, session_data in self.session_cache.items():
                created_at = session_data['created_at']
                if current_time - created_at > timedelta(hours=8):
                    expired_tokens.append(token)
            
            # Remove expired tokens
            for token in expired_tokens:
                del self.session_cache[token]
            
            if expired_tokens:
                logger.info(f"Cleaned up {len(expired_tokens)} expired pgAdmin sessions")
                
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
    
    async def auto_setup_healthcare_servers(self, admin_email: str) -> Dict[str, Any]:
        """
        Automatically setup Healthcare AI database servers in pgAdmin
        """
        try:
            logger.info(f"Starting auto-setup for pgAdmin servers by {admin_email}")
            
            # First, ensure pgAdmin is accessible
            health_check = await self.check_pgadmin_health()
            if health_check.get("status") not in ["healthy", "unhealthy"]:
                return {
                    "success": False,
                    "message": "pgAdmin is not accessible",
                    "error": health_check.get("error", "Unknown error")
                }
            
            # Try to setup servers via direct database manipulation
            setup_result = await self._setup_servers_via_database()
            
            if setup_result["success"]:
                logger.info(f"Auto-setup completed successfully by {admin_email}")
                return setup_result
            else:
                # Return manual instructions
                return {
                    "success": False,
                    "message": "Auto-setup not available, manual setup required",
                    "manual_instructions": {
                        "url": f"{self.pgadmin_url}/",
                        "email": self.pgadmin_email,
                        "password": self.pgadmin_password,
                        "server_config": {
                            "name": "Healthcare AI V2 - Primary Database",
                            "host": settings.DATABASE_HOST,
                            "port": settings.DATABASE_PORT,
                            "database": settings.DATABASE_NAME,
                            "username": settings.DATABASE_USER,
                            "password": settings.DATABASE_PASSWORD
                        }
                    }
                }
                        
        except Exception as e:
            logger.error(f"Auto-setup error: {e}")
            return {
                "success": False,
                "message": f"Auto-setup failed: {str(e)}"
            }
    
    async def _setup_servers_via_database(self) -> Dict[str, Any]:
        """
        Setup servers by directly manipulating pgAdmin's database
        """
        try:
            import subprocess
            
            setup_script = f'''
import sqlite3
import os

def setup_servers():
    db_path = "/var/lib/pgadmin/pgadmin4.db"
    
    if not os.path.exists(db_path):
        return False, "Database not found"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get admin user
        cursor.execute("SELECT id FROM user WHERE email = ?", ("{self.pgadmin_email}",))
        user_row = cursor.fetchone()
        
        if not user_row:
            conn.close()
            return False, "Admin user not found - login to pgAdmin first"
            
        user_id = user_row[0]
        
        # Check existing servers
        cursor.execute("SELECT COUNT(*) FROM server WHERE user_id = ? AND name LIKE ?", (user_id, "%Healthcare AI%"))
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            conn.close()
            return True, f"Found {{existing_count}} existing Healthcare AI server(s)"
        
        # Create Healthcare AI server
        cursor.execute("""
            INSERT INTO server (
                user_id, servergroup_id, name, host, port, 
                maintenance_db, username, ssl_mode, comment,
                discovery_id, hostaddr, db_res, passfile, 
                sslcert, sslkey, sslrootcert, sslcrl, sslcompression,
                bgcolor, fgcolor, service, use_ssh_tunnel, tunnel_host,
                tunnel_port, tunnel_username, tunnel_authentication,
                shared, restore_env
            ) VALUES (
                ?, 1, ?, ?, ?,
                ?, ?, ?, ?,
                '', '', '', '/pgadmin4/pgpass',
                '', '', '', '', 0,
                '', '', '', 0, '',
                22, '', 0,
                0, ''
            )
        """, (
            user_id,
            "Healthcare AI V2 - Primary Database",
            "{settings.DATABASE_HOST}",
            {settings.DATABASE_PORT},
            "{settings.DATABASE_NAME}",
            "{settings.DATABASE_USER}",
            "prefer",
            "Auto-configured Healthcare AI Database"
        ))
        
        conn.commit()
        conn.close()
        return True, "Server created successfully"
        
    except Exception as e:
        return False, f"Database error: {{e}}"

success, message = setup_servers()
print(f"RESULT:{{success}}:{{message}}")
'''
            
            # Execute the setup script in the pgAdmin container
            try:
                result = subprocess.run([
                    'docker-compose', 'exec', '-T', 'pgadmin', 
                    'python3', '-c', setup_script
                ], capture_output=True, text=True, timeout=30, cwd='/workspaces/fyp2526-use1essx/healthcare_ai_live2d_unified')
                
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if 'RESULT:True:' in output:
                        message = output.split('RESULT:True:')[1]
                        return {
                            "success": True,
                            "message": f"Healthcare AI database server configured: {message}",
                            "servers_created": ["Healthcare AI V2 - Primary Database"],
                            "total_servers": 1
                        }
                    elif 'RESULT:False:' in output:
                        message = output.split('RESULT:False:')[1]
                        return {
                            "success": False,
                            "message": message
                        }
                
                logger.warning(f"Database setup unexpected output: {result.stdout}")
                return {
                    "success": False,
                    "message": "Setup completed but result unclear",
                    "output": result.stdout
                }
                    
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "message": "Setup timeout - pgAdmin may be slow to respond"
                }
            except Exception as e:
                logger.error(f"Subprocess error: {e}")
                return {
                    "success": False,
                    "message": f"Setup execution failed: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"Database setup error: {e}")
            return {
                "success": False,
                "message": f"Database setup error: {str(e)}"
            }


# Global instance
pgadmin_integration = PgAdminIntegration()


async def get_pgadmin_integration() -> PgAdminIntegration:
    """
    Dependency injection for pgAdmin integration
    """
    return pgadmin_integration
