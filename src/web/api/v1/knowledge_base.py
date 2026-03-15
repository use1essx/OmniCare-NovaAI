"""
Knowledge Base API

Admin/org-admin upload, list, status, delete for knowledge documents.
Uses DocumentIngestionService for ingestion and HybridRetriever for retrieval status.
"""

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query, Request
from typing import Optional, List, Dict, Any
import hashlib
import os
import json
import unicodedata
import logging
import traceback
from pathlib import Path
from fastapi import BackgroundTasks

from src.core.config import settings

logger = logging.getLogger(__name__)
from src.knowledge_base.document_ingestion import DocumentIngestionService, get_ingestion_service
from src.database.vector_store import get_vector_store
from src.knowledge_base.extractors import detect_and_extract, ExtractionError
from src.knowledge_base.media_pipeline import process_media_for_kb, MediaProcessingError
from src.web.auth.dependencies import require_org_admin, get_optional_user
from src.database.models_comprehensive import User

router = APIRouter(prefix="/knowledge", tags=["knowledge_base"])


class _DevAdmin:
    def __init__(self, organization_id: int):
        self.id = 0
        self.organization_id = organization_id
        self.is_admin = True
        self.role = "admin"


async def get_kb_admin(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Allow admin access or dev bypass for KB sandbox."""
    if settings.kb_sandbox_dev_mode:
        return _DevAdmin(settings.kb_sandbox_dev_org_id)
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await require_org_admin(current_user)


def _calc_file_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def _is_garbled_taxonomy_value(value: str) -> bool:
    if not value:
        return False
    if "\ufffd" in value:
        return True
    control = any(unicodedata.category(c) == "Cc" for c in value if c not in ("\n", "\t", " "))
    if control:
        return True
    latin1 = sum(1 for c in value if 0x00C0 <= ord(c) <= 0x00FF)
    extended = sum(1 for c in value if 0x0080 <= ord(c) <= 0x00FF)
    cjk = sum(1 for c in value if 0x4E00 <= ord(c) <= 0x9FFF)
    ascii_letters = sum(1 for c in value if ("a" <= c.lower() <= "z"))
    mojibake_markers = ("Ã", "Â", "å", "ç", "œ", "™", "ï»¿")
    if any(m in value for m in mojibake_markers) and cjk == 0:
        return True
    if latin1 >= 2 and cjk == 0 and ascii_letters == 0:
        return True
    if extended >= 2 and cjk == 0:
        return True
    return False


async def _ensure_taxonomy_table() -> None:
    from sqlalchemy import text
    from src.database.connection import get_async_db

    sql = text("""
        CREATE TABLE IF NOT EXISTS knowledge_taxonomy (
            id SERIAL PRIMARY KEY,
            taxonomy_type VARCHAR(20) NOT NULL,
            value TEXT NOT NULL,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            is_active BOOLEAN DEFAULT TRUE
        );
    """)
    async for session in get_async_db():
        await session.execute(sql)
        await session.commit()


@router.post("/upload")
async def upload_knowledge_document(
    file: Optional[UploadFile] = File(None),
    text_content: Optional[str] = Form(None),
    title: str = Form(...),
    category: str = Form("general"),
    category_id: Optional[int] = Form(None),  # NEW: Accept category ID
    language: str = Form("en"),
    tags: Optional[str] = Form(None),
    topics: Optional[str] = Form(None),
    age_groups: Optional[str] = Form(None),
    auto_tag: bool = Form(True),
    auto_summary: bool = Form(True),
    visibility: str = Form("org"),
    organization_id: Optional[int] = Form(None),
    force_reindex: bool = Form(False),
    # FORM METADATA: Form Smart Delivery feature
    is_form: bool = Form(False),
    form_type: Optional[str] = Form(None),
    form_category: Optional[str] = Form(None),
    submission_instructions: Optional[str] = Form(None),
    language_versions: Optional[str] = Form(None),  # JSON string: {"en": 123, "zh-HK": 124}
    requires_signature: Optional[bool] = Form(None),
    estimated_completion_time_minutes: Optional[int] = Form(None),
    background_tasks: BackgroundTasks = None,
    current_admin=Depends(get_kb_admin),
):
    """
    Upload a knowledge document (file or raw text).
    Only admin/org-admin.
    
    Form Smart Delivery Feature:
    - is_form: Mark document as a form (default: False)
    - form_type: Type of form (e.g., "application", "assessment", "registration")
    - form_category: Category of form (e.g., "patient_registration", "health_assessment")
    - submission_instructions: Instructions for completing and submitting the form
    - language_versions: JSON string mapping language codes to document IDs (e.g., '{"en": 123, "zh-HK": 124}')
    - requires_signature: Whether the form requires a signature
    - estimated_completion_time_minutes: Estimated time to complete the form
    """
    if not file and not text_content:
        raise HTTPException(status_code=400, detail="Provide file or text_content")

    ingestion: DocumentIngestionService = get_ingestion_service()

    content = ""
    file_hash = None
    source_type = "text"
    metadata = {}

    if file:
        data = await file.read()
        if len(data) > settings.knowledge_max_upload_size:
            raise HTTPException(status_code=413, detail="File too large")
        file_hash = _calc_file_hash(data)
        mime = (file.content_type or "").lower()

        # Video/Audio path
        if mime.startswith("video/") or mime.startswith("audio/"):
            # Enforce max duration by rough size; hard cap length via pipeline defaults
            try:
                transcript, chunks_override = await process_media_for_kb(
                    data,
                    file.filename or "media",
                    language=language if language else "en-US",
                    summary=True,
                    max_minutes=settings.knowledge_max_video_minutes,
                )
            except MediaProcessingError as e:
                raise HTTPException(status_code=400, detail=str(e))
            content = transcript
            source_type = "video" if mime.startswith("video/") else "audio"
            metadata["content_type"] = file.content_type
            metadata["filename"] = file.filename
            metadata["file_size"] = len(data)
            metadata["file_path"] = None  # optional to persist later
            if chunks_override and any(getattr(c, "chunk_type", None) == "summary" for c in chunks_override):
                auto_summary = False
        else:
            # Document/image path
            try:
                content, extracted_meta = detect_and_extract(file.filename or "upload", data)
                source_type = extracted_meta.get("source_type", "file")
                metadata.update(extracted_meta)
            except ExtractionError as e:
                raise HTTPException(status_code=400, detail=str(e))

            # persist file to upload path
            dest_dir = Path(settings.knowledge_upload_path)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / (file.filename or f"doc-{file_hash}.bin")
            with open(dest_path, "wb") as f:
                f.write(data)
            metadata["file_path"] = str(dest_path)
            metadata["file_size"] = len(data)
            metadata["content_type"] = file.content_type
            metadata["filename"] = file.filename
            chunks_override = None
    else:
        content = text_content or ""
        file_hash = _calc_file_hash(content.encode())
        chunks_override = None

    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    topic_list = [t.strip() for t in topics.split(",")] if topics else []
    age_list = [a.strip() for a in age_groups.split(",")] if age_groups else []

    # FORM METADATA: Build form metadata if document is marked as a form
    # VALIDATION: Input sanitized for XSS and validated for correct types
    form_metadata = {}
    if is_form:
        form_metadata["is_form"] = True
        
        # Validate form_type (alphanumeric, underscore, hyphen only)
        if form_type:
            if not form_type.replace("_", "").replace("-", "").isalnum():
                raise HTTPException(
                    status_code=400,
                    detail="form_type must contain only alphanumeric characters, underscores, and hyphens"
                )
            form_metadata["form_type"] = form_type
        
        # Validate form_category (alphanumeric, underscore, hyphen only)
        if form_category:
            if not form_category.replace("_", "").replace("-", "").isalnum():
                raise HTTPException(
                    status_code=400,
                    detail="form_category must contain only alphanumeric characters, underscores, and hyphens"
                )
            form_metadata["form_category"] = form_category
        
        # Validate submission_instructions (check for XSS patterns)
        if submission_instructions:
            # SECURITY: XSS prevention - reject common XSS patterns
            xss_patterns = ["<script", "javascript:", "onerror=", "onload=", "<iframe"]
            submission_lower = submission_instructions.lower()
            if any(pattern in submission_lower for pattern in xss_patterns):
                raise HTTPException(
                    status_code=400,
                    detail="submission_instructions contains invalid content"
                )
            form_metadata["submission_instructions"] = submission_instructions
        
        # Validate language_versions JSON
        if language_versions:
            try:
                lang_versions_dict = json.loads(language_versions)
                # Validate it's a dict with string keys and integer values
                if not isinstance(lang_versions_dict, dict):
                    raise HTTPException(
                        status_code=400,
                        detail="language_versions must be a JSON object"
                    )
                for key, value in lang_versions_dict.items():
                    if not isinstance(key, str) or not isinstance(value, int):
                        raise HTTPException(
                            status_code=400,
                            detail="language_versions must map language codes (strings) to document IDs (integers)"
                        )
                form_metadata["language_versions"] = lang_versions_dict
            except (json.JSONDecodeError, TypeError):
                raise HTTPException(
                    status_code=400, 
                    detail="language_versions must be valid JSON (e.g., '{\"en\": 123, \"zh-HK\": 124}')"
                )
        
        if requires_signature is not None:
            form_metadata["requires_signature"] = requires_signature
        
        # Validate estimated_completion_time_minutes (must be positive)
        if estimated_completion_time_minutes is not None:
            if estimated_completion_time_minutes <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="estimated_completion_time_minutes must be a positive integer"
                )
            form_metadata["estimated_completion_time_minutes"] = estimated_completion_time_minutes
    else:
        # Explicitly set is_form to false for non-form documents
        form_metadata["is_form"] = False
    
    # Merge form metadata into the main metadata dict
    metadata.update(form_metadata)

    async def _run_ingest():
        return await ingestion.ingest_document(
            title=title,
            content=content,
            category=category,
            category_id=category_id,  # NEW: Pass category ID
            language=language,
            tags=tag_list,
            topics=topic_list or None,
            age_groups=age_list or None,
            auto_tag=auto_tag,
            auto_summary=auto_summary,
            source="upload",
            author=str(current_admin.id),
            metadata=metadata,
            organization_id=organization_id or current_admin.organization_id,
            visibility=visibility,
            file_hash=file_hash,
            force_reindex=force_reindex,
            source_type=source_type,
            chunks_override=chunks_override,
        )

    # Background task for large uploads (>20MB or video/audio)
    is_heavy = (file and len(data) > 20 * 1024 * 1024) or (file and (file.content_type or "").startswith(("video/", "audio/")))
    if is_heavy and background_tasks is not None:
        background_tasks.add_task(_run_ingest)
        return {
            "document_id": None,
            "status": "processing",
            "message": "Ingestion started in background"
        }

    result = await _run_ingest()

    return {
        "document_id": result.document_id,
        "status": result.status,
        "error": result.error,
        "chunk_count": result.chunk_count,
    }


@router.get("/taxonomy")
async def get_taxonomy(
    visibility: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    current_admin=Depends(get_kb_admin),
):
    """Return distinct categories/topics/age_groups for suggestion lists."""
    await _ensure_taxonomy_table()
    filters = []
    params = {"limit": limit}
    if visibility:
        filters.append("visibility = :visibility")
        params["visibility"] = visibility
    org_scope = org_id or current_admin.organization_id
    filters.append("(organization_id = :org_id OR visibility = 'public')")
    params["org_id"] = org_scope

    where_clause = " AND ".join(filters) if filters else "TRUE"
    from sqlalchemy import text
    from src.database.connection import get_async_db

    sql = text(f"""
        SELECT category, document_metadata as metadata
        FROM uploaded_documents
        WHERE {where_clause} AND is_active = TRUE
        ORDER BY updated_at DESC
        LIMIT :limit
    """)

    taxonomy_sql = text("""
        SELECT id, taxonomy_type, value
        FROM knowledge_taxonomy
        WHERE is_active = TRUE
        ORDER BY updated_at DESC
        LIMIT :limit
    """)

    categories: Dict[str, int] = {}
    topics: Dict[str, int] = {}
    age_groups: Dict[str, int] = {}

    async for session in get_async_db():
        result = await session.execute(sql, params)
        rows = result.fetchall()
        taxonomy_rows = (await session.execute(taxonomy_sql, {"limit": limit})).fetchall()

    for row in rows:
        cat = (row.category or "").strip()
        if cat and not _is_garbled_taxonomy_value(cat):
            categories[cat] = categories.get(cat, 0) + 1

        meta_val = row.metadata
        if isinstance(meta_val, str):
            try:
                meta_val = json.loads(meta_val)
            except Exception:
                meta_val = {}
        if not isinstance(meta_val, dict):
            meta_val = {}

        topic_sources = meta_val.get("topics_all") or []
        if not topic_sources:
            topic_sources = []
            topic_sources.extend(meta_val.get("topics") or [])
            topic_sources.extend(meta_val.get("topics_en") or [])
            topic_sources.extend(meta_val.get("topics_zh") or [])

        for topic in topic_sources:
            topic = str(topic).strip()
            if not topic or _is_garbled_taxonomy_value(topic):
                continue
            topics[topic] = topics.get(topic, 0) + 1
        for age in meta_val.get("age_groups", []) or []:
            age = str(age).strip()
            if not age:
                continue
            age_groups[age] = age_groups.get(age, 0) + 1

    def _build_map(items: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
        return {
            k: {"value": k, "count": v, "source": "document", "id": None}
            for k, v in items.items()
        }

    categories_map = _build_map(categories)
    topics_map = _build_map(topics)
    age_groups_map = _build_map(age_groups)

    for row in taxonomy_rows:
        ttype = (row.taxonomy_type or "").strip().lower()
        value = (row.value or "").strip()
        if not value:
            continue
        target = None
        if ttype == "category":
            target = categories_map
        elif ttype == "topic":
            target = topics_map
        elif ttype == "age_group":
            target = age_groups_map
        if target is None:
            continue
        entry = target.get(value)
        if not entry:
            entry = {"value": value, "count": 0, "source": "manual", "id": row.id}
            target[value] = entry
        else:
            entry["source"] = "manual"
            entry["id"] = row.id

    base_age_groups = ["child", "teen", "adult", "elderly"]
    for value in base_age_groups:
        if value not in age_groups_map:
            age_groups_map[value] = {
                "value": value,
                "count": 0,
                "source": "system",
                "id": None
            }

    def _to_list(items: Dict[str, Dict[str, Any]], ttype: str) -> List[Dict[str, Any]]:
        def _sort_key(item: Dict[str, Any]):
            return (-int(item.get("count") or 0), str(item.get("value") or ""))
        out = list(items.values())
        out.sort(key=_sort_key)
        for item in out:
            item["type"] = ttype
        return out

    return {
        "categories": _to_list(categories_map, "category"),
        "topics": _to_list(topics_map, "topic"),
        "age_groups": _to_list(age_groups_map, "age_group")
    }


@router.post("/taxonomy")
async def add_taxonomy(
    taxonomy_type: str = Form(...),
    value: str = Form(...),
    current_admin=Depends(get_kb_admin),
):
    """Add a global taxonomy entry (category/topic/age_group)."""
    await _ensure_taxonomy_table()
    ttype = (taxonomy_type or "").strip().lower()
    val = (value or "").strip()
    if ttype not in {"category", "topic", "age_group"}:
        raise HTTPException(status_code=400, detail="Invalid taxonomy_type")
    if ttype == "age_group":
        allowed = {"child", "teen", "adult", "elderly"}
        if val.lower() not in allowed:
            raise HTTPException(status_code=400, detail="Age group must be child, teen, adult, or elderly")
    if not val:
        raise HTTPException(status_code=400, detail="Value is required")
    if _is_garbled_taxonomy_value(val):
        raise HTTPException(status_code=400, detail="Value looks garbled; please check encoding")

    from sqlalchemy import text
    from src.database.connection import get_async_db

    sql = text("""
        INSERT INTO knowledge_taxonomy (taxonomy_type, value, created_by)
        SELECT CAST(:ttype AS VARCHAR), CAST(:value AS TEXT), :created_by
        WHERE NOT EXISTS (
            SELECT 1 FROM knowledge_taxonomy
            WHERE taxonomy_type = CAST(:ttype AS VARCHAR)
              AND LOWER(value) = LOWER(CAST(:value AS TEXT))
        )
    """)
    async for session in get_async_db():
        await session.execute(sql, {
            "ttype": ttype,
            "value": val,
            "created_by": getattr(current_admin, "id", None)
        })
        await session.commit()

    return {"ok": True, "taxonomy_type": ttype, "value": val}


@router.patch("/taxonomy/{tax_id}")
async def update_taxonomy(
    tax_id: int,
    value: str = Form(...),
    current_admin=Depends(get_kb_admin),
):
    """Update a taxonomy entry's value."""
    await _ensure_taxonomy_table()
    val = (value or "").strip()
    if not val:
        raise HTTPException(status_code=400, detail="Value is required")

    from sqlalchemy import text
    from src.database.connection import get_async_db

    check_sql = text("""
        SELECT taxonomy_type FROM knowledge_taxonomy
        WHERE id = :tax_id AND is_active = TRUE
    """)
    update_sql = text("""
        UPDATE knowledge_taxonomy
        SET value = CAST(:value AS TEXT), updated_at = NOW()
        WHERE id = :tax_id AND is_active = TRUE
    """)
    async for session in get_async_db():
        row = (await session.execute(check_sql, {"tax_id": tax_id})).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        ttype = row.taxonomy_type
        if str(ttype).lower() == "age_group":
            raise HTTPException(status_code=403, detail="Age groups are system-defined")
        dup_sql = text("""
            SELECT 1 FROM knowledge_taxonomy
            WHERE taxonomy_type = :ttype
              AND LOWER(value) = LOWER(CAST(:value AS TEXT))
              AND id <> :tax_id
              AND is_active = TRUE
        """)
        dup = (await session.execute(dup_sql, {"ttype": ttype, "value": val, "tax_id": tax_id})).fetchone()
        if dup:
            raise HTTPException(status_code=409, detail="Value already exists")
        await session.execute(update_sql, {"tax_id": tax_id, "value": val})
        await session.commit()

    return {"ok": True, "id": tax_id, "value": val}


@router.delete("/taxonomy/{tax_id}")
async def delete_taxonomy(
    tax_id: int,
    current_admin=Depends(get_kb_admin),
):
    """Soft delete a taxonomy entry."""
    await _ensure_taxonomy_table()
    from sqlalchemy import text
    from src.database.connection import get_async_db

    check_sql = text("""
        SELECT taxonomy_type FROM knowledge_taxonomy
        WHERE id = :tax_id AND is_active = TRUE
    """)
    sql = text("""
        UPDATE knowledge_taxonomy
        SET is_active = FALSE, updated_at = NOW()
        WHERE id = :tax_id AND is_active = TRUE
    """)
    async for session in get_async_db():
        row = (await session.execute(check_sql, {"tax_id": tax_id})).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        if str(row.taxonomy_type).lower() == "age_group":
            raise HTTPException(status_code=403, detail="Age groups are system-defined")
        result = await session.execute(sql, {"tax_id": tax_id})
        await session.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True}


@router.get("/documents")
async def list_documents(
    status: Optional[str] = Query(None),
    visibility: Optional[str] = Query(None),
    org_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_admin=Depends(get_kb_admin),
):
    """List knowledge documents (basic view)."""
    filters = []
    params = {"limit": limit, "offset": offset}
    
    # Map status to processing_status for uploaded_documents table
    if status:
        status_map = {
            "indexed": "processed",
            "processing": "processing",
            "error": "failed",
            "pending": "uploaded"
        }
        processing_status = status_map.get(status, status)
        filters.append("processing_status = :status")
        params["status"] = processing_status
    
    # Map visibility to access_level for uploaded_documents table
    if visibility:
        access_level_map = {
            "public": "public",
            "org": "internal",
            "private": "restricted"
        }
        access_level = access_level_map.get(visibility, visibility)
        filters.append("access_level = :visibility")
        params["visibility"] = access_level
    
    org_scope = org_id or current_admin.organization_id
    # Note: uploaded_documents doesn't have organization_id, using uploaded_by instead
    # For now, show all active documents
    filters.append("is_active = TRUE")

    where_clause = " AND ".join(filters) if filters else "TRUE"
    from sqlalchemy import text
    from src.database.connection import get_async_db

    async for session in get_async_db():
        result = await session.execute(
            text(
                f"""
                SELECT id, title, category, language, access_level as visibility, 
                       processing_status as status,
                       0 as chunk_count, uploaded_by as organization_id, 
                       created_at, processing_completed_at as indexed_at,
                       processing_error as error_message,
                       file_size, original_filename
                FROM uploaded_documents
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        )
        rows = result.fetchall()
        return [dict(row._mapping) for row in rows]


@router.get("/{doc_id}/status")
async def get_document_status(doc_id: int, current_admin=Depends(get_kb_admin)):
    from sqlalchemy import text
    from src.database.connection import get_async_db

    async for session in get_async_db():
        result = await session.execute(
            text(
                """
                SELECT id, processing_status as status, 0 as chunk_count, 
                       processing_error as error_message, 
                       processing_completed_at as indexed_at
                FROM uploaded_documents
                WHERE id = :doc_id AND is_active = TRUE
                """
            ),
            {"doc_id": doc_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return dict(row._mapping)

@router.get("/{doc_id}")
async def get_document(doc_id: int, current_admin=Depends(get_kb_admin)):
    from sqlalchemy import text
    from src.database.connection import get_async_db

    async for session in get_async_db():
        result = await session.execute(
            text(
                """
                SELECT id, title, extracted_text as content, category, language, 
                       access_level as visibility,
                       uploaded_by as organization_id, processing_status as status, 
                       0 as chunk_count, processing_completed_at as indexed_at,
                       file_size, original_filename
                FROM uploaded_documents
                WHERE id = :doc_id AND is_active = TRUE
                """
            ),
            {"doc_id": doc_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        return dict(row._mapping)


@router.delete("/{doc_id}")
async def delete_document(doc_id: int, current_admin=Depends(get_kb_admin)):
    ingestion = get_ingestion_service()
    ok = await ingestion.delete_document(doc_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete")
    return {"success": True}


@router.post("/{doc_id}/reindex")
async def reindex_document(
    doc_id: int,
    auto_tag: bool = Form(True),
    auto_summary: bool = Form(True),
    category: Optional[str] = Form(None),
    language: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    topics: Optional[str] = Form(None),
    age_groups: Optional[str] = Form(None),
    current_admin=Depends(get_kb_admin),
):
    """Reindex an existing document with optional auto-tag/summary."""
    ingestion = get_ingestion_service()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    topic_list = [t.strip() for t in topics.split(",")] if topics else None
    age_list = [a.strip() for a in age_groups.split(",")] if age_groups else None

    result = await ingestion.reindex_document(
        document_id=doc_id,
        category=category,
        language=language,
        tags=tag_list,
        topics=topic_list,
        age_groups=age_list,
        auto_tag=auto_tag,
        auto_summary=auto_summary,
    )

    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.error or "Reindex failed")

    return {
        "document_id": result.document_id,
        "status": result.status,
        "error": result.error,
        "chunk_count": result.chunk_count,
    }


@router.get("/debug/db")
async def debug_db_snapshot(
    limit_docs: int = Query(20, ge=1, le=200),
    limit_chunks: int = Query(50, ge=1, le=500),
    org_id: Optional[int] = Query(None),
    doc_id: Optional[int] = Query(None),
    current_admin=Depends(get_kb_admin),
):
    """Dev snapshot of knowledge tables for sandbox UI."""
    from sqlalchemy import text
    from src.database.connection import get_async_db

    org_scope = org_id or current_admin.organization_id
    # Query uploaded_documents table (the actual table where documents are stored)
    docs_sql = """
        SELECT id, title, category, language, 
               access_level as visibility, 
               processing_status as status,
               0 as chunk_count,
               uploaded_by as organization_id, 
               created_at, 
               updated_at as indexed_at,
               processing_error as error_message
        FROM uploaded_documents
        WHERE (uploaded_by = :org_id OR access_level = 'public')
        AND is_active = TRUE
        ORDER BY created_at DESC
        LIMIT :limit_docs
    """
    # Note: document_chunks table doesn't exist - chunks are stored in vector store only
    # Return documents and get chunk info from vector store instead
    
    async for session in get_async_db():
        docs_result = await session.execute(
            text(docs_sql),
            {"org_id": org_scope, "limit_docs": limit_docs},
        )
        
        documents = [dict(row._mapping) for row in docs_result.fetchall()]
        
        # Get chunks from vector store for the documents
        chunks_data = []
        try:
            vector_store = get_vector_store()
            
            # If specific doc_id requested, filter by it
            if doc_id:
                filter_dict = {"document_id": doc_id}
            else:
                # Get chunks for all returned documents
                doc_ids = [doc['id'] for doc in documents[:limit_chunks]]
                if doc_ids:
                    # Get chunks from vector store (limited)
                    for doc_id_item in doc_ids[:min(len(doc_ids), limit_chunks)]:
                        try:
                            results = vector_store.collection.get(
                                where={"document_id": doc_id_item},
                                limit=5,  # Limit chunks per document
                                include=['metadatas', 'documents']
                            )
                            for i, chunk_id in enumerate(results['ids']):
                                metadata = results['metadatas'][i]
                                content = results['documents'][i]
                                chunks_data.append({
                                    "id": chunk_id,
                                    "document_id": metadata.get('document_id'),
                                    "title": metadata.get('title', 'N/A'),
                                    "snippet": content[:220] if content else "",
                                    "chunk_index": metadata.get('chunk_index'),
                                    "source_type": metadata.get('source_type', 'N/A'),
                                    "language": metadata.get('language', 'N/A'),
                                })
                        except Exception as e:
                            logger.warning(f"Could not fetch chunks for doc {doc_id_item}: {e}")
                            continue
        except Exception as e:
            logger.error(f"Error fetching chunks from vector store: {e}")
            chunks_data = []
        
        return {
            "documents": documents,
            "chunks": chunks_data[:limit_chunks],
        }



@router.get("/categories/tree")
async def get_category_tree(
    current_admin=Depends(get_kb_admin),
):
    """
    Get the full category tree with document counts.
    
    Returns hierarchical category structure for KB navigation.
    """
    from src.knowledge_base.category_service import get_category_service
    from src.database.connection import get_async_db
    from sqlalchemy import text
    import traceback
    
    try:
        category_service = get_category_service()
        
        async for db in get_async_db():
            # Get the full tree
            tree = await category_service.get_category_tree(db, parent_id=None, max_depth=3)
            
            # Add document counts for each category
            async def add_doc_counts(categories):
                for cat in categories:
                    # Count documents tagged with this category
                    # Use document_category_tags table and check document is active
                    result = await db.execute(
                        text("""
                            SELECT COUNT(DISTINCT dct.document_id) as count
                            FROM document_category_tags dct
                            JOIN uploaded_documents ud ON dct.document_id = ud.id
                            WHERE dct.category_id = :category_id
                              AND ud.is_active = TRUE
                        """),
                        {"category_id": cat["id"]}
                    )
                    row = result.fetchone()
                    direct_count = row.count if row else 0
                    
                    # Store direct count separately
                    cat["direct_document_count"] = direct_count
                    
                    # Recursively add counts for children and sum them
                    child_count = 0
                    if cat.get("children"):
                        await add_doc_counts(cat["children"])
                        # Sum up all children's document counts
                        child_count = sum(child.get("document_count", 0) for child in cat["children"])
                    
                    # Total count = direct documents + all descendant documents
                    cat["document_count"] = direct_count + child_count
            
            await add_doc_counts(tree)
            return tree
            
    except Exception as e:
        logger.error(f"Failed to load category tree: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to load category tree: {str(e)}")


@router.post("/categories")
async def create_category(
    name_zh: str = Form(...),
    name_en: str = Form(...),
    parent_id: int = Form(...),
    level: int = Form(...),
    icon: str = Form("📁"),
    description_zh: Optional[str] = Form(None),
    description_en: Optional[str] = Form(None),
    current_admin=Depends(get_kb_admin),
):
    """
    Create a new category.
    
    Args:
        name_zh: Chinese name
        name_en: English name
        parent_id: Parent category ID
        level: Level in hierarchy (1=age group, 2=category, 3=topic)
        icon: Icon emoji
        description_zh: Chinese description (optional)
        description_en: English description (optional)
    """
    from sqlalchemy import text
    from src.database.connection import get_async_db
    from src.knowledge_base.category_service import get_category_service
    import re
    
    try:
        # Generate slug from name
        slug = re.sub(r'[^\w\s-]', '', name_en.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        
        # Get display order (max + 1)
        async for db in get_async_db():
            result = await db.execute(
                text("""
                    SELECT COALESCE(MAX(display_order), 0) + 1 as next_order
                    FROM kb_categories
                    WHERE parent_id = :parent_id
                """),
                {"parent_id": parent_id}
            )
            display_order = result.fetchone()[0]
            
            # Insert category
            result = await db.execute(
                text("""
                    INSERT INTO kb_categories 
                    (name_en, name_zh, slug, icon, description_en, description_zh, level, display_order, parent_id)
                    VALUES (:name_en, :name_zh, :slug, :icon, :description_en, :description_zh, :level, :display_order, :parent_id)
                    RETURNING id
                """),
                {
                    "name_en": name_en,
                    "name_zh": name_zh,
                    "slug": slug,
                    "icon": icon,
                    "description_en": description_en,
                    "description_zh": description_zh,
                    "level": level,
                    "display_order": display_order,
                    "parent_id": parent_id
                }
            )
            await db.commit()
            
            category_id = result.fetchone()[0]
            
            # Clear category cache so tree refreshes immediately
            category_service = get_category_service()
            category_service._cache.clear()
            logger.info(f"Category cache cleared after creating category {category_id}")
            
            return {"id": category_id, "name_zh": name_zh, "name_en": name_en, "slug": slug}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create category: {str(e)}")


@router.delete("/categories/{category_id}")
async def delete_category(
    category_id: int,
    current_admin=Depends(get_kb_admin),
):
    """
    Delete a category or topic.
    
    Only Level 2 (categories) and Level 3 (topics) can be deleted.
    Level 1 (age groups) are system-defined and cannot be deleted.
    
    Args:
        category_id: ID of the category to delete
    """
    from sqlalchemy import text
    from src.database.connection import get_async_db
    from src.knowledge_base.category_service import get_category_service
    
    try:
        async for db in get_async_db():
            # Check if category exists and get its level
            result = await db.execute(
                text("""
                    SELECT id, level, name_zh, name_en
                    FROM kb_categories
                    WHERE id = :category_id
                """),
                {"category_id": category_id}
            )
            category = result.fetchone()
            
            if not category:
                raise HTTPException(status_code=404, detail="Category not found")
            
            # Prevent deletion of age groups (level 1)
            if category.level == 1:
                raise HTTPException(
                    status_code=403, 
                    detail="Cannot delete age groups (Level 1). Only categories and topics can be deleted."
                )
            
            # Check if category has children
            result = await db.execute(
                text("""
                    SELECT COUNT(*) as child_count
                    FROM kb_categories
                    WHERE parent_id = :category_id
                """),
                {"category_id": category_id}
            )
            child_count = result.fetchone()[0]
            
            if child_count > 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete category with {child_count} sub-categories. Delete children first."
                )
            
            # Delete document associations first
            await db.execute(
                text("""
                    DELETE FROM document_category_tags
                    WHERE category_id = :category_id
                """),
                {"category_id": category_id}
            )
            
            # Delete the category
            await db.execute(
                text("""
                    DELETE FROM kb_categories
                    WHERE id = :category_id
                """),
                {"category_id": category_id}
            )
            
            await db.commit()
            
            # Clear category cache so tree refreshes immediately
            category_service = get_category_service()
            category_service._cache.clear()
            logger.info(f"Category cache cleared after deleting category {category_id}")
            
            return {
                "success": True,
                "message": f"Category '{category.name_zh}' deleted successfully",
                "deleted_id": category_id
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete category {category_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to delete category: {str(e)}")


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: int,
    current_admin=Depends(get_kb_admin),
):
    """
    Download the original document file.
    
    Args:
        doc_id: Document ID to download
    """
    from fastapi.responses import FileResponse
    from sqlalchemy import text
    from src.database.connection import get_async_db
    import os
    
    try:
        # Get document info from uploaded_documents table
        async for db in get_async_db():
            result = await db.execute(
                text("""
                    SELECT id, title, file_path, original_filename, mime_type
                    FROM uploaded_documents
                    WHERE id = :doc_id AND is_active = TRUE
                """),
                {"doc_id": doc_id}
            )
            doc = result.fetchone()
            
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found")
            
            file_path = doc.file_path
            if not file_path or not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Document file not found on disk")
            
            # Return file for download
            filename = doc.original_filename or f"document_{doc_id}.pdf"
            return FileResponse(
                path=file_path,
                filename=filename,
                media_type=doc.mime_type or "application/octet-stream"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download document {doc_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to download document: {str(e)}")


@router.get("/categories/{category_id}/documents")
async def get_category_documents(
    category_id: int,
    current_admin=Depends(get_kb_admin),
):
    """
    Get all documents tagged with a specific category.
    
    Args:
        category_id: Category ID to filter documents
    """
    from sqlalchemy import text
    from src.database.connection import get_async_db
    
    try:
        async for db in get_async_db():
            result = await db.execute(
                text("""
                    SELECT DISTINCT ud.id, ud.title, ud.original_filename, 
                           ud.created_at, ud.file_size
                    FROM uploaded_documents ud
                    JOIN document_category_tags dct ON ud.id = dct.document_id
                    WHERE dct.category_id = :category_id
                      AND ud.is_active = TRUE
                    ORDER BY ud.created_at DESC
                """),
                {"category_id": category_id}
            )
            docs = result.fetchall()
            
            return [
                {
                    "id": doc.id,
                    "title": doc.title,
                    "filename": doc.original_filename,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "file_size": doc.file_size
                }
                for doc in docs
            ]
            
    except Exception as e:
        logger.error(f"Failed to get documents for category {category_id}: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to get category documents: {str(e)}")
