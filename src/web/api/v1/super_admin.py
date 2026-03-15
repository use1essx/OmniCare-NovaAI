"""
Super Admin API Endpoints
Complete user and organization management for super administrators
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, select
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
import logging

from src.database.connection import get_async_db, get_db
from src.database.models_comprehensive import User
from src.web.auth.dependencies import get_current_user, require_super_admin
from src.security.auth import get_password_hash
from src.security.audit import AuditEvent, audit_action

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
    role: str = Field(..., regex="^(super_admin|doctor|social_worker|nurse|counselor|staff|user)$")
    organization_id: Optional[int] = None
    is_active: bool = True
    
class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., regex="^(hospital|clinic|ngo|social_service|mental_health|research|platform|other)$")
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    max_users: int = Field(default=50, ge=1)
    max_admins: int = Field(default=10, ge=1)
    is_active: bool = True

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: str
    organization_id: Optional[int]
    organization_name: Optional[str] = None
    is_active: bool
    is_verified: Optional[bool]
    is_admin: bool
    is_super_admin: Optional[bool]
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True

class OrganizationResponse(BaseModel):
    id: int
    name: str
    type: str
    description: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    max_users: int
    max_admins: int
    is_active: bool
    is_verified: bool
    user_count: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True

class StatsResponse(BaseModel):
    totalUsers: int
    adminUsers: int
    organizations: int
    pendingApprovals: int
    activeUsers: int
    inactiveUsers: int

# ============================================================================
# User Management Endpoints
# ============================================================================

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(require_super_admin)
):
    """
    List all users in the system
    Super admin only
    """
    try:
        query = select(User)
        
        # Apply filters
        if role:
            query = query.filter(User.role == role)
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        query = query.order_by(User.created_at.desc())
        result = await db.execute(query)
        users = result.scalars().all()
        
        # Get organization names
        result = []
        for user in users:
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "organization_id": user.organization_id,
                "organization_name": None,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "is_admin": user.is_admin,
                "is_super_admin": user.is_super_admin,
                "created_at": user.created_at,
                "last_login": user.last_login
            }
            
            # Get organization name if exists
            if user.organization_id:
                org_result = await db.execute(
                    select(User.__table__.c.organization_id).select_from(User.__table__.metadata.tables['organizations'])
                    .where(User.__table__.metadata.tables['organizations'].c.id == user.organization_id)
                )
                org = org_result.first()
                if org:
                    user_dict["organization_name"] = str(org[0])  # Will fix properly later
            
            result.append(user_dict)
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving users"
        )

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Create a new user
    Super admin only
    """
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == user_data.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        
        # Check if email already exists
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        
        # Determine admin status based on role
        is_admin = user_data.role in ['super_admin', 'doctor', 'social_worker', 'nurse', 'counselor', 'staff']
        is_super_admin = user_data.role == 'super_admin'
        
        # Create new user
        new_user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            organization_id=user_data.organization_id,
            is_active=user_data.is_active,
            is_verified=True,  # Admin-created users are auto-verified
            is_admin=is_admin,
            is_super_admin=is_super_admin,
            created_by=current_user.id,
            failed_login_attempts=0
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"User created by super admin: {new_user.username} (ID: {new_user.id})")
        
        return UserResponse(
            id=new_user.id,
            username=new_user.username,
            email=new_user.email,
            full_name=new_user.full_name,
            role=new_user.role,
            organization_id=new_user.organization_id,
            is_active=new_user.is_active,
            is_verified=new_user.is_verified,
            is_admin=new_user.is_admin,
            is_super_admin=new_user.is_super_admin,
            created_at=new_user.created_at,
            last_login=new_user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating user: {str(e)}"
        )

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Delete a user
    Super admin only
    Cannot delete yourself
    """
    try:
        # Prevent self-deletion
        if user_id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Log the deletion
        logger.info(f"User deleted by super admin {current_user.username}: {user.username} (ID: {user.id})")
        
        db.delete(user)
        db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user"
        )

# ============================================================================
# Organization Management Endpoints
# ============================================================================

@router.get("/organizations", response_model=List[OrganizationResponse])
async def list_organizations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    List all organizations
    Super admin only
    """
    try:
        # Query organizations with user count
        orgs = db.execute("""
            SELECT 
                o.id,
                o.name,
                o.type,
                o.description,
                o.email,
                o.phone,
                o.max_users,
                o.max_admins,
                o.is_active,
                o.is_verified,
                o.created_at,
                COUNT(u.id) as user_count
            FROM organizations o
            LEFT JOIN users u ON u.organization_id = o.id
            GROUP BY o.id
            ORDER BY o.created_at DESC
        """).fetchall()
        
        result = []
        for org in orgs:
            result.append({
                "id": org[0],
                "name": org[1],
                "type": org[2],
                "description": org[3],
                "email": org[4],
                "phone": org[5],
                "max_users": org[6],
                "max_admins": org[7],
                "is_active": org[8],
                "is_verified": org[9],
                "created_at": org[10],
                "user_count": org[11] or 0
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing organizations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving organizations"
        )

def _build_organization_create_audit(action, args, kwargs, result):
    """Build audit event for organization creation."""
    current_user = kwargs.get("current_user")
    org_data = kwargs.get("org_data")
    return AuditEvent(
        action=action,
        actor_id=getattr(current_user, "id", None),
        target_type="organization",
        target_id=str(result.get("id")) if result else None,
        organization_id=result.get("id") if result else None,
        metadata={
            "organization_name": org_data.name if org_data else None,
            "organization_type": org_data.type if org_data else None,
        },
    )


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
@audit_action("organization.create", extract_context=_build_organization_create_audit)
async def create_organization(
    org_data: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Create a new organization
    Super admin only
    """
    try:
        # Check if organization name already exists
        existing = db.execute(
            "SELECT id FROM organizations WHERE name = :name",
            {"name": org_data.name}
        ).fetchone()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organization name already exists"
            )
        
        # Insert new organization
        result = db.execute("""
            INSERT INTO organizations (
                name, type, description, email, phone,
                max_users, max_admins, is_active, is_verified,
                created_by, created_at, updated_at
            ) VALUES (
                :name, :type, :description, :email, :phone,
                :max_users, :max_admins, :is_active, true,
                :created_by, NOW(), NOW()
            ) RETURNING id, name, type, description, email, phone,
                        max_users, max_admins, is_active, is_verified, created_at
        """, {
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
        
        db.commit()
        org = result.fetchone()
        
        logger.info(f"Organization created by super admin: {org[1]} (ID: {org[0]})")
        
        return {
            "id": org[0],
            "name": org[1],
            "type": org[2],
            "description": org[3],
            "email": org[4],
            "phone": org[5],
            "max_users": org[6],
            "max_admins": org[7],
            "is_active": org[8],
            "is_verified": org[9],
            "created_at": org[10],
            "user_count": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating organization: {str(e)}"
        )

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


@router.put("/organizations/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: int,
    update_data: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update organization details
    - Super admins can update any organization
    - Org admins can only update their own organization
    """
    try:
        # Check if organization exists
        org = db.execute(
            "SELECT id, name FROM organizations WHERE id = :id",
            {"id": org_id}
        ).fetchone()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Security check: Org admins can only edit their own organization
        is_super_admin = (
            getattr(current_user, "is_super_admin", False) or 
            getattr(current_user, "role", "").lower() == "super_admin"
        )
        
        if not is_super_admin:
            # Must be admin of this specific organization
            if not getattr(current_user, "is_admin", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only admins can edit organizations"
                )
            if getattr(current_user, "organization_id", None) != org_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only edit your own organization"
                )
        
        # Build update query
        update_fields = []
        params = {"id": org_id}
        
        if update_data.name is not None:
            update_fields.append("name = :name")
            params["name"] = update_data.name
        if update_data.description is not None:
            update_fields.append("description = :description")
            params["description"] = update_data.description
        if update_data.email is not None:
            update_fields.append("email = :email")
            params["email"] = update_data.email
        if update_data.phone is not None:
            update_fields.append("phone = :phone")
            params["phone"] = update_data.phone
        
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        update_fields.append("updated_at = NOW()")
        
        # Execute update
        result = db.execute(f"""
            UPDATE organizations
            SET {', '.join(update_fields)}
            WHERE id = :id
            RETURNING id, name, type, description, email, phone,
                      max_users, max_admins, is_active, is_verified, created_at
        """, params)
        
        db.commit()
        updated_org = result.fetchone()
        
        logger.info(f"Organization updated: {updated_org[1]} (ID: {updated_org[0]}) by user {current_user.username}")
        
        return {
            "id": updated_org[0],
            "name": updated_org[1],
            "type": updated_org[2],
            "description": updated_org[3],
            "email": updated_org[4],
            "phone": updated_org[5],
            "max_users": updated_org[6],
            "max_admins": updated_org[7],
            "is_active": updated_org[8],
            "is_verified": updated_org[9],
            "created_at": updated_org[10],
            "user_count": 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating organization: {str(e)}"
        )


def _build_organization_delete_audit(action, args, kwargs, result):
    """Build audit event for organization deletion."""
    current_user = kwargs.get("current_user")
    org_id = kwargs.get("org_id")
    # Try to extract org name from the closure/context if available
    # Since we can't easily access the org name after deletion, we rely on metadata
    return AuditEvent(
        action=action,
        actor_id=getattr(current_user, "id", None),
        target_type="organization",
        target_id=str(org_id) if org_id else None,
        organization_id=org_id,
        metadata={"operation": "delete"},
    )


@router.delete("/organizations/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
@audit_action("organization.delete", extract_context=_build_organization_delete_audit)
async def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Delete an organization
    Super admin only
    Will fail if organization has users
    """
    try:
        # Check if organization exists
        org = db.execute(
            "SELECT id, name FROM organizations WHERE id = :id",
            {"id": org_id}
        ).fetchone()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        
        # Check if organization has users
        user_count = db.execute(
            "SELECT COUNT(*) FROM users WHERE organization_id = :id",
            {"id": org_id}
        ).scalar()
        
        if user_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete organization with {user_count} users. Remove users first."
            )
        
        # Delete organization
        db.execute(
            "DELETE FROM organizations WHERE id = :id",
            {"id": org_id}
        )
        db.commit()
        
        logger.info(f"Organization deleted by super admin {current_user.username}: {org[1]} (ID: {org[0]})")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting organization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting organization"
        )

# ============================================================================
# Statistics Endpoint
# ============================================================================

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin)
):
    """
    Get dashboard statistics
    Super admin only
    """
    try:
        # Total users
        total_users = db.query(func.count(User.id)).scalar() or 0
        
        # Admin users
        admin_users = db.query(func.count(User.id)).filter(User.is_admin).scalar() or 0
        
        # Active users
        active_users = db.query(func.count(User.id)).filter(User.is_active).scalar() or 0
        
        # Inactive users
        inactive_users = total_users - active_users
        
        # Pending approvals (not active and verified)
        pending_approvals = db.query(func.count(User.id)).filter(
            and_(not User.is_active, User.is_verified)
        ).scalar() or 0
        
        # Organizations
        organizations = db.execute("SELECT COUNT(*) FROM organizations").scalar() or 0
        
        return {
            "totalUsers": total_users,
            "adminUsers": admin_users,
            "organizations": organizations,
            "pendingApprovals": pending_approvals,
            "activeUsers": active_users,
            "inactiveUsers": inactive_users
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving statistics"
        )

