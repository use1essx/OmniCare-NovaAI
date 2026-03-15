#!/usr/bin/env python3
"""
Healthcare AI V2 - Seed Form Documents
Automatically loads Hong Kong elderly welfare forms as default knowledge base data
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text

from src.database.connection import init_database, get_async_session_context
from src.database.models_knowledge_base import KnowledgeDocument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Form metadata mapping - categorizes each form type
FORM_CATEGORIES = {
    "樂悠咭": {
        "form_type": "application",
        "submission_instructions": "Submit to Social Welfare Department or designated service centers",
        "category": "elderly_discount",
        "tags": ["elderly", "discount", "card", "application"]
    },
    "綜援": {
        "form_type": "application",
        "submission_instructions": "Submit to Social Security Field Unit",
        "category": "financial_assistance",
        "tags": ["elderly", "financial", "assistance", "welfare"]
    },
    "醫療費用減免": {
        "form_type": "application",
        "submission_instructions": "Submit to Hospital Authority or designated clinics",
        "category": "healthcare",
        "tags": ["elderly", "medical", "fee", "waiver"]
    },
    "長者牙科服務資助": {
        "form_type": "application",
        "submission_instructions": "Submit to participating dental clinics",
        "category": "healthcare",
        "tags": ["elderly", "dental", "subsidy"]
    },
    "長者社區照顧服務券計劃": {
        "form_type": "application",
        "submission_instructions": "Submit to Social Welfare Department",
        "category": "community_care",
        "tags": ["elderly", "community", "care", "voucher"]
    },
    "長者醫療券計劃": {
        "form_type": "registration",
        "submission_instructions": "Register at participating healthcare providers",
        "category": "healthcare",
        "tags": ["elderly", "medical", "voucher"]
    },
    "長者院舍照顧服務券計劃": {
        "form_type": "application",
        "submission_instructions": "Submit to Social Welfare Department",
        "category": "residential_care",
        "tags": ["elderly", "residential", "care", "voucher"]
    },
    "高齡津貼、傷殘津貼及長者生活津貼": {
        "form_type": "application",
        "submission_instructions": "Submit to Social Welfare Department",
        "category": "financial_assistance",
        "tags": ["elderly", "allowance", "subsidy"]
    }
}


async def _create_knowledge_document_record(
    db,
    title: str,
    filename: str,
    file_path: str,
    file_size: int,
    category: str,
    language: str,
    tags: list,
    metadata: Dict,
    total_characters: int
) -> Optional[int]:
    """
    Create document record in knowledge_documents table.
    
    This bypasses DocumentIngestionService which targets uploaded_documents.
    Forms must be in knowledge_documents table due to FK constraint from form_deliveries.
    
    Args:
        db: Database session
        title: Document title
        filename: Original filename
        file_path: Path to file
        file_size: File size in bytes
        category: Document category
        language: Language code (e.g., 'zh-HK')
        tags: List of tags
        metadata: Document metadata dict
        total_characters: Total character count
        
    Returns:
        Document ID if successful, None otherwise
        
    PRIVACY: No PII in logs - only document IDs
    """
    try:
        # VALIDATION: Insert into knowledge_documents table
        sql = text("""
            INSERT INTO knowledge_documents (
                title, filename, file_path, file_size, file_type,
                category, language, tags, status, doc_metadata,
                total_characters, uploaded_by, upload_date
            ) VALUES (
                :title, :filename, :file_path, :file_size, :file_type,
                :category, :language, :tags, :status, :metadata,
                :total_characters, :uploaded_by, NOW()
            )
            RETURNING id
        """)
        
        # VALIDATION: Serialize metadata to JSON
        metadata_json = json.dumps(metadata)
        
        result = await db.execute(sql, {
            "title": title,
            "filename": filename,
            "file_path": file_path,
            "file_size": file_size,
            "file_type": "pdf",
            "category": category,
            "language": language,
            "tags": tags,
            "status": "approved",  # Forms are pre-approved
            "metadata": metadata_json,
            "total_characters": total_characters,
            "uploaded_by": 1  # System user
        })
        await db.commit()
        
        row = result.fetchone()
        doc_id = row[0] if row else None
        
        # PRIVACY: Log only document ID, not content
        if doc_id:
            logger.info(f"Created knowledge_documents record with ID: {doc_id}")
        
        return doc_id
        
    except Exception as e:
        logger.error(f"Error creating knowledge_documents record: {e}")
        await db.rollback()
        return None


def get_form_metadata(folder_name: str, filename: str) -> Dict:
    """
    Get form metadata based on folder name and filename.
    
    Only actual application forms are marked as forms.
    Other documents (FAQs, guidelines, lists) are informational only.
    
    Args:
        folder_name: Name of the folder containing the form
        filename: Name of the file
        
    Returns:
        Dictionary with form metadata (is_form will be True only for actual forms)
    """
    # PRIVACY: No PII in logs
    logger.debug(f"Getting metadata for: {folder_name}/{filename}")
    
    # ONLY these 2 files are actual forms to fill out
    ACTUAL_FORMS = {
        "樂悠咭_申請表格.pdf": {
            "is_form": True,
            "form_type": "application",
            "submission_instructions": "Submit to Social Welfare Department or designated service centers",
            "category": "elderly_discount",
            "tags": ["elderly", "discount", "card", "application", "form"]
        },
        "綜援_申請綜合社會保障援助登記表格.pdf": {
            "is_form": True,
            "form_type": "application",
            "submission_instructions": "Submit to Social Security Field Unit",
            "category": "financial_assistance",
            "tags": ["elderly", "financial", "assistance", "welfare", "form"]
        }
    }
    
    # Check if this is an actual form
    if filename in ACTUAL_FORMS:
        return ACTUAL_FORMS[filename]
    
    # Otherwise, it's informational content (not a form)
    # Match folder name to category for informational docs
    for form_name, metadata in FORM_CATEGORIES.items():
        if form_name in folder_name:
            return {
                "is_form": False,  # Not an actual form
                "form_type": None,
                "submission_instructions": None,
                "category": metadata["category"],
                "tags": metadata["tags"]
            }
    
    # Default for unknown documents
    return {
        "is_form": False,
        "form_type": None,
        "submission_instructions": None,
        "category": "general",
        "tags": ["elderly", "information"]
    }


async def seed_form_documents():
    """Seed form documents from preset data directory"""
    logger.info("Starting form documents seeding...")
    
    # Initialize database
    await init_database()
    
    # Find form documents directory
    # Try multiple locations: Docker image data, local development, parent directory
    project_root = Path(__file__).parent.parent
    possible_dirs = [
        project_root / "data" / "kb_seed_docs",  # Docker image location
        project_root.parent / "fyp_長者",         # Local development
    ]
    
    forms_dir = None
    for dir_path in possible_dirs:
        if dir_path.exists():
            forms_dir = dir_path
            break
    
    if not forms_dir:
        logger.error(f"Forms directory not found in any of: {possible_dirs}")
        return 0, 0
    
    logger.info(f"Scanning forms directory: {forms_dir}")
    
    async with get_async_session_context() as db:
        created_count = 0
        skipped_count = 0
        
        # Scan all subdirectories for PDF files
        for category_dir in forms_dir.iterdir():
            if not category_dir.is_dir():
                continue
            
            category_name = category_dir.name
            logger.info(f"Processing category: {category_name}")
            
            # Process all PDF files in this category
            for pdf_file in category_dir.glob("*.pdf"):
                filename = pdf_file.name
                
                # Get metadata for this specific file
                form_metadata = get_form_metadata(category_name, filename)
                
                # PRIVACY: Log only filename, not content
                logger.info(f"  Checking: {filename}")
                
                # VALIDATION: Check if document already exists (idempotency)
                # Check by both filename AND category to avoid false positives
                result = await db.execute(
                    select(KnowledgeDocument).where(
                        KnowledgeDocument.filename == filename,
                        KnowledgeDocument.category == form_metadata["category"]
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.info(f"  ✓ Already exists: {filename} (ID: {existing.id})")
                    skipped_count += 1
                    continue
                
                try:
                    # Read file content
                    with open(pdf_file, 'rb') as f:
                        file_content = f.read()
                    
                    # Extract text from PDF
                    from src.knowledge_base.extractors import detect_and_extract
                    extracted_text, extraction_metadata = detect_and_extract(filename, file_content)
                    
                    if not extracted_text or len(extracted_text.strip()) < 50:
                        logger.warning(f"  ⚠️  Insufficient text extracted from: {filename}")
                        continue
                    
                    # VALIDATION: Prepare document metadata with form fields
                    doc_metadata = {
                        "is_form": form_metadata["is_form"],
                        "form_type": form_metadata["form_type"],
                        "submission_instructions": form_metadata["submission_instructions"],
                        "source": "seed_data",
                        "category_folder": category_name,
                        "filename": filename
                    }
                    
                    # BUGFIX: Create record in knowledge_documents table (not uploaded_documents)
                    # This fixes the FK constraint issue with form_deliveries table
                    document_id = await _create_knowledge_document_record(
                        db=db,
                        title=filename.replace('.pdf', '').replace('_', ' '),
                        filename=filename,
                        file_path=str(pdf_file),
                        file_size=len(file_content),
                        category=form_metadata["category"],
                        language='zh-HK',
                        tags=form_metadata["tags"],
                        metadata=doc_metadata,
                        total_characters=len(extracted_text)
                    )
                    
                    if not document_id:
                        logger.error(f"  ❌ Failed to create database record for: {filename}")
                        continue
                    
                    # BUGFIX: Use DocumentIngestionService ONLY for vector store operations
                    # This preserves the metadata propagation logic while using correct table
                    from src.knowledge_base.document_ingestion import DocumentIngestionService
                    
                    ingestion_service = DocumentIngestionService()
                    
                    # Chunk the document
                    chunks = ingestion_service._chunk_document(extracted_text)
                    
                    # VALIDATION: Store chunks in vector store with coordinated document_id
                    chunk_count = await ingestion_service._store_chunks(
                        document_id=document_id,  # Use ID from knowledge_documents
                        chunks=chunks,
                        category=form_metadata["category"],
                        language='zh-HK',
                        organization_id=None,  # System-wide
                        source_type='pdf',
                        title=filename.replace('.pdf', '').replace('_', ' '),
                        tags=form_metadata["tags"],
                        topics=[],
                        age_groups=[],
                        visibility='public',
                        doc_metadata=doc_metadata  # CRITICAL: Pass metadata for is_form propagation
                    )
                    
                    if chunk_count == 0:
                        logger.error(f"  ❌ Failed to store chunks for: {filename}")
                        # Rollback database record
                        await db.execute(
                            text("DELETE FROM knowledge_documents WHERE id = :doc_id"),
                            {"doc_id": document_id}
                        )
                        await db.commit()
                        continue
                    
                    # Update document with chunk count
                    await db.execute(
                        text("""
                            UPDATE knowledge_documents 
                            SET total_chunks = :chunk_count, updated_at = NOW()
                            WHERE id = :doc_id
                        """),
                        {"chunk_count": chunk_count, "doc_id": document_id}
                    )
                    await db.commit()
                    
                    created_count += 1
                    # AUDIT: Log successful creation in both database and vector store
                    logger.info(
                        f"  ✅ Created: {filename} "
                        f"(DB ID: {document_id}, chunks: {chunk_count}, "
                        f"is_form: {doc_metadata['is_form']})"
                    )
                    
                except Exception as e:
                    logger.error(f"  ❌ Error processing {filename}: {e}")
                    await db.rollback()
                    continue
        
        logger.info(f"Seeding complete: {created_count} created, {skipped_count} skipped")
        return created_count, skipped_count


async def main():
    """Main entry point"""
    try:
        created, skipped = await seed_form_documents()
        print(f"\n{'='*60}")
        print(f"✅ Form documents seeded successfully!")
        print(f"{'='*60}")
        print(f"   Created: {created}")
        print(f"   Skipped (already exist): {skipped}")
        print(f"{'='*60}")
        print(f"\n📋 Form Categories Loaded:")
        for form_name in FORM_CATEGORIES.keys():
            print(f"   • {form_name}")
        print(f"\n✅ Forms are now available in the Knowledge Base!")
        print(f"   Access them through the KB Sandbox or chat interface")
    except Exception as e:
        logger.error(f"Failed to seed form documents: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
