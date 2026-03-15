"""
Healthcare AI V2 - Movement Analysis API Routes
FastAPI routes for movement analysis rules and assessments
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_async_db
from src.database.models_comprehensive import User
from src.web.auth.dependencies import get_current_user, get_optional_user

from .schemas import (
    AssessmentRuleCreate,
    AssessmentRuleUpdate,
    AssessmentRuleResponse,
    AssessmentRuleListResponse,
)
from .rules_service import AssessmentRulesService

logger = logging.getLogger(__name__)

# Public API Router (for assessments)
router = APIRouter(prefix="/movement-analysis", tags=["movement-analysis"])

# Admin API Router (for rule management)
admin_router = APIRouter(prefix="/movement-analysis", tags=["movement-analysis-admin"])


# =============================================================================
# Admin Routes - Assessment Rules Management
# =============================================================================

@admin_router.get("/rules", response_model=AssessmentRuleListResponse)
async def list_assessment_rules(
    page: int = 1,
    limit: int = 20,
    active_only: bool = False,
    category: Optional[str] = None,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List assessment rules with pagination
    
    - **page**: Page number (1-indexed)
    - **limit**: Items per page (max 100)
    - **active_only**: Filter to only active rules
    - **category**: Filter by category name (partial match)
    """
    # Validate pagination
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
    
    service = AssessmentRulesService(db)
    
    try:
        result = await service.list_rules(
            current_user=current_user,
            page=page,
            limit=limit,
            active_only=active_only,
            category_filter=category
        )
        
        return AssessmentRuleListResponse(
            rules=[AssessmentRuleResponse(**rule) for rule in result["rules"]],
            total=result["total"],
            page=result["page"],
            limit=result["limit"],
            pages=result["pages"]
        )
    except Exception as e:
        logger.error(f"Error listing assessment rules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load rules"
        )


@admin_router.post("/rules", response_model=AssessmentRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment_rule(
    rule_data: AssessmentRuleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Create a new assessment rule (JSON)
    
    Requires: manage_assessment_rules permission
    """
    service = AssessmentRulesService(db)
    
    try:
        rule = await service.create_rule(rule_data, current_user)
        return AssessmentRuleResponse.model_validate(rule)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating assessment rule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rule"
        )


@admin_router.post("/rules/upload", response_model=AssessmentRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_assessment_rule_with_files(
    category: str = Form(...),
    index_code: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    ai_role: Optional[str] = Form(None),
    reference_video_url: Optional[str] = Form(None),
    reference_description: Optional[str] = Form(None),
    analysis_instruction: Optional[str] = Form(None),
    text_standards: Optional[str] = Form(None),
    is_active: bool = Form(True),
    documents: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Create a new assessment rule with document uploads (FormData)
    
    Requires: manage_assessment_rules permission
    """
    import json
    
    service = AssessmentRulesService(db)
    
    try:
        # Parse text_standards if provided
        text_standards_dict = None
        if text_standards:
            try:
                text_standards_dict = json.loads(text_standards)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in text_standards")
        
        # Handle uploaded documents
        uploaded_docs = []
        if documents:
            for doc in documents:
                # Read file content
                content = await doc.read()
                uploaded_docs.append({
                    "filename": doc.filename,
                    "content_type": doc.content_type,
                    "size": len(content),
                    "content": content.decode('utf-8', errors='ignore') if doc.content_type and doc.content_type.startswith('text') else None
                })
        
        # Add uploaded documents to text_standards
        if uploaded_docs:
            if not text_standards_dict:
                text_standards_dict = {}
            text_standards_dict["uploaded_documents"] = uploaded_docs
        
        # Create rule data object
        rule_data = AssessmentRuleCreate(
            category=category,
            index_code=index_code,
            description=description,
            ai_role=ai_role,
            reference_video_url=reference_video_url,
            reference_description=reference_description,
            analysis_instruction=analysis_instruction,
            text_standards=text_standards_dict,
            is_active=is_active
        )
        
        rule = await service.create_rule(rule_data, current_user)
        return AssessmentRuleResponse.model_validate(rule)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating assessment rule with files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rule"
        )
    except Exception as e:
        logger.error(f"Error creating assessment rule: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create rule"
        )


@admin_router.get("/rules/{rule_id}", response_model=AssessmentRuleResponse)
async def get_assessment_rule(
    rule_id: int,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get a single assessment rule by ID
    """
    service = AssessmentRulesService(db)
    
    try:
        rule = await service.get_rule(rule_id, current_user)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        
        return AssessmentRuleResponse.model_validate(rule)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assessment rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load rule"
        )


@admin_router.put("/rules/{rule_id}", response_model=AssessmentRuleResponse)
async def update_assessment_rule_json(
    rule_id: int,
    rule_data: AssessmentRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update an existing assessment rule (JSON format, no file uploads)
    
    Requires: manage_assessment_rules permission
    """
    service = AssessmentRulesService(db)
    
    try:
        logger.info(f"=== UPDATE RULE JSON: rule_id={rule_id} ===")
        logger.info(f"Update data: {rule_data.model_dump(exclude_unset=True)}")
        
        rule = await service.update_rule(rule_id, rule_data, current_user)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        
        logger.info(f"Rule updated successfully via JSON endpoint")
        
        return AssessmentRuleResponse.model_validate(rule)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assessment rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update rule"
        )


@admin_router.put("/rules/upload/{rule_id}", response_model=AssessmentRuleResponse)
async def update_assessment_rule_with_files(
    rule_id: int,
    category: Optional[str] = Form(None),
    index_code: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    ai_role: Optional[str] = Form(None),
    reference_video_url: Optional[str] = Form(None),
    reference_description: Optional[str] = Form(None),
    analysis_instruction: Optional[str] = Form(None),
    text_standards: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    documents: Optional[list[UploadFile]] = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Update an existing assessment rule with document uploads (FormData format)
    
    Requires: manage_assessment_rules permission
    """
    import json
    
    service = AssessmentRulesService(db)
    
    try:
        logger.info(f"=== UPDATE RULE WITH FILES: rule_id={rule_id} ===")
        logger.info(f"Received text_standards: {text_standards}")
        logger.info(f"Received documents: {documents}")
        
        # Get existing rule to preserve existing files
        existing_rule = await service.get_rule(rule_id, current_user)
        if not existing_rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        
        logger.info(f"Existing rule text_standards: {existing_rule.text_standards}")
        
        # Parse text_standards if provided
        text_standards_dict = None
        if text_standards:
            try:
                text_standards_dict = json.loads(text_standards)
                logger.info(f"Parsed text_standards_dict: {text_standards_dict}")
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in text_standards")
        
        # Get existing uploaded documents from text_standards
        existing_uploaded_docs = []
        if text_standards_dict and "uploaded_documents" in text_standards_dict:
            # Frontend sends existing files in text_standards.uploaded_documents
            existing_uploaded_docs = text_standards_dict.get("uploaded_documents", [])
            logger.info(f"Found existing docs in text_standards: {len(existing_uploaded_docs)}")
        elif existing_rule.text_standards and "uploaded_documents" in existing_rule.text_standards:
            # Fallback: get from existing rule if not in new text_standards
            existing_uploaded_docs = existing_rule.text_standards.get("uploaded_documents", [])
            logger.info(f"Found existing docs in existing rule: {len(existing_uploaded_docs)}")
        
        # Handle new uploaded documents
        new_uploaded_docs = []
        if documents:
            logger.info(f"Processing {len(documents)} new documents")
            for doc in documents:
                if isinstance(doc, UploadFile):
                    content = await doc.read()
                    new_uploaded_docs.append({
                        "filename": doc.filename,
                        "content_type": doc.content_type,
                        "size": len(content),
                        "content": content.decode('utf-8', errors='ignore') if doc.content_type and doc.content_type.startswith('text') else None
                    })
                    logger.info(f"Added new document: {doc.filename}, size: {len(content)}")
        
        # Merge existing and new documents
        if new_uploaded_docs or existing_uploaded_docs:
            if not text_standards_dict:
                text_standards_dict = {}
            # Combine existing files with new uploads
            all_docs = existing_uploaded_docs + new_uploaded_docs
            text_standards_dict["uploaded_documents"] = all_docs
            logger.info(f"Total documents after merge: {len(all_docs)}")
        
        logger.info(f"Final text_standards_dict: {text_standards_dict}")
        
        # Build update data
        update_dict = {}
        if category is not None:
            update_dict["category"] = category
        if index_code is not None:
            update_dict["index_code"] = index_code
        if description is not None:
            update_dict["description"] = description
        if ai_role is not None:
            update_dict["ai_role"] = ai_role
        if reference_video_url is not None:
            update_dict["reference_video_url"] = reference_video_url
        if reference_description is not None:
            update_dict["reference_description"] = reference_description
        if analysis_instruction is not None:
            update_dict["analysis_instruction"] = analysis_instruction
        if text_standards_dict is not None:
            update_dict["text_standards"] = text_standards_dict
        if is_active is not None:
            update_dict["is_active"] = is_active
        
        logger.info(f"Update dict keys: {update_dict.keys()}")
        
        rule_data = AssessmentRuleUpdate(**update_dict)
        
        rule = await service.update_rule(rule_id, rule_data, current_user)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        
        logger.info(f"Rule updated successfully, text_standards: {rule.text_standards}")
        
        return AssessmentRuleResponse.model_validate(rule)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating assessment rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update rule"
        )


@admin_router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Delete an assessment rule
    
    Requires: manage_assessment_rules permission
    """
    service = AssessmentRulesService(db)
    
    try:
        deleted = await service.delete_rule(rule_id, current_user)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        
        return None
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting assessment rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete rule"
        )


@admin_router.patch("/rules/{rule_id}/toggle", response_model=AssessmentRuleResponse)
async def toggle_assessment_rule(
    rule_id: int,
    is_active: bool,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Toggle rule active status
    
    Requires: manage_assessment_rules permission
    """
    service = AssessmentRulesService(db)
    
    try:
        rule = await service.toggle_rule_active(rule_id, is_active, current_user)
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
        
        return AssessmentRuleResponse.model_validate(rule)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling assessment rule {rule_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle rule"
        )


@admin_router.post("/upload-standard-video")
async def upload_standard_video(
    movement_title: str = Form(...),
    video: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Upload a standard tutorial video and auto-generate an assessment rule
    
    Requires: manage_assessment_rules permission
    """
    import os
    import tempfile
    from pathlib import Path
    from .standard_video_service import get_standard_video_analyzer
    
    service = AssessmentRulesService(db)
    
    try:
        # Save uploaded video to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(video.filename).suffix) as tmp_file:
            content = await video.read()
            tmp_file.write(content)
            tmp_video_path = tmp_file.name
        
        try:
            # Analyze video and generate rule data
            analyzer = get_standard_video_analyzer()
            rule_data_dict = await analyzer.analyze_and_create_rule(
                video_path=tmp_video_path,
                movement_title=movement_title,
                user_id=current_user.id
            )
            
            # Create rule (initially inactive for review)
            rule_data_dict['is_active'] = False
            rule_data = AssessmentRuleCreate(**rule_data_dict)
            
            rule = await service.create_rule(rule_data, current_user)
            
            return {
                "message": "Standard video analyzed successfully",
                "rule": AssessmentRuleResponse.model_validate(rule).model_dump()
            }
        
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_video_path)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temp file {tmp_video_path}: {cleanup_error}")
    
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing standard video upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process video: {str(e)}"
        )


# =============================================================================
# Public Routes - Active Rules (for dropdown selection)
# =============================================================================

@router.get("/rules/active", response_model=list[AssessmentRuleResponse])
async def get_active_rules(
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get all active assessment rules (for dropdown selection in upload form)
    """
    service = AssessmentRulesService(db)
    
    try:
        rules = await service.get_active_rules(current_user)
        return [AssessmentRuleResponse.model_validate(rule) for rule in rules]
    except Exception as e:
        logger.error(f"Error getting active rules: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load active rules"
        )
