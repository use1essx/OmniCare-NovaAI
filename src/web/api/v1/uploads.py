# src/web/api/v1/uploads.py
"""
File upload endpoints for medical document management
"""

import os
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.exceptions import ValidationError
from src.core.validators import FileValidator
from src.security.auth import InputSanitizer
from src.database.connection import get_async_db
from src.database.models_comprehensive import UploadedDocument, User
# Note: FileProcessor and QualityScorer removed with data pipeline
# from src.data.processors.file_processor import FileProcessor
# from src.data.processors.quality_scorer import QualityScorer
from src.web.auth.dependencies import get_current_active_user
from src.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/uploads", tags=["uploads"])

# WebSocket connection manager for upload progress
class UploadProgressManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, upload_id: str):
        await websocket.accept()
        self.active_connections[upload_id] = websocket
    
    def disconnect(self, upload_id: str):
        if upload_id in self.active_connections:
            del self.active_connections[upload_id]
    
    async def send_progress(self, upload_id: str, progress: dict):
        if upload_id in self.active_connections:
            try:
                await self.active_connections[upload_id].send_text(json.dumps(progress))
            except Exception:
                # Connection closed, remove it
                self.disconnect(upload_id)

upload_manager = UploadProgressManager()

# Request/Response Models
class UploadResponse(BaseModel):
    """Response model for file upload"""
    success: bool
    document_id: Optional[int] = None
    filename: str
    file_size: int
    processing_status: str
    quality_score: Optional[float] = None
    message: str
    warnings: List[str] = []
    task_id: Optional[str] = None

class DocumentMetadata(BaseModel):
    """Document metadata for upload"""
    title: Optional[str] = None
    description: Optional[str] = None
    category: str
    tags: List[str] = []
    language: str = "en"
    is_sensitive: bool = False

class DocumentSearchParams(BaseModel):
    """Search parameters for documents"""
    query: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    language: Optional[str] = None
    uploaded_by: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    page: int = 1
    limit: int = 20

class DocumentUpdateRequest(BaseModel):
    """Document update request"""
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None

# File Upload Endpoints
@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma-separated tags
    language: str = Form("en"),
    is_sensitive: bool = Form(False),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Upload a medical document for processing and review
    
    - **file**: Document file (PDF, JPG, PNG, TXT)
    - **category**: Document category (required)
    - **title**: Document title (optional)
    - **description**: Document description (optional)
    - **tags**: Comma-separated tags (optional)
    - **language**: Document language (default: en)
    - **is_sensitive**: Whether document contains sensitive data
    """
    try:
        # Input validation and sanitization
        sanitizer = InputSanitizer()
        file_validator = FileValidator()
        
        # Validate file
        file_content = await file.read()
        validation_result = file_validator.validate_file(
            file_content, 
            file.filename, 
            file.content_type
        )
        
        if not validation_result.is_valid:
            raise ValidationError(
                f"File validation failed: {', '.join(validation_result.errors)}"
            )
        
        # Sanitize inputs
        safe_title = sanitizer.sanitize_string(title or "", max_length=255) if title else None
        safe_description = sanitizer.sanitize_string(description or "", max_length=2000) if description else None
        safe_category = sanitizer.sanitize_string(category, max_length=100)
        
        # Parse tags
        tag_list = []
        if tags:
            tag_list = [
                sanitizer.sanitize_string(tag.strip(), max_length=50) 
                for tag in tags.split(",") 
                if tag.strip()
            ][:10]  # Limit to 10 tags
        
        # Check file size
        if len(file_content) > settings.upload_max_size:
            raise ValidationError(
                f"File size {len(file_content)} exceeds maximum {settings.upload_max_size}"
            )
        
        # Generate unique filename and storage path
        file_extension = Path(file.filename).suffix.lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        storage_path = settings.upload_path / "documents" / datetime.now().strftime("%Y/%m/%d")
        storage_path.mkdir(parents=True, exist_ok=True)
        full_file_path = storage_path / unique_filename
        
        # Save file temporarily for processing
        with open(full_file_path, "wb") as f:
            f.write(file_content)
        
        # Create database record (align with UploadedDocument schema)
        document = UploadedDocument(
            original_filename=file.filename,
            stored_filename=unique_filename,
            file_type=file_extension.lstrip('.'),
            mime_type=file.content_type,
            file_size=len(file_content),
            file_path=str(full_file_path),
            title=safe_title or file.filename,
            description=safe_description,
            category=safe_category,
            tags=tag_list or None,
            document_type="training_material",
            processing_status="processing",
            uploaded_by=current_user.id,
            document_metadata={
                "language": language,
                "is_sensitive": is_sensitive,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "content_type": file.content_type,
                "validation_warnings": validation_result.warnings
            }
        )
        
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        # Start background processing
        task_id = str(uuid.uuid4())
        background_tasks.add_task(
            process_document_background,
            document.id,
            full_file_path,
            task_id
        )
        
        logger.info(f"File uploaded: {file.filename} by user {current_user.id}")
        
        return UploadResponse(
            success=True,
            document_id=document.id,
            filename=file.filename,
            file_size=len(file_content),
            processing_status="processing",
            message="File uploaded successfully and processing started",
            warnings=validation_result.warnings,
            task_id=task_id
        )
        
    except ValidationError as e:
        logger.warning(f"File upload validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during upload")

@router.post("/upload/batch", response_model=List[UploadResponse])
async def upload_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    category: str = Form(...),
    language: str = Form("en"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Upload multiple files in batch
    Maximum 10 files per batch
    """
    if len(files) > 10:
        raise HTTPException(
            status_code=400, 
            detail="Maximum 10 files allowed per batch upload"
        )
    
    results = []
    for file in files:
        try:
            # Create individual upload request
            result = await upload_file(
                background_tasks=background_tasks,
                file=file,
                category=category,
                language=language,
                current_user=current_user,
                db=db
            )
            results.append(result)
        except Exception as e:
            logger.error(f"Batch upload error for {file.filename}: {e}")
            results.append(UploadResponse(
                success=False,
                filename=file.filename,
                file_size=0,
                processing_status="error",
                message=f"Upload failed: {str(e)}"
            ))
    
    return results

@router.websocket("/ws/progress/{upload_id}")
async def upload_progress_websocket(websocket: WebSocket, upload_id: str):
    """WebSocket endpoint for upload progress tracking"""
    await upload_manager.connect(websocket, upload_id)
    try:
        while True:
            # Keep connection alive and listen for client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        upload_manager.disconnect(upload_id)

@router.post("/upload-with-progress", response_model=UploadResponse)
async def upload_file_with_progress(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    language: str = Form("en"),
    is_sensitive: bool = Form(False),
    upload_id: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Upload a file with real-time progress tracking"""
    try:
        # Send initial progress
        await upload_manager.send_progress(upload_id, {
            "stage": "validation",
            "progress": 10,
            "message": "Validating file...",
            "filename": file.filename
        })
        
        # Input validation and sanitization
        sanitizer = InputSanitizer()
        file_validator = FileValidator()
        
        # Validate file
        file_content = await file.read()
        
        # Check file size
        if len(file_content) > settings.upload_max_size:
            await upload_manager.send_progress(upload_id, {
                "stage": "error",
                "progress": 0,
                "message": f"File size {len(file_content)} exceeds maximum {settings.upload_max_size}",
                "filename": file.filename
            })
            raise ValidationError(
                f"File size {len(file_content)} exceeds maximum {settings.upload_max_size}"
            )
        
        await upload_manager.send_progress(upload_id, {
            "stage": "content_validation",
            "progress": 25,
            "message": "Validating file content...",
            "filename": file.filename
        })
        
        validation_result = file_validator.validate_file(
            file_content, 
            file.filename, 
            file.content_type
        )
        
        if not validation_result.is_valid:
            await upload_manager.send_progress(upload_id, {
                "stage": "error",
                "progress": 0,
                "message": f"File validation failed: {', '.join(validation_result.errors)}",
                "filename": file.filename
            })
            raise ValidationError(
                f"File validation failed: {', '.join(validation_result.errors)}"
            )
        
        await upload_manager.send_progress(upload_id, {
            "stage": "saving",
            "progress": 50,
            "message": "Saving file...",
            "filename": file.filename
        })
        
        # Sanitize inputs
        safe_title = sanitizer.sanitize_string(title or "", max_length=255) if title else None
        safe_description = sanitizer.sanitize_string(description or "", max_length=2000) if description else None
        safe_category = sanitizer.sanitize_string(category, max_length=100)
        
        # Parse tags
        tag_list = []
        if tags:
            tag_list = [
                sanitizer.sanitize_string(tag.strip(), max_length=50) 
                for tag in tags.split(",") 
                if tag.strip()
            ][:10]  # Limit to 10 tags
        
        # Generate unique filename and storage path
        file_extension = Path(file.filename).suffix.lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        storage_path = settings.upload_path / "documents" / datetime.now().strftime("%Y/%m/%d")
        storage_path.mkdir(parents=True, exist_ok=True)
        full_file_path = storage_path / unique_filename
        
        # Save file temporarily for processing
        with open(full_file_path, "wb") as f:
            f.write(file_content)
        
        await upload_manager.send_progress(upload_id, {
            "stage": "database",
            "progress": 75,
            "message": "Creating database record...",
            "filename": file.filename
        })
        
        # Create database record
        document = UploadedDocument(
            original_filename=file.filename,
            file_type=file_extension.lstrip('.'),
            file_size=len(file_content),
            file_path=str(full_file_path),
            title=safe_title or file.filename,
            description=safe_description,
            category=safe_category,
            keywords={"tags": tag_list},
            status="processing",
            uploaded_by=current_user.id,
            metadata={
                "language": language,
                "is_sensitive": is_sensitive,
                "upload_timestamp": datetime.utcnow().isoformat(),
                "content_type": file.content_type,
                "validation_warnings": validation_result.warnings,
                "upload_id": upload_id
            }
        )
        
        db.add(document)
        await db.commit()
        await db.refresh(document)
        
        await upload_manager.send_progress(upload_id, {
            "stage": "processing",
            "progress": 90,
            "message": "Queuing for background processing...",
            "filename": file.filename
        })
        
        # Start background processing
        task_id = str(uuid.uuid4())
        background_tasks.add_task(
            process_document_background,
            document.id,
            full_file_path,
            task_id,
            upload_id
        )
        
        await upload_manager.send_progress(upload_id, {
            "stage": "complete",
            "progress": 100,
            "message": "Upload complete! Processing in background...",
            "filename": file.filename,
            "document_id": document.id,
            "task_id": task_id
        })
        
        logger.info(f"File uploaded with progress tracking: {file.filename} by user {current_user.id}")
        
        return UploadResponse(
            success=True,
            document_id=document.id,
            filename=file.filename,
            file_size=len(file_content),
            processing_status="processing",
            message="File uploaded successfully and processing started",
            warnings=validation_result.warnings,
            task_id=task_id
        )
        
    except ValidationError as e:
        await upload_manager.send_progress(upload_id, {
            "stage": "error",
            "progress": 0,
            "message": str(e),
            "filename": file.filename
        })
        logger.warning(f"File upload validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        await upload_manager.send_progress(upload_id, {
            "stage": "error",
            "progress": 0,
            "message": f"Upload failed: {str(e)}",
            "filename": file.filename
        })
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during upload")

@router.post("/bulk-operations")
async def bulk_document_operations(
    document_ids: List[int],
    operation: str,  # "approve", "reject", "delete"
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Perform bulk operations on multiple documents"""
    try:
        if operation not in ["approve", "reject", "delete"]:
            raise HTTPException(status_code=400, detail="Invalid operation")
        
        results = []
        
        for doc_id in document_ids:
            try:
                document = await db.query(UploadedDocument).filter(
                    UploadedDocument.id == doc_id
                ).first()
                
                if not document:
                    results.append({
                        "document_id": doc_id,
                        "success": False,
                        "error": "Document not found"
                    })
                    continue
                
                if operation == "approve":
                    document.status = "approved"
                    document.approved_by = current_user.id
                    document.approved_at = datetime.utcnow()
                    
                elif operation == "reject":
                    document.status = "rejected"
                    document.metadata = document.metadata or {}
                    document.metadata.update({
                        "rejection_reason": reason,
                        "rejected_by": current_user.id,
                        "rejected_at": datetime.utcnow().isoformat()
                    })
                    
                elif operation == "delete":
                    # Delete physical file
                    try:
                        if document.file_path and os.path.exists(document.file_path):
                            os.remove(document.file_path)
                    except Exception as e:
                        logger.warning(f"Could not delete file {document.file_path}: {e}")
                    
                    await db.delete(document)
                
                results.append({
                    "document_id": doc_id,
                    "success": True,
                    "operation": operation
                })
                
            except Exception as e:
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(e)
                })
        
        await db.commit()
        
        successful_ops = sum(1 for r in results if r["success"])
        
        logger.info(f"Bulk operation {operation} by user {current_user.id}: {successful_ops}/{len(document_ids)} successful")
        
        return {
            "operation": operation,
            "total_documents": len(document_ids),
            "successful_operations": successful_ops,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk operation error: {e}")
        raise HTTPException(status_code=500, detail="Error performing bulk operation")

@router.get("/documents", response_model=Dict[str, Any])
async def list_documents(
    query: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    language: Optional[str] = None,
    uploaded_by: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List and search uploaded documents with filtering and pagination
    """
    try:
        from sqlalchemy import and_, or_
        from sqlalchemy.orm import selectinload
        
        # Build query
        query_filters = []
        
        if query:
            search_filter = or_(
                UploadedDocument.title.ilike(f"%{query}%"),
                UploadedDocument.description.ilike(f"%{query}%"),
                UploadedDocument.original_filename.ilike(f"%{query}%")
            )
            query_filters.append(search_filter)
        
        if category:
            query_filters.append(UploadedDocument.category == category)
        
        if status:
            query_filters.append(UploadedDocument.status == status)
        
        if language:
            query_filters.append(
                UploadedDocument.metadata['language'].astext == language
            )
        
        if uploaded_by:
            query_filters.append(UploadedDocument.uploaded_by == uploaded_by)
        
        # Calculate offset
        offset = (page - 1) * limit
        
        # Execute query
        base_query = db.query(UploadedDocument).options(
            selectinload(UploadedDocument.uploaded_by_user),
            selectinload(UploadedDocument.approved_by_user)
        )
        
        if query_filters:
            base_query = base_query.filter(and_(*query_filters))
        
        # Get total count
        total_count = await base_query.count()
        
        # Get paginated results
        documents = await base_query.order_by(
            UploadedDocument.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        # Format response
        document_list = []
        for doc in documents:
            document_list.append({
                "id": doc.id,
                "title": doc.title,
                "description": doc.description,
                "category": doc.category,
                "original_filename": doc.original_filename,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "status": doc.status,
                "quality_score": float(doc.quality_score) if doc.quality_score else None,
                "usage_count": doc.usage_count,
                "uploaded_by": {
                    "id": doc.uploaded_by_user.id,
                    "username": doc.uploaded_by_user.username,
                    "full_name": doc.uploaded_by_user.full_name
                } if doc.uploaded_by_user else None,
                "approved_by": {
                    "id": doc.approved_by_user.id,
                    "username": doc.approved_by_user.username,
                    "full_name": doc.approved_by_user.full_name
                } if doc.approved_by_user else None,
                "created_at": doc.created_at.isoformat(),
                "approved_at": doc.approved_at.isoformat() if doc.approved_at else None,
                "keywords": doc.keywords,
                "metadata": doc.metadata
            })
        
        return {
            "documents": document_list,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total_count,
                "pages": (total_count + limit - 1) // limit
            },
            "filters": {
                "query": query,
                "category": category,
                "status": status,
                "language": language,
                "uploaded_by": uploaded_by
            }
        }
        
    except Exception as e:
        logger.error(f"Document listing error: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving documents")

@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get detailed information about a specific document"""
    try:
        from sqlalchemy.orm import selectinload
        
        document = await db.query(UploadedDocument).options(
            selectinload(UploadedDocument.uploaded_by_user),
            selectinload(UploadedDocument.approved_by_user)
        ).filter(UploadedDocument.id == document_id).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "id": document.id,
            "title": document.title,
            "description": document.description,
            "category": document.category,
            "original_filename": document.original_filename,
            "file_type": document.file_type,
            "file_size": document.file_size,
            "file_path": document.file_path,
            "extracted_content": document.extracted_content,
            "content_summary": document.content_summary,
            "keywords": document.keywords,
            "quality_score": float(document.quality_score) if document.quality_score else None,
            "status": document.status,
            "usage_count": document.usage_count,
            "last_used": document.last_used.isoformat() if document.last_used else None,
            "uploaded_by": {
                "id": document.uploaded_by_user.id,
                "username": document.uploaded_by_user.username,
                "full_name": document.uploaded_by_user.full_name
            } if document.uploaded_by_user else None,
            "approved_by": {
                "id": document.approved_by_user.id,
                "username": document.approved_by_user.username,
                "full_name": document.approved_by_user.full_name
            } if document.approved_by_user else None,
            "created_at": document.created_at.isoformat(),
            "updated_at": document.updated_at.isoformat(),
            "approved_at": document.approved_at.isoformat() if document.approved_at else None,
            "metadata": document.metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving document")

@router.put("/documents/{document_id}")
async def update_document(
    document_id: int,
    update_data: DocumentUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Update document metadata"""
    try:
        document = await db.query(UploadedDocument).filter(
            UploadedDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Update fields if provided
        sanitizer = InputSanitizer()
        
        if update_data.title is not None:
            document.title = sanitizer.sanitize_string(update_data.title, max_length=255)
        
        if update_data.description is not None:
            document.description = sanitizer.sanitize_string(update_data.description, max_length=2000)
        
        if update_data.category is not None:
            document.category = sanitizer.sanitize_string(update_data.category, max_length=100)
        
        if update_data.tags is not None:
            # Update keywords
            document.keywords = document.keywords or {}
            document.keywords["tags"] = [
                sanitizer.sanitize_string(tag.strip(), max_length=50)
                for tag in update_data.tags
                if tag.strip()
            ][:10]
        
        if update_data.status is not None:
            if update_data.status in ["pending_approval", "approved", "rejected", "processing"]:
                document.status = update_data.status
                
                if update_data.status == "approved":
                    document.approved_by = current_user.id
                    document.approved_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(document)
        
        logger.info(f"Document {document_id} updated by user {current_user.id}")
        
        return {"success": True, "message": "Document updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document update error: {e}")
        raise HTTPException(status_code=500, detail="Error updating document")

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Delete a document and its associated file"""
    try:
        document = await db.query(UploadedDocument).filter(
            UploadedDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete physical file
        try:
            if document.file_path and os.path.exists(document.file_path):
                os.remove(document.file_path)
        except Exception as e:
            logger.warning(f"Could not delete file {document.file_path}: {e}")
        
        # Delete database record
        await db.delete(document)
        await db.commit()
        
        logger.info(f"Document {document_id} deleted by user {current_user.id}")
        
        return {"success": True, "message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document deletion error: {e}")
        raise HTTPException(status_code=500, detail="Error deleting document")

@router.post("/documents/{document_id}/approve")
async def approve_document(
    document_id: int,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Approve a document for use in the system"""
    try:
        document = await db.query(UploadedDocument).filter(
            UploadedDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if document.status == "approved":
            return {"success": True, "message": "Document already approved"}
        
        document.status = "approved"
        document.approved_by = current_user.id
        document.approved_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(document)
        
        logger.info(f"Document {document_id} approved by user {current_user.id}")
        
        return {"success": True, "message": "Document approved successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document approval error: {e}")
        raise HTTPException(status_code=500, detail="Error approving document")

@router.post("/documents/{document_id}/reject")
async def reject_document(
    document_id: int,
    reason: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Reject a document with reason"""
    try:
        document = await db.query(UploadedDocument).filter(
            UploadedDocument.id == document_id
        ).first()
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        document.status = "rejected"
        document.metadata = document.metadata or {}
        document.metadata["rejection_reason"] = reason
        document.metadata["rejected_by"] = current_user.id
        document.metadata["rejected_at"] = datetime.utcnow().isoformat()
        
        await db.commit()
        await db.refresh(document)
        
        logger.info(f"Document {document_id} rejected by user {current_user.id}")
        
        return {"success": True, "message": "Document rejected successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document rejection error: {e}")
        raise HTTPException(status_code=500, detail="Error rejecting document")

@router.get("/processing-status/{task_id}")
async def get_processing_status(
    task_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get the processing status of an uploaded file"""
    # This would integrate with your background task system
    # For now, return a mock response
    return {
        "task_id": task_id,
        "status": "processing",
        "progress": 50,
        "message": "Processing file content..."
    }

@router.get("/categories")
async def get_categories(
    current_user: User = Depends(get_current_active_user)
):
    """Get available document categories"""
    categories = [
        "medical_guidelines",
        "treatment_protocols", 
        "medication_info",
        "emergency_procedures",
        "hk_health_policies",
        "clinical_research",
        "patient_education",
        "administrative_forms"
    ]
    return {"categories": categories}

@router.get("/stats")
async def get_upload_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get upload statistics"""
    try:
        from sqlalchemy import func
        
        # Get basic stats
        total_docs = await db.query(func.count(UploadedDocument.id)).scalar()
        pending_docs = await db.query(func.count(UploadedDocument.id)).filter(
            UploadedDocument.status == "pending_approval"
        ).scalar()
        approved_docs = await db.query(func.count(UploadedDocument.id)).filter(
            UploadedDocument.status == "approved"
        ).scalar()
        
        # Get category breakdown
        category_stats = await db.query(
            UploadedDocument.category,
            func.count(UploadedDocument.id).label("count")
        ).group_by(UploadedDocument.category).all()
        
        # Get file type breakdown
        type_stats = await db.query(
            UploadedDocument.file_type,
            func.count(UploadedDocument.id).label("count")
        ).group_by(UploadedDocument.file_type).all()
        
        return {
            "total_documents": total_docs,
            "pending_approval": pending_docs,
            "approved_documents": approved_docs,
            "categories": [{"category": cat, "count": count} for cat, count in category_stats],
            "file_types": [{"type": ftype, "count": count} for ftype, count in type_stats]
        }
        
    except Exception as e:
        logger.error(f"Stats retrieval error: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving statistics")

# Background processing function
async def process_document_background(document_id: int, file_path: Path, task_id: str, upload_id: str = None):
    """Background task for processing uploaded documents"""
    try:
        from src.database.connection import get_async_session
        
        async with get_async_session() as db:
            document = await db.query(UploadedDocument).filter(
                UploadedDocument.id == document_id
            ).first()
            
            if not document:
                logger.error(f"Document {document_id} not found for processing")
                return
            
            # Note: File processing disabled (processors removed with data pipeline)
            # Initialize processors
            # file_processor = FileProcessor()
            # quality_scorer = QualityScorer()
            
            try:
                # Send progress update
                if upload_id:
                    await upload_manager.send_progress(upload_id, {
                        "stage": "background_processing",
                        "progress": 30,
                        "message": "File uploaded successfully",
                        "document_id": document_id
                    })
                
                # Note: Content processing disabled
                # Process file content
                # processing_result = await file_processor.process_file(
                #     file_path, 
                #     document.file_type
                # )
                
                # Update document with extracted content
                # document.extracted_content = processing_result.get("content", "")
                # document.content_summary = processing_result.get("summary", "")
                document.extracted_content = ""
                document.content_summary = "File uploaded (processing disabled)"
                
                # Send progress update
                if upload_id:
                    await upload_manager.send_progress(upload_id, {
                        "stage": "quality_scoring",
                        "progress": 60,
                        "message": "Upload complete",
                        "document_id": document_id
                    })
                
                # Note: Quality scoring disabled
                # Calculate quality score
                # quality_score = await quality_scorer.score_medical_content(
                #     document.extracted_content,
                #     document.category
                # )
                # document.quality_score = quality_score
                document.quality_score = 0.0
                
                # Update keywords
                keywords = document.keywords or {}
                keywords.update(processing_result.get("keywords", {}))
                document.keywords = keywords
                
                # Update status
                document.status = "pending_approval"
                
                # Update metadata
                metadata = document.metadata or {}
                metadata.update({
                    "processing_completed_at": datetime.utcnow().isoformat(),
                    "task_id": task_id,
                    "processing_time_ms": processing_result.get("processing_time_ms", 0)
                })
                document.metadata = metadata
                
                await db.commit()
                
                # Send final progress update
                if upload_id:
                    await upload_manager.send_progress(upload_id, {
                        "stage": "processing_complete",
                        "progress": 100,
                        "message": "Document processing complete!",
                        "document_id": document_id,
                        "quality_score": float(quality_score) if quality_score else None,
                        "status": "pending_approval"
                    })
                
                logger.info(f"Document {document_id} processed successfully")
                
            except Exception as e:
                # Update status to error
                document.status = "processing_error"
                metadata = document.metadata or {}
                metadata.update({
                    "error_message": str(e),
                    "error_timestamp": datetime.utcnow().isoformat(),
                    "task_id": task_id
                })
                document.metadata = metadata
                
                await db.commit()
                
                logger.error(f"Document {document_id} processing failed: {e}")
                
    except Exception as e:
        logger.error(f"Background processing error for document {document_id}: {e}")