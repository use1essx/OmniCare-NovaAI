# 🚀 Quick Test Reference Card

## One-Liner Commands

```bash
# Run all backend tests (RECOMMENDED)
./run_backend_tests_only.sh

# Run with detailed output
pytest tests/test_api_comprehensive.py -v

# Run specific test category
pytest tests/test_api_comprehensive.py::TestHealthEndpoints -v

# Generate HTML report
pytest tests/ --html=report.html --self-contained-html

# Check if backend is running
curl http://localhost:8001/health
```

---

## Test Categories

| Command | What It Tests | Time |
|---------|---------------|------|
| `pytest tests/test_api_comprehensive.py::TestHealthEndpoints -v` | Health check | ~5s |
| `pytest tests/test_api_comprehensive.py::TestDetailedRecordingEndpoints -v` | Recording workflow | ~15s |
| `pytest tests/test_api_comprehensive.py::TestEmotionEndpoints -v` | Emotion detection | ~10s |
| `pytest tests/test_api_comprehensive.py::TestHealthcareSessionEndpoints -v` | Sessions & interventions | ~20s |
| `pytest tests/test_api_comprehensive.py::TestIntegrationScenarios -v` | Full workflows | ~10s |

---

## Expected Output (All Passing)

```
======================== 22 passed in 61.64s =========================

✅ All backend tests passed!

📊 Test Summary:
22 tests collected
```

---

## Test Status Indicators

| Symbol | Meaning |
|--------|---------|
| ✅ `PASSED` | Test succeeded |
| ❌ `FAILED` | Test failed |
| ⏭️ `SKIPPED` | Test skipped |
| ⚠️ `ERROR` | Test error |

---

## Quick Troubleshooting

### Backend Not Running?
```bash
docker-compose up -d
curl http://localhost:8001/health
```

### Tests Failing?
```bash
# Check logs
docker-compose logs app --tail=50

# Restart
docker-compose restart app

# Retry
pytest tests/test_api_comprehensive.py -v
```

### Need More Details?
```bash
# Show full error traces
pytest tests/ -v --tb=long

# Stop on first failure
pytest tests/ -x

# Show print statements
pytest tests/ -s
```

---

## Manual Testing Checklist

### 5-Minute Quick Test
1. Open http://localhost:8001/
2. Click "Start Camera" (grant permission)
3. Wait 10 seconds
4. Check console for logs
5. Click "Stop Camera"

**Expected:** ✅ No errors, recording auto-starts

### 10-Minute Full Test
1. Start camera
2. Switch through all 6 tabs
3. Trigger 2-3 interventions
4. Check Stats tab
5. Stop camera
6. Review console logs

**Expected:** ✅ All tabs work, data updates

---

## Test Results Interpretation

### All Green ✅
```
======================== 22 passed =========================
```
**Meaning:** Everything works perfectly!

### Some Red ❌
```
============ 2 failed, 20 passed ============
```
**Action:** Check which tests failed, review logs

### Import Errors
```
ModuleNotFoundError: No module named 'mediapipe'
```
**Fix:** `pip install mediapipe opencv-python-headless`

---

## Performance Benchmarks

| Metric | Expected | Your Result |
|--------|----------|-------------|
| Health Check | < 100ms | ✅ |
| Start Session | < 500ms | ✅ |
| Emotion Analysis | < 1s | ✅ |
| Full Test Suite | ~60s | ✅ |

---

## Common Test Patterns

### Test One Endpoint
```bash
pytest tests/ -k "test_health_check" -v
```

### Test By Keyword
```bash
pytest tests/ -k "session" -v  # All session tests
pytest tests/ -k "recording" -v  # All recording tests
```

### Test With Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

---

## Documentation Quick Links

- 📄 **TEST_REPORT.md** - Detailed test results
- 📘 **TESTING_GUIDE.md** - Complete testing guide
- ✅ **TESTING_COMPLETE.md** - Status summary
- 🎯 **This file** - Quick reference

---

## Support

### Tests Passing? ✅
**You're good to go!** Deploy with confidence.

### Tests Failing? ❌
1. Read error message
2. Check `docker-compose logs app`
3. Review `TEST_REPORT.md`
4. Consult `TESTING_GUIDE.md`

---

**Quick Test:** `./run_backend_tests_only.sh`  
**Full Test:** `./run_all_tests.sh`  
**Help:** Read `TESTING_GUIDE.md`

---

*Keep this card handy for quick testing!* 📋✨

