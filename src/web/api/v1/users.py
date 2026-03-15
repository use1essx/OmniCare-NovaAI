"""
User Management API Endpoints

This module provides comprehensive user management functionality including:
- User profile management
- User listing and search (admin only)
- User activation/deactivation (admin only)
- User preferences and settings
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from src.core.logging import get_logger, log_api_request
from src.security.auth import InputSanitizer
from src.database.connection import get_async_db
from src.database.models_comprehensive import User
from src.database.repositories.user_repository import UserRepository
from src.web.auth.dependencies import get_current_user, require_role, auth_rate_limit

logger = get_logger(__name__)
router = APIRouter(prefix="/users", tags=["users"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class UserProfileResponse(BaseModel):
    """User profile response model"""
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    role: str
    department: Optional[str] = None
    license_number: Optional[str] = None
    is_active: bool
    is_verified: bool
    language_preference: Optional[str] = "en"
    timezone: Optional[str] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    created_at: datetime
    last_login: Optional[datetime] = None
    health_profile: Optional[Dict[str, Any]] = None  # Include health profile data
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """User list item response model"""
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    role: str
    department: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class UpdateUserProfileRequest(BaseModel):
    """Update user profile request model"""
    full_name: Optional[str] = Field(None, max_length=255, description="User's full name")
    department: Optional[str] = Field(None, max_length=100, description="User's department")
    license_number: Optional[str] = Field(None, max_length=100, description="Professional license number")
    language_preference: Optional[str] = Field(None, pattern="^(en|zh-HK)$", description="Preferred language")  # Only English and Cantonese (Hong Kong)
    timezone: Optional[str] = Field(None, max_length=50, description="User's timezone")
    notification_preferences: Optional[Dict[str, Any]] = Field(None, description="Notification preferences")
    health_profile: Optional[Dict[str, Any]] = Field(None, description="User health profile data")


class UpdateUserRequest(BaseModel):
    """Update user request model (admin only)"""
    full_name: Optional[str] = Field(None, max_length=255)
    department: Optional[str] = Field(None, max_length=100)
    license_number: Optional[str] = Field(None, max_length=100)
    role: Optional[str] = Field(None, pattern="^(user|admin|medical_reviewer|data_manager|super_admin)$")
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    language_preference: Optional[str] = Field(None, pattern="^(en|zh-HK)$")  # Only English and Cantonese (Hong Kong)
    timezone: Optional[str] = Field(None, max_length=50)


class UserSearchResponse(BaseModel):
    """User search response model"""
    users: List[UserListResponse]
    total: int
    page: int
    page_size: int
    pages: int


class UserStatsResponse(BaseModel):
    """User statistics response model"""
    total_users: int
    active_users: int
    inactive_users: int
    verified_users: int
    unverified_users: int
    users_by_role: Dict[str, int]
    recent_registrations: int
    recent_logins: int


# ============================================================================
# USER PROFILE ENDPOINTS
# ============================================================================

@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
    description="Get the profile information for the currently authenticated user",
    responses={
        200: {"description": "User profile retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "User not found"}
    }
)
async def get_current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    _: None = Depends(auth_rate_limit)
) -> UserProfileResponse:
    """Get current user's profile information"""
    start_time = datetime.now()
    
    try:
        from src.database.health_profile_models import HealthProfile
        from sqlalchemy import select
        
        user_repo = UserRepository()
        user_with_permissions = await user_repo.get_with_permissions(current_user.id, db)
        
        if not user_with_permissions:
            raise NotFoundError("User profile not found")
        
        # Fetch health profile
        health_profile_data = None
        try:
            result = await db.execute(
                select(HealthProfile).where(HealthProfile.user_id == current_user.id)
            )
            health_profile = result.scalar_one_or_none()
            if health_profile:
                health_profile_data = {
                    "id": health_profile.id,
                    "nickname": health_profile.nickname,
                    "age": health_profile.age,
                    "age_group": health_profile.age_group.value if health_profile.age_group else None,
                    "gender": health_profile.gender.value if health_profile.gender else None,
                    "date_of_birth": str(health_profile.date_of_birth) if health_profile.date_of_birth else None,
                    "school_name": health_profile.school_name,
                    "school_level": health_profile.school_level.value if health_profile.school_level else None,
                    "current_mood": health_profile.current_mood,
                    "stress_level": health_profile.stress_level,
                    "stress_sources": health_profile.stress_sources,
                    "hobbies": health_profile.hobbies,
                    "favorite_subjects": health_profile.favorite_subjects,
                    "challenging_subjects": health_profile.challenging_subjects,
                    "coping_strategies": health_profile.coping_strategies,
                    "favorite_activities": health_profile.favorite_activities,
                    "personal_goals": health_profile.personal_goals,
                    "academic_goals": health_profile.academic_goals,
                    "dream_career": health_profile.dream_career,
                    "academic_pressure_level": health_profile.academic_pressure_level,
                    "social_comfort_level": health_profile.social_comfort_level,
                    "sleep_hours_weekday": health_profile.sleep_hours_weekday,
                    "allergies": health_profile.allergies,
                }
        except Exception as e:
            logger.warning(f"Could not load health profile for user {current_user.id}: {e}")
        
        # Log successful API request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return UserProfileResponse(
            id=user_with_permissions.id,
            email=user_with_permissions.email,
            username=user_with_permissions.username,
            full_name=user_with_permissions.full_name,
            role=user_with_permissions.role,
            department=user_with_permissions.department,
            license_number=user_with_permissions.license_number,
            is_active=user_with_permissions.is_active,
            is_verified=user_with_permissions.is_verified,
            language_preference=user_with_permissions.language_preference,
            timezone=user_with_permissions.timezone,
            notification_preferences=user_with_permissions.notification_preferences or {},
            created_at=user_with_permissions.created_at,
            last_login=user_with_permissions.last_login,
            health_profile=health_profile_data
        )
        
    except Exception as e:
        logger.error(f"Error retrieving user profile for user {current_user.id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, (NotFoundError, AuthorizationError, ValidationError)):
            raise e
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user profile"
        )


@router.put(
    "/me",
    response_model=UserProfileResponse,
    summary="Update current user profile",
    description="Update the profile information for the currently authenticated user",
    responses={
        200: {"description": "User profile updated successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Authentication required"},
        404: {"description": "User not found"}
    }
)
  # 10 updates per minute
async def update_current_user_profile(
    request: Request,
    user_data: UpdateUserProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> UserProfileResponse:
    """Update current user's profile information"""
    start_time = datetime.now()
    
    try:
        # Sanitize input data
        sanitizer = InputSanitizer()
        update_data = {}
        
        for field, value in user_data.dict(exclude_unset=True).items():
            if value is not None:
                if isinstance(value, str):
                    sanitized_value = sanitizer.sanitize_string(value)
                    if sanitized_value != value:
                        logger.warning(f"Input sanitized for field {field}")
                    update_data[field] = sanitized_value
                else:
                    update_data[field] = value
        
        user_repo = UserRepository()
        
        # Update user profile
        if update_data:
            updated_user = await user_repo.update(current_user.id, update_data, db)
            if not updated_user:
                raise NotFoundError("User not found")
        else:
            updated_user = current_user
        
        # Get updated user with permissions
        user_with_permissions = await user_repo.get_with_permissions(updated_user.id, db)
        
        # Log successful update
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"User {current_user.id} updated their profile")
        
        return UserProfileResponse.from_orm(user_with_permissions)
        
    except Exception as e:
        logger.error(f"Error updating user profile for user {current_user.id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, (NotFoundError, AuthorizationError, ValidationError)):
            raise e
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user profile"
        )


# ============================================================================
# HEALTH PROFILE ENDPOINTS (Teen/Kids Mental Health)
# ============================================================================

class HealthProfileUpdateRequest(BaseModel):
    """Request model for updating health profile from chat extraction"""
    nickname: Optional[str] = Field(None, max_length=100)
    age: Optional[int] = Field(None, ge=5, le=25)
    age_group: Optional[str] = Field(None, description="child, teen, or adult")
    gender: Optional[str] = Field(None)
    school_level: Optional[str] = Field(None)
    current_mood: Optional[str] = Field(None)
    stress_level: Optional[int] = Field(None, ge=1, le=5)
    stress_sources: Optional[List[str]] = Field(None)
    hobbies: Optional[List[str]] = Field(None)
    favorite_subjects: Optional[List[str]] = Field(None)
    challenging_subjects: Optional[List[str]] = Field(None)
    coping_strategies: Optional[List[str]] = Field(None)
    dream_career: Optional[str] = Field(None, max_length=255)
    friend_circle_size: Optional[str] = Field(None)
    relationship_with_parents: Optional[str] = Field(None)
    sleep_hours_weekday: Optional[float] = Field(None, ge=0, le=24)
    physical_activity_level: Optional[str] = Field(None)


class HealthProfileResponse(BaseModel):
    """Response model for health profile"""
    id: int
    user_id: int
    nickname: Optional[str]
    age: Optional[int]
    age_group: Optional[str]
    current_mood: Optional[str]
    stress_level: Optional[int]
    hobbies: Optional[List[str]]
    completion_percentage: float
    
    class Config:
        from_attributes = True


@router.get(
    "/me/health-profile",
    response_model=HealthProfileResponse,
    summary="Get current user's health profile",
    description="Get the health profile for teens/kids mental health tracking",
    responses={
        200: {"description": "Health profile retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Health profile not found"}
    }
)
async def get_my_health_profile(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> HealthProfileResponse:
    """Get current user's health profile"""
    from src.database.health_profile_models import HealthProfile
    from src.services.profile_extraction_service import get_profile_extraction_service
    from sqlalchemy import select
    
    try:
        # Query health profile
        result = await db.execute(
            select(HealthProfile).where(HealthProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()
        
        if not profile:
            # Return empty profile with 0% completion
            return HealthProfileResponse(
                id=0,
                user_id=current_user.id,
                nickname=None,
                age=None,
                age_group=None,
                current_mood=None,
                stress_level=None,
                hobbies=None,
                completion_percentage=0.0
            )
        
        # Calculate completion percentage
        profile_service = get_profile_extraction_service()
        completeness = profile_service.assess_profile_completeness(profile)
        
        return HealthProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            nickname=profile.nickname,
            age=profile.age,
            age_group=profile.age_group.value if profile.age_group else None,
            current_mood=profile.current_mood,
            stress_level=profile.stress_level,
            hobbies=profile.hobbies,
            completion_percentage=completeness.completion_percentage
        )
        
    except Exception as e:
        logger.error(f"Error retrieving health profile for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving health profile"
        )


@router.put(
    "/me/health-profile",
    response_model=HealthProfileResponse,
    summary="Update current user's health profile",
    description="Update health profile data (can be called from chat extraction or manual input)",
    responses={
        200: {"description": "Health profile updated successfully"},
        401: {"description": "Authentication required"}
    }
)
async def update_my_health_profile(
    request: Request,
    profile_data: HealthProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
) -> HealthProfileResponse:
    """Update current user's health profile"""
    from src.database.health_profile_models import HealthProfile, AgeGroupEnum, SchoolLevelEnum
    from src.services.profile_extraction_service import get_profile_extraction_service
    from sqlalchemy import select
    
    try:
        # Query existing health profile
        result = await db.execute(
            select(HealthProfile).where(HealthProfile.user_id == current_user.id)
        )
        profile = result.scalar_one_or_none()
        
        # Create profile if doesn't exist
        if not profile:
            profile = HealthProfile(user_id=current_user.id)
            db.add(profile)
        
        # Update fields from request
        update_dict = profile_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            if value is not None:
                # Handle enum conversions
                if field == "age_group" and value:
                    try:
                        value = AgeGroupEnum(value)
                    except ValueError:
                        pass
                elif field == "school_level" and value:
                    try:
                        value = SchoolLevelEnum(value)
                    except ValueError:
                        pass
                setattr(profile, field, value)
        
        await db.commit()
        await db.refresh(profile)
        
        # Calculate completion percentage
        profile_service = get_profile_extraction_service()
        completeness = profile_service.assess_profile_completeness(profile)
        
        logger.info(f"Updated health profile for user {current_user.id}")
        
        return HealthProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            nickname=profile.nickname,
            age=profile.age,
            age_group=profile.age_group.value if profile.age_group else None,
            current_mood=profile.current_mood,
            stress_level=profile.stress_level,
            hobbies=profile.hobbies,
            completion_percentage=completeness.completion_percentage
        )
        
    except Exception as e:
        logger.error(f"Error updating health profile for user {current_user.id}: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating health profile"
        )


# ============================================================================
# ADMIN USER MANAGEMENT ENDPOINTS
# ============================================================================

@router.get(
    "",
    response_model=UserSearchResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="List users (Admin)",
    description="Get a paginated list of users with optional search and filtering",
    responses={
        200: {"description": "Users retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)
  # 20 calls per minute for admin
async def list_users(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term for username, email, or full name"),
    role: Optional[str] = Query(None, description="Filter by user role"),
    active_only: bool = Query(default=False, description="Show only active users"),
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> UserSearchResponse:
    """Get paginated list of users with search and filtering"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        
        # Build filters
        filters = {}
        if role:
            filters["role"] = role
        if active_only:
            filters["is_active"] = True
        
        # Get paginated results
        if search:
            # Sanitize search term
            sanitizer = InputSanitizer()
            safe_search = sanitizer.sanitize_string(search, max_length=100)
            users = await user_repo.search_users(
                search_term=safe_search,
                limit=page_size,
                offset=(page - 1) * page_size
            )
            total = len(users)  # For simplicity, using length of results
        else:
            result = await user_repo.get_paginated(
                page=page,
                page_size=page_size,
                filters=filters,
                order_by="created_at",
                order_desc=True,
                session=db
            )
            users = result["items"]
            total = result["pagination"]["total_count"]
        
        # Calculate pagination info
        pages = (total + page_size - 1) // page_size
        
        # Convert to response models
        user_list = [UserListResponse.from_orm(user) for user in users]
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return UserSearchResponse(
            users=user_list,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving users"
        )


@router.get(
    "/{user_id}",
    response_model=UserProfileResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Get user by ID (Admin)",
    description="Get detailed information about a specific user",
    responses={
        200: {"description": "User retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)

async def get_user_by_id(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> UserProfileResponse:
    """Get user by ID (admin only)"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        user = await user_repo.get_with_permissions(user_id, db)
        
        if not user:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return UserProfileResponse.from_orm(user)
        
    except Exception as e:
        logger.error(f"Error retrieving user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=404 if isinstance(e, NotFoundError) else 500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, NotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user"
        )


@router.put(
    "/{user_id}",
    response_model=UserProfileResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Update user (Admin)",
    description="Update user information (admin only)",
    responses={
        200: {"description": "User updated successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)

async def update_user(
    request: Request,
    user_id: int,
    user_data: UpdateUserRequest,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> UserProfileResponse:
    """Update user information (admin only)"""
    start_time = datetime.now()
    
    try:
        # Prevent admin from modifying super admin users unless they are super admin
        user_repo = UserRepository()
        target_user = await user_repo.get_by_id(user_id, db)
        
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        # Super admin protection
        if target_user.is_super_admin and not current_user.is_super_admin:
            raise AuthorizationError("Cannot modify super admin users")
        
        # Sanitize input data
        sanitizer = InputSanitizer()
        update_data = {}
        
        for field, value in user_data.dict(exclude_unset=True).items():
            if value is not None:
                if isinstance(value, str):
                    sanitized_value = sanitizer.sanitize_string(value)
                    if sanitized_value != value:
                        logger.warning(f"Input sanitized for field {field}")
                    update_data[field] = sanitized_value
                else:
                    update_data[field] = value
        
        # Update user
        if update_data:
            updated_user = await user_repo.update(user_id, update_data, db)
            if not updated_user:
                raise NotFoundError(f"User with ID {user_id} not found")
        else:
            updated_user = target_user
        
        # Get updated user with permissions
        user_with_permissions = await user_repo.get_with_permissions(updated_user.id, db)
        
        # Log successful update
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} updated user {user_id}")
        
        return UserProfileResponse.from_orm(user_with_permissions)
        
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, (NotFoundError, AuthorizationError, ValidationError)):
            status_code = status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else status.HTTP_403_FORBIDDEN
            raise HTTPException(status_code=status_code, detail=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating user"
        )


@router.post(
    "/{user_id}/activate",
    dependencies=[Depends(require_role("admin"))],
    summary="Activate user (Admin)",
    description="Activate a user account",
    responses={
        200: {"description": "User activated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)

async def activate_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, str]:
    """Activate a user account"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        success = await user_repo.activate_user(user_id)
        
        if not success:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        # Log successful activation
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} activated user {user_id}")
        
        return {"message": f"User {user_id} activated successfully"}
        
    except Exception as e:
        logger.error(f"Error activating user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=404 if isinstance(e, NotFoundError) else 500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, NotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error activating user"
        )


@router.post(
    "/{user_id}/deactivate",
    dependencies=[Depends(require_role("admin"))],
    summary="Deactivate user (Admin)",
    description="Deactivate a user account",
    responses={
        200: {"description": "User deactivated successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)

async def deactivate_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, str]:
    """Deactivate a user account"""
    start_time = datetime.now()
    
    try:
        # Prevent deactivating self or super admins
        if user_id == current_user.id:
            raise AuthorizationError("Cannot deactivate your own account")
        
        user_repo = UserRepository()
        target_user = await user_repo.get_by_id(user_id, db)
        
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        if target_user.is_super_admin:
            raise AuthorizationError("Cannot deactivate super admin users")
        
        success = await user_repo.deactivate_user(user_id)
        
        if not success:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        # Log successful deactivation
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} deactivated user {user_id}")
        
        return {"message": f"User {user_id} deactivated successfully"}
        
    except Exception as e:
        logger.error(f"Error deactivating user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, (NotFoundError, AuthorizationError)):
            status_code = status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else status.HTTP_403_FORBIDDEN
            raise HTTPException(status_code=status_code, detail=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deactivating user"
        )


@router.get(
    "/stats",
    response_model=UserStatsResponse,
    dependencies=[Depends(require_role("admin"))],
    summary="Get user statistics (Admin)",
    description="Get comprehensive user statistics for admin dashboard",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"}
    }
)

async def get_user_statistics(
    request: Request,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> UserStatsResponse:
    """Get user statistics for admin dashboard"""
    start_time = datetime.now()
    
    try:
        user_repo = UserRepository()
        stats = await user_repo.get_user_statistics()
        
        # Log successful request
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        return UserStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Error retrieving user statistics: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving user statistics"
        )


@router.delete(
    "/{user_id}",
    dependencies=[Depends(require_role("admin"))],
    summary="Delete user (Admin)",
    description="Delete a user account",
    responses={
        200: {"description": "User deleted successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin access required"},
        404: {"description": "User not found"}
    }
)
async def delete_user(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_async_db)
) -> Dict[str, str]:
    """Delete a user account"""
    start_time = datetime.now()
    
    try:
        # Prevent deleting self
        if user_id == current_user.id:
            raise AuthorizationError("Cannot delete your own account")
        
        user_repo = UserRepository()
        target_user = await user_repo.get_by_id(user_id, db)
        
        if not target_user:
            raise NotFoundError(f"User with ID {user_id} not found")
        
        if target_user.is_super_admin:
            raise AuthorizationError("Cannot delete super admin users")
        
        # Perform deletion
        success = await user_repo.delete(user_id, db)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )
        
        # Log successful deletion
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=200,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None
        )
        
        logger.info(f"Admin {current_user.id} deleted user {user_id}")
        
        return {"message": f"User {user_id} deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting user {user_id}: {e}")
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        log_api_request(
            method=request.method,
            endpoint=str(request.url.path),
            status_code=500,
            response_time_ms=processing_time,
            user_id=current_user.id,
            ip_address=request.client.host if request.client else None,
            error=str(e)
        )
        
        if isinstance(e, (NotFoundError, AuthorizationError)):
            status_code = status.HTTP_404_NOT_FOUND if isinstance(e, NotFoundError) else status.HTTP_403_FORBIDDEN
            raise HTTPException(status_code=status_code, detail=str(e))
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting user"
        )
