# ⚠️ IMPORTANT: Document Chunking Issue

## Current Situation

Your documents in the KB admin panel show `chunks=0` because they haven't been properly chunked yet. Here's what's happening:

### The Problem

1. **Documents are uploaded** to `uploaded_documents` table ✅
2. **Documents show as `[processed]`** but have `chunks=0` ❌
3. **KB Sandbox shows error** because it's looking at `knowledge_documents` table which is empty ❌

### Why This Happened

The documents were uploaded but the chunking step wasn't completed. This can happen if:
- The document ingestion service didn't finish processing
- The chunking step failed silently
- The vector store wasn't properly initialized

## Solution: Re-chunk Your Documents

Follow these steps to fix the issue:

### Step 1: Enable Semantic Chunking

Edit your `.env` file:
```bash
AI_SEMANTIC_CHUNKING_ENABLED=true
```

### Step 2: Test the Setup

```bash
cd healthcare_ai_live2d_unified
python scripts/test_rechunking.py
```

This will verify:
- Database connection ✓
- Vector store connection ✓
- Semantic chunker initialization ✓
- Sample document processing ✓

### Step 3: Re-chunk Your Documents

**Option A: Dry Run First (Recommended)**
```bash
python scripts/rechunk_documents.py --all --dry-run
```

**Option B: Re-chunk All Documents**
```bash
python scripts/rechunk_documents.py --all
```

**Option C: Re-chunk by Category**
```bash
# Example categories from your KB:
python scripts/rechunk_documents.py --category "長者醫療券計劃"
python scripts/rechunk_documents.py --category "綜援"
python scripts/rechunk_documents.py --category "醫療費用減免"
```

### Step 4: Verify the Results

After re-chunking, check:

1. **In the admin panel**: Documents should show `chunks > 0`
2. **In the database**:
   ```sql
   SELECT id, title, category, 
          (SELECT COUNT(*) FROM document_chunks WHERE document_id = ud.id) as chunk_count
   FROM uploaded_documents ud
   WHERE is_active = TRUE
   ORDER BY id;
   ```

3. **In the vector store**: Chunks should be searchable

## What the Re-chunking Does

For each document, the script will:

1. **Delete old chunks** from the vector store (if any)
2. **Re-chunk with AI** using semantic boundaries:
   - Detects natural topic transitions
   - Adapts chunk size based on complexity (200-1200 chars)
   - Generates AI summaries (max 150 chars)
   - Generates keywords (3-7 per chunk)
   - Identifies topics and structure types
3. **Store new chunks** in the vector store with metadata
4. **Update document status** to show chunk count

## Expected Results

After successful re-chunking:

- ✅ Documents show `chunks > 0` in admin panel
- ✅ KB Sandbox works without errors
- ✅ Search and retrieval work properly
- ✅ Each chunk has AI-generated metadata

## Troubleshooting

### Error: "No documents found to re-chunk"

**Check your documents:**
```sql
SELECT id, title, category, processing_status, 
       LENGTH(extracted_text) as content_length,
       is_active
FROM uploaded_documents
WHERE is_active = TRUE
ORDER BY id;
```

**Possible issues:**
- `is_active = FALSE` - Documents are inactive
- `extracted_text IS NULL` - No content extracted
- `processing_status != 'indexed'` - Documents not processed

**Fix:**
```sql
-- Activate documents
UPDATE uploaded_documents 
SET is_active = TRUE 
WHERE id IN (130, 131, 132, 133, 134, 135, 136, 128, 129);

-- Set processing status
UPDATE uploaded_documents 
SET processing_status = 'indexed' 
WHERE id IN (130, 131, 132, 133, 134, 135, 136, 128, 129)
AND extracted_text IS NOT NULL;
```

### Error: "AI service timeout"

The AI service is taking too long. This is normal for the first run.

**Solutions:**
- Wait and try again (AI service may be warming up)
- Process documents one category at a time
- Check your AI service credentials in `.env`

### Error: "Vector store connection failed"

**Check if ChromaDB is running:**
```bash
# If using Docker
docker-compose ps

# Check logs
docker-compose logs chroma
```

**Fix:**
```bash
# Restart services
docker-compose restart
```

## Quick Commands Reference

```bash
# Test setup
python scripts/test_rechunking.py

# Dry run (safe test)
python scripts/rechunk_documents.py --all --dry-run

# Re-chunk all
python scripts/rechunk_documents.py --all

# Re-chunk specific category
python scripts/rechunk_documents.py --category "長者醫療券計劃"

# Re-chunk specific documents
python scripts/rechunk_documents.py --document-ids 130,131,132

# Force re-chunk (even if already chunked)
python scripts/rechunk_documents.py --all --force
```

## Need Help?

1. Check the logs in `logs/` directory
2. Review `README_RECHUNKING.md` for detailed documentation
3. Run the test script to diagnose issues
4. Check the AI semantic chunking spec in `.kiro/specs/ai-semantic-chunking/`

---

**Next Step**: Run `python scripts/test_rechunking.py` to verify your setup! 🚀
