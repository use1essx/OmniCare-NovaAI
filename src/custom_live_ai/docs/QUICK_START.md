# 🚀 Quick Start Guide - Custom Live AI

## ⚠️ IMPORTANT: Correct URL

**Access the application at:**
```
http://localhost:8001/
```

**NOT:** `http://localhost:8001/detailed` ❌ (This will give 404 error)

---

## 📋 Prerequisites

- Docker and Docker Compose installed
- Webcam (for camera-based tracking)
- At least 4GB RAM available
- Modern web browser (Chrome, Firefox, Edge)

---

## 🎯 Starting the Application

### 1. Navigate to Project Directory
```bash
cd custom_live_ai
```

### 2. Start Docker Containers
```bash
./start_docker.sh
```

Or manually:
```bash
docker-compose up -d
```

### 3. Wait for Services to Start (~30 seconds)
```bash
# Check if services are healthy
docker-compose ps
```

You should see:
- `app` - running (port 8001)
- `db` - running (port 5432)  
- `pgadmin` - running (port 5050)

### 4. Open Web Browser
Navigate to: **http://localhost:8001/**

---

## 🎥 Using the Interface

### Camera Setup
1. Click **"Start Camera"** button
2. Grant webcam permission when prompted
3. Camera will auto-start:
   - ✅ Recording
   - ✅ AI session tracking
   - ✅ Emotion detection

### Console System
Three console tabs for monitoring:
- **All Events** - Everything (info, success, warnings, errors)
- **Errors Only** - Just errors and warnings
- **API Calls** - HTTP requests/responses

### Control Tabs
- **📹 Recording** - Camera and recording controls
- **🤖 Session** - AI session management
- **😊 Emotion** - Emotion tracking and testing
- **💪 Posture** - Body part detection toggles
- **⚡ Interventions** - Manual triggers and history
- **📊 Stats** - Real-time metrics

---

## 🧪 Running Tests

```bash
# Full test suite
pytest tests/ -v

# UI comprehensive tests only
pytest tests/test_ui_comprehensive.py -v

# With coverage report
pytest tests/ --cov=src --cov-report=html
```

---

## 🛑 Stopping the Application

```bash
docker-compose down
```

Or to also remove volumes:
```bash
docker-compose down -v
```

---

## 🔍 Troubleshooting

### Camera Not Starting
- **Error:** "Requested device not found"
- **Fix:** Check webcam is connected and not in use by another app

### 404 Error
- **Error:** Page shows `{"detail":"Not Found"}`
- **Fix:** Make sure you're using `http://localhost:8001/` (with trailing slash) not `/detailed`

### 422 Errors in Console
- **Expected Behavior:** You may see 1-2 "Waiting for face detection" messages
- **This is normal** - Face detection takes a few seconds to initialize
- **If constant 422 errors:** Face not detected, adjust lighting or camera angle

### Console Jumping/Scrolling
- **Fixed in latest version** - Console now uses smooth scrolling
- If issues persist, clear browser cache

### Memory/Performance Issues
- Console is limited to 50 lines per tab
- Duplicate messages are throttled
- Data updates every 5 seconds (not 2)

---

## 📊 Performance Expectations

| Metric | Expected Value |
|--------|---------------|
| FPS | 30-60 (depends on hardware) |
| Face Detection | 1-3 seconds initial |
| Emotion Updates | Every 500ms |
| Data Stream | Every 5 seconds |
| Console Lines | Max 50 per tab |

---

## 🌐 Other Services

### PgAdmin (Database Management)
```
http://localhost:5050
Username: admin@admin.com
Password: admin
```

### API Documentation
```
http://localhost:8001/docs
```

### Health Check
```
http://localhost:8001/api/health
```

---

## 📝 Next Steps

1. ✅ Test camera and recording
2. ✅ Check emotion detection accuracy
3. ✅ Monitor console for errors
4. ✅ Generate session reports
5. ✅ Review API documentation

---

## 🆘 Getting Help

- Check `UI_FIXES_AND_IMPROVEMENTS.md` for recent fixes
- Run tests to verify functionality
- Check Docker logs: `docker-compose logs app`
- Check browser console (F12) for JavaScript errors

---

**Happy Tracking!** 🎯

