"""
Organization Management API Endpoints
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger, log_api_request
from src.database.connection import get_async_db
from src.database.models_comprehensive import User
from src.database.repositories.organization_repository import OrganizationRepository
from src.web.auth.dependencies import require_role

logger = get_logger(__name__)
router = APIRouter(prefix="/organizations", tags=["organizations"])

# ============================================================================
# MODELS
# ============================================================================

class OrganizationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    type: str = Field(..., max_length=50)
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    max_users: Optional[int] = 50
    max_admins: Optional[int] = 10
    is_active: bool = True

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    type: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    max_users: Optional[int] = None
    max_admins: Optional[int] = None
    is_active: Optional[bool] = None

class OrganizationResponse(OrganizationBase):
    id: int
    created_at: datetime
    updated_at: datetime
    user_count: int = 0
    
    class Config:
        from_attributes = True

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get(
    "/",
    response_model=List[OrganizationResponse],
    dependencies=[Depends(require_role("admin"))],
    summary="List organizations",
    description="Get a list of all organizations"
)
async def list_organizations(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
):
    """List organizations with user counts"""
    start_time = datetime.now()
    try:
        repo = OrganizationRepository()
        if search:
            # For search, get orgs and manually add user counts
            orgs = await repo.search(search, limit, skip, session=db)
            # Convert to dict and add user_count = 0 for now (search optimization can be added later)
            orgs_data = [
                {**org.__dict__, 'user_count': 0} for org in orgs
            ]
        else:
            # Get organizations with user counts
            orgs_data = await repo.get_all_with_user_counts(limit, skip, order_by="name", session=db)
            
        # Log request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id
        )
        return orgs_data
    except Exception as e:
        logger.error(f"Error listing organizations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list organizations")

@router.post(
    "/",
    response_model=OrganizationResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Create organization",
    status_code=status.HTTP_201_CREATED
)
async def create_organization(
    request: Request,
    org_data: OrganizationCreate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
):
    """Create a new organization"""
    start_time = datetime.now()
    try:
        repo = OrganizationRepository()
        
        # Check if name exists
        existing = await repo.get_by_name(org_data.name, session=db)
        if existing:
            raise HTTPException(status_code=400, detail="Organization with this name already exists")
            
        new_org = await repo.create(org_data.dict(), session=db)
        
        # Log request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=201,
            response_time_ms=processing_time,
            user_id=current_user.id
        )
        return new_org
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating organization: {e}")
        raise HTTPException(status_code=500, detail="Failed to create organization")

@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    dependencies=[Depends(require_role("admin"))]
)
async def get_organization(
    request: Request,
    org_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
):
    """Get organization by ID"""
    try:
        repo = OrganizationRepository()
        org = await repo.get_by_id(org_id, session=db)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return org
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting organization {org_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get organization")

@router.put(
    "/{org_id}",
    response_model=OrganizationResponse,
    dependencies=[Depends(require_role("admin"))]
)
async def update_organization(
    request: Request,
    org_id: int,
    org_data: OrganizationUpdate,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
):
    """Update organization"""
    try:
        repo = OrganizationRepository()
        existing = await repo.get_by_id(org_id, session=db)
        if not existing:
            raise HTTPException(status_code=404, detail="Organization not found")
            
        updated = await repo.update(org_id, org_data.dict(exclude_unset=True), session=db)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating organization {org_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update organization")

@router.delete(
    "/{org_id}",
    dependencies=[Depends(require_role("admin"))],
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_organization(
    request: Request,
    org_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
):
    """Delete organization"""
    try:
        repo = OrganizationRepository()
        existing = await repo.get_by_id(org_id, session=db)
        if not existing:
            raise HTTPException(status_code=404, detail="Organization not found")
            
        await repo.delete(org_id, session=db)
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting organization {org_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete organization")
