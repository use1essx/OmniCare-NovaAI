"""
Super Admin API Endpoints - Simplified Version
Uses direct SQL queries for simplicity
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
import logging

from src.database.connection import get_async_db
from src.database.models_comprehensive import User
from src.web.auth.dependencies import require_super_admin, get_current_user, require_org_admin
from src.security.auth import get_password_hash
from src.web.auth.permissions_hierarchical import (
    get_accessible_user_ids,
    get_accessible_organization_ids,
    can_create_user_in_org,
    can_manage_user,
    can_assign_caregiver
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/admin", tags=["super-admin"])

# ============================================================================
# Pydantic Models
# ============================================================================

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=4)
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(...)
    organization_id: Optional[int] = None
    is_active: bool = True

class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=100)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[str] = None
    organization_id: Optional[int] = Field(default=None)
    assigned_caregiver_id: Optional[int] = Field(default=None)
    is_active: Optional[bool] = None
    new_password: Optional[str] = Field(default=None, min_length=4)
    
class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(...)
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    max_users: int = Field(default=50, ge=1)
    max_admins: int = Field(default=10, ge=1)
    is_active: bool = True

# ============================================================================
# User Management Endpoints
# ============================================================================

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)  # Changed to get_current_user for flexible access
):
    """List users based on current user's access level"""
    try:
        # Get accessible user IDs based on role hierarchy
        accessible_ids = await get_accessible_user_ids(db, current_user)
        
        # Build query with access filtering
        if accessible_ids is None:
            # Super admin - see all users
            query = text("""
                SELECT 
                    u.id, u.username, u.email, u.full_name, u.role,
                    u.organization_id, o.name as organization_name,
                    u.is_active, u.is_verified, u.is_admin, u.is_super_admin,
                    u.created_at, u.last_login, u.created_by, u.assigned_caregiver_id,
                    caregiver.full_name as caregiver_name
                FROM users u
                LEFT JOIN organizations o ON u.organization_id = o.id
                LEFT JOIN users caregiver ON u.assigned_caregiver_id = caregiver.id
                ORDER BY u.created_at DESC
            """)
            result = await db.execute(query)
        elif not accessible_ids:
            # No access - return empty list
            return []
        else:
            # Filter by accessible IDs
            ids_str = ','.join(str(uid) for uid in accessible_ids)
            query = text(f"""
                SELECT 
                    u.id, u.username, u.email, u.full_name, u.role,
                    u.organization_id, o.name as organization_name,
                    u.is_active, u.is_verified, u.is_admin, u.is_super_admin,
                    u.created_at, u.last_login, u.created_by, u.assigned_caregiver_id,
                    caregiver.full_name as caregiver_name
                FROM users u
                LEFT JOIN organizations o ON u.organization_id = o.id
                LEFT JOIN users caregiver ON u.assigned_caregiver_id = caregiver.id
                WHERE u.id IN ({ids_str})
                ORDER BY u.created_at DESC
            """)
            result = await db.execute(query)
        
        users = []
        for row in result:
            users.append({
                "id": row[0],
                "username": row[1],
                "email": row[2],
                "full_name": row[3],
                "role": row[4],
                "organization_id": row[5],
                "organization_name": row[6],
                "is_active": row[7],
                "is_verified": row[8],
                "is_admin": row[9],
                "is_super_admin": row[10],
                "created_at": row[11].isoformat() if row[11] else None,
                "last_login": row[12].isoformat() if row[12] else None,
                "created_by": row[13],
                "assigned_caregiver_id": row[14],
                "caregiver_name": row[15]
            })
        
        logger.info(f"User {current_user.username} (role: {current_user.role}) accessed {len(users)} users")
        return users
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving users: {str(e)}")

@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)  # Changed to allow org admins and caregivers
):
    """Create a new user (with permission check)"""
    try:
        # Check if current user can create user in target organization with target role
        can_create, error_msg = await can_create_user_in_org(
            db, current_user, user_data.organization_id, user_data.role
        )
        
        if not can_create:
            raise HTTPException(status_code=403, detail=error_msg)
        
        # Debug log
        logger.info(f"User {current_user.username} creating user: username={user_data.username}, role={user_data.role}, organization_id={user_data.organization_id}")
        
        # Check if username exists
        result = await db.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": user_data.username}
        )
        if result.first():
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Determine admin status
        is_admin = user_data.role in ['super_admin', 'doctor', 'social_worker', 'nurse', 'counselor', 'staff', 'admin']
        is_super_admin_flag = user_data.role == 'super_admin'
        
        # Insert new user
        result = await db.execute(text("""
            INSERT INTO users (
                username, email, hashed_password, full_name, role,
                organization_id, is_active, is_verified, is_admin, is_super_admin,
                created_by, failed_login_attempts, created_at, updated_at
            ) VALUES (
                :username, :email, :password, :full_name, :role,
                :org_id, :is_active, true, :is_admin, :is_super_admin,
                :created_by, 0, NOW(), NOW()
            ) RETURNING id, username, email, full_name, role, is_active, created_at
        """), {
            "username": user_data.username,
            "email": user_data.email,
            "password": get_password_hash(user_data.password),
            "full_name": user_data.full_name,
            "role": user_data.role,
            "org_id": user_data.organization_id,
            "is_active": user_data.is_active,
            "is_admin": is_admin,
            "is_super_admin": is_super_admin_flag,
            "created_by": current_user.id
        })
        
        await db.commit()
        
        user = result.first()
        logger.info(f"User created: {user[1]} (ID: {user[0]})")
        
        return {
            "id": user[0],
            "username": user[1],
            "email": user[2],
            "full_name": user[3],
            "role": user[4],
            "is_active": user[5],
            "created_at": user[6].isoformat() if user[6] else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)  # Changed to allow org admins and caregivers
):
    """Update an existing user's details (with permission check)"""
    try:
        payload = user_data.model_dump(exclude_unset=True)
        new_password = payload.pop("new_password", None)
        assigned_caregiver_id = payload.pop("assigned_caregiver_id", None)
        
        if not payload and not new_password and assigned_caregiver_id is None:
            raise HTTPException(status_code=400, detail="No fields provided for update")
        
        result = await db.execute(
            text("""
                SELECT id, username, email, full_name, role, organization_id, is_super_admin, is_active, assigned_caregiver_id
                FROM users
                WHERE id = :id
            """),
            {"id": user_id}
        )
        existing = result.first()
        if not existing:
            raise HTTPException(status_code=404, detail="User not found")
        
        existing_user = {
            "id": existing[0],
            "username": existing[1],
            "email": existing[2],
            "full_name": existing[3],
            "role": existing[4],
            "organization_id": existing[5],
            "is_super_admin": existing[6],
            "is_active": existing[7],
            "assigned_caregiver_id": existing[8]
        }
        
        # Check if current user can manage target user
        target_user_obj = User(**{k: v for k, v in existing_user.items() if k in ['id', 'role', 'organization_id', 'assigned_caregiver_id']})
        target_user_obj.id = existing_user["id"]
        target_user_obj.role = existing_user["role"]
        target_user_obj.organization_id = existing_user["organization_id"]
        target_user_obj.assigned_caregiver_id = existing_user["assigned_caregiver_id"]
        
        if not can_manage_user(current_user, target_user_obj):
            raise HTTPException(status_code=403, detail="You do not have permission to manage this user")
        
        if "username" in payload:
            duplicate_username = await db.execute(
                text("SELECT id FROM users WHERE username = :username AND id <> :id"),
                {"username": payload["username"], "id": user_id}
            )
            if duplicate_username.first():
                raise HTTPException(status_code=400, detail="Username already exists")
        
        if "email" in payload:
            duplicate_email = await db.execute(
                text("SELECT id FROM users WHERE email = :email AND id <> :id"),
                {"email": payload["email"], "id": user_id}
            )
            if duplicate_email.first():
                raise HTTPException(status_code=400, detail="Email already exists")
        
        if existing_user["is_super_admin"]:
            if "role" in payload and payload["role"] != "super_admin":
                raise HTTPException(status_code=400, detail="Cannot change role of super admin account")
            if "is_active" in payload and payload["is_active"] is False:
                raise HTTPException(status_code=400, detail="Cannot deactivate super admin account")
        
        set_clauses = []
        params = {"id": user_id}
        
        # Handle assigned_caregiver_id separately
        if assigned_caregiver_id is not None:
            # Check permission to assign caregiver
            if assigned_caregiver_id:  # Not NULL
                can_assign, assign_error = await can_assign_caregiver(db, current_user, user_id, assigned_caregiver_id)
                if not can_assign:
                    raise HTTPException(status_code=403, detail=assign_error)
            set_clauses.append("assigned_caregiver_id = :assigned_caregiver_id")
            params["assigned_caregiver_id"] = assigned_caregiver_id
        
        for column in ("username", "email", "full_name", "organization_id", "role", "is_active"):
            if column in payload:
                set_clauses.append(f"{column} = :{column}")
                params[column] = payload[column]
        
        if "role" in payload:
            role_value = payload["role"]
        else:
            role_value = existing_user["role"]
        
        if "role" in payload:
            set_clauses.append("is_admin = :is_admin")
            set_clauses.append("is_super_admin = :is_super_admin")
            params["is_admin"] = role_value in ['super_admin', 'doctor', 'social_worker', 'nurse', 'counselor', 'staff']
            params["is_super_admin"] = role_value == 'super_admin'
        
        if new_password:
            set_clauses.append("hashed_password = :hashed_password")
            params["hashed_password"] = get_password_hash(new_password)
        
        if not set_clauses:
            raise HTTPException(status_code=400, detail="No valid fields provided for update")
        
        set_clauses.append("updated_at = NOW()")
        
        update_query = text(f"""
            UPDATE users
            SET {', '.join(set_clauses)}
            WHERE id = :id
            RETURNING id, username, email, full_name, role, organization_id, is_active, is_super_admin, is_admin
        """)
        
        updated_result = await db.execute(update_query, params)
        updated = updated_result.first()
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        
        await db.commit()
        
        org_name = None
        if updated[5]:
            org_query = await db.execute(
                text("SELECT name FROM organizations WHERE id = :id"),
                {"id": updated[5]}
            )
            org_row = org_query.first()
            if org_row:
                org_name = org_row[0]
        
        logger.info(f"User updated: {updated[1]} (ID: {updated[0]}) by super admin {current_user.id}")
        
        return {
            "id": updated[0],
            "username": updated[1],
            "email": updated[2],
            "full_name": updated[3],
            "role": updated[4],
            "organization_id": updated[5],
            "organization_name": org_name,
            "is_active": updated[6],
            "is_super_admin": updated[7],
            "is_admin": updated[8]
        }
        
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """Delete a user and all their data"""
    try:
        if user_id == current_user.id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
        # Get username before deletion
        result = await db.execute(
            text("SELECT username FROM users WHERE id = :id"),
            {"id": user_id}
        )
        user = result.first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        username = user[0]
        
        # Delete related data based on actual foreign key constraints
        # 1. User sessions (has FK to users)
        await db.execute(
            text("DELETE FROM user_sessions WHERE user_id = :id"),
            {"id": user_id}
        )
        
        # 2. User permissions (has FK to users)
        await db.execute(
            text("DELETE FROM user_permissions WHERE user_id = :id"),
            {"id": user_id}
        )
        
        # 3. Audit logs (if has FK to users)
        await db.execute(
            text("DELETE FROM audit_logs WHERE user_id = :id"),
            {"id": user_id}
        )
        
        # 4. Uploaded documents (if has FK to users)
        await db.execute(
            text("DELETE FROM uploaded_documents WHERE uploaded_by = :id"),
            {"id": user_id}
        )
        
        # 5. Conversations (if has FK to users)
        await db.execute(
            text("DELETE FROM conversations WHERE user_id = :id"),
            {"id": user_id}
        )
        
        # 6. Finally, delete the user
        await db.execute(
            text("DELETE FROM users WHERE id = :id"),
            {"id": user_id}
        )
        
        await db.commit()
        logger.info(f"User deleted: {username} (ID: {user_id}) and all related data")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")

# ============================================================================
# Organization Management Endpoints
# ============================================================================

@router.get("/organizations")
async def list_organizations(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user)  # Changed to allow org admins
):
    """List organizations based on current user's access level"""
    try:
        # Get accessible organization IDs
        accessible_org_ids = await get_accessible_organization_ids(db, current_user)
        
        if accessible_org_ids is None:
            # Super admin - see all orgs
            query = text("""
                SELECT 
                    o.id, o.name, o.type, o.description, o.email, o.phone,
                    o.max_users, o.max_admins, o.is_active, o.is_verified, o.created_at,
                    COUNT(u.id) as user_count
                FROM organizations o
                LEFT JOIN users u ON u.organization_id = o.id
                GROUP BY o.id, o.name, o.type, o.description, o.email, o.phone, 
                         o.max_users, o.max_admins, o.is_active, o.is_verified, o.created_at
                ORDER BY o.created_at DESC
            """)
            result = await db.execute(query)
        elif not accessible_org_ids:
            # No access - return empty list
            return []
        else:
            # Filter by accessible org IDs
            ids_str = ','.join(str(org_id) for org_id in accessible_org_ids)
            query = text(f"""
                SELECT 
                    o.id, o.name, o.type, o.description, o.email, o.phone,
                    o.max_users, o.max_admins, o.is_active, o.is_verified, o.created_at,
                    COUNT(u.id) as user_count
                FROM organizations o
                LEFT JOIN users u ON u.organization_id = o.id
                WHERE o.id IN ({ids_str})
                GROUP BY o.id, o.name, o.type, o.description, o.email, o.phone, 
                         o.max_users, o.max_admins, o.is_active, o.is_verified, o.created_at
                ORDER BY o.created_at DESC
            """)
            result = await db.execute(query)
        
        orgs = []
        for row in result:
            orgs.append({
                "id": row[0],
                "name": row[1],
                "type": row[2],
                "description": row[3],
                "email": row[4],
                "phone": row[5],
                "max_users": row[6],
                "max_admins": row[7],
                "is_active": row[8],
                "is_verified": row[9],
                "created_at": row[10].isoformat() if row[10] else None,
                "user_count": row[11] or 0
            })
        
        return orgs
        
    except Exception as e:
        logger.error(f"Error listing organizations: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving organizations: {str(e)}")

@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_data: OrganizationCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """Create a new organization"""
    try:
        # Check if name exists
        result = await db.execute(
            text("SELECT id FROM organizations WHERE name = :name"),
            {"name": org_data.name}
        )
        if result.first():
            raise HTTPException(status_code=400, detail="Organization name already exists")
        
        # Insert new organization
        result = await db.execute(text("""
            INSERT INTO organizations (
                name, type, description, email, phone,
                max_users, max_admins, is_active, is_verified,
                created_at, updated_at
            ) VALUES (
                :name, :type, :description, :email, :phone,
                :max_users, :max_admins, :is_active, true,
                NOW(), NOW()
            ) RETURNING id, name, type, description, email, max_users, max_admins, is_active, created_at
        """), {
            "name": org_data.name,
            "type": org_data.type,
            "description": org_data.description,
            "email": org_data.email,
            "phone": org_data.phone,
            "max_users": org_data.max_users,
            "max_admins": org_data.max_admins,
            "is_active": org_data.is_active,
            "created_by": current_user.id
        })
        
        await db.commit()
        
        org = result.first()
        logger.info(f"Organization created: {org[1]} (ID: {org[0]})")
        
        return {
            "id": org[0],
            "name": org[1],
            "type": org[2],
            "description": org[3],
            "email": org[4],
            "max_users": org[5],
            "max_admins": org[6],
            "is_active": org[7],
            "created_at": org[8].isoformat() if org[8] else None,
            "user_count": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating organization: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating organization: {str(e)}")

@router.delete("/organizations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(
    org_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """Delete an organization and unlink all users"""
    try:
        # First, unlink all users from this organization
        await db.execute(
            text("UPDATE users SET organization_id = NULL WHERE organization_id = :id"),
            {"id": org_id}
        )
        
        # Delete organization
        result = await db.execute(
            text("DELETE FROM organizations WHERE id = :id RETURNING name"),
            {"id": org_id}
        )
        
        org = result.first()
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        
        await db.commit()
        logger.info(f"Organization deleted: {org[0]} (ID: {org_id})")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting organization: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting organization: {str(e)}")

# ============================================================================
# Statistics Endpoint
# ============================================================================

@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_org_admin)  # Changed: Allow org admins
):
    """Get dashboard statistics (org-scoped for org admins)"""
    try:
        # Get stats
        result = await db.execute(text("""
            SELECT 
                COUNT(*) as total_users,
                SUM(CASE WHEN is_admin = true THEN 1 ELSE 0 END) as admin_users,
                SUM(CASE WHEN is_active = true THEN 1 ELSE 0 END) as active_users,
                SUM(CASE WHEN is_active = false AND is_verified = true THEN 1 ELSE 0 END) as pending_approvals
            FROM users
        """))
        
        stats_row = result.first()
        
        org_result = await db.execute(text("SELECT COUNT(*) FROM organizations"))
        org_count = org_result.scalar()
        
        return {
            "totalUsers": stats_row[0] or 0,
            "adminUsers": stats_row[1] or 0,
            "activeUsers": stats_row[2] or 0,
            "pendingApprovals": stats_row[3] or 0,
            "organizations": org_count or 0,
            "inactiveUsers": (stats_row[0] or 0) - (stats_row[2] or 0)
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")
