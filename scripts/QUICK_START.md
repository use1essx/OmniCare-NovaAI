# 🚀 Quick Start: Fix Document Chunking

## Problem
Your documents show `chunks=0` and KB Sandbox shows errors.

## Solution (3 Simple Steps)

### Step 1: Enable Semantic Chunking ✅ DONE!

Your `.env` file has been updated with:
```bash
AI_SEMANTIC_CHUNKING_ENABLED=true
```

### Step 2: Run the Fix Script

**Option A: Automatic (Recommended)**
```bash
# Windows
cd healthcare_ai_live2d_unified
scripts\fix_chunking.bat

# Linux/Mac
cd healthcare_ai_live2d_unified
bash scripts/fix_chunking.sh
```

**Option B: Manual Steps**

```bash
# 1. Test setup
python scripts/test_rechunking.py

# 2. Dry run (safe test)
python scripts/rechunk_documents.py --all --dry-run

# 3. Actual re-chunking
python scripts/rechunk_documents.py --all
```

### Step 3: Verify Results

1. **Check Admin Panel**: Documents should show `chunks > 0`
2. **Test KB Sandbox**: Should work without errors
3. **Try Search**: Search for documents in chat

## What Happens During Re-chunking?

For each document:
1. ✅ Deletes old chunks (if any)
2. ✅ Re-chunks with AI semantic analysis
3. ✅ Generates summaries (Chinese, 150 chars max)
4. ✅ Generates keywords (3-7 per chunk)
5. ✅ Identifies topics and complexity
6. ✅ Stores chunks in vector store

## Expected Time

- **Per document**: 5-10 seconds
- **9 documents**: ~1-2 minutes total

## Troubleshooting

### "Python was not found"
**Solution**: Activate your Python environment first
```bash
# If using venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# If using conda
conda activate healthcare_ai
```

### "No documents found"
**Solution**: Run the SQL script to activate documents
```bash
# Connect to your database and run:
psql -d healthcare_ai_v2 -f scripts/prepare_documents_for_rechunking.sql
```

### "AI service timeout"
**Solution**: This is normal for first run. Just wait and try again.

### "Vector store connection failed"
**Solution**: Make sure Docker containers are running
```bash
docker-compose ps
docker-compose up -d
```

## Need Help?

1. Check `scripts/IMPORTANT_README.md` for detailed guide
2. Check `scripts/README_RECHUNKING.md` for full documentation
3. Run `python scripts/test_rechunking.py` to diagnose issues

---

**Ready?** Run the fix script now! 🚀

```bash
# Windows
scripts\fix_chunking.bat

# Linux/Mac  
bash scripts/fix_chunking.sh
```
