# Custom Live AI - Documentation Index

Welcome! This directory contains comprehensive documentation for the Custom Live AI module - a self-hosted, production-ready motion capture and emotion detection system.

## Quick Navigation

### For Quick Understanding
Start here if you just want to understand what this module does:
- **[QUICK_INTEGRATION_REFERENCE.md](QUICK_INTEGRATION_REFERENCE.md)** - TL;DR reference with key facts, endpoints, and troubleshooting

### For Detailed Understanding
Read this for comprehensive technical knowledge:
- **[ARCHITECTURE_AND_INTEGRATION_GUIDE.md](ARCHITECTURE_AND_INTEGRATION_GUIDE.md)** - Complete 1,900+ line technical documentation covering all aspects

### For Getting Started
Quick setup and demo information:
- **[QUICK_START.md](QUICK_START.md)** - How to start the application
- **[DEMO_READY.md](DEMO_READY.md)** - Demo script for presentations

### For Deployment
Production deployment information:
- **[docker-compose.yml](docker-compose.yml)** - Docker configuration
- **[Dockerfile](Dockerfile)** - Container specification
- **[requirements.txt](requirements.txt)** - Python dependencies

### For Testing
Test coverage and validation:
- **[TESTING_README.md](TESTING_README.md)** - Testing guide
- **[/tests](tests/)** - Test suite directory

---

## What is Custom Live AI? (30-second summary)

Custom Live AI is a **self-hosted, real-time behavior monitoring system** that:

1. **Detects** body movements, facial expressions, and hand gestures using MediaPipe
2. **Analyzes** emotions using face-api.js + ML classifiers with temporal smoothing
3. **Monitors** behavior patterns (posture, engagement, emotional state)
4. **Intervenes** intelligently (break reminders, posture alerts, emotional support)
5. **Records** everything frame-by-frame for playback and analysis
6. **Reports** comprehensive insights with AI-generated recommendations

Perfect as a microservice for healthcare AI systems that need real-time behavioral monitoring.

---

## Documentation Structure

### 1. QUICK_INTEGRATION_REFERENCE.md (434 lines)
**Best for:** Developers who want a quick reference

Contains:
- TL;DR definition
- Quick facts table
- Core components overview
- Key endpoints reference
- Integration options
- Troubleshooting
- Common tasks
- Performance expectations

### 2. ARCHITECTURE_AND_INTEGRATION_GUIDE.md (1,904 lines)
**Best for:** Understanding the complete system

Sections:
1. **Overview** - What Custom Live AI is and key characteristics
2. **What is Custom Live AI?** - Purpose, target users, key features
3. **Main Components & Functionality** - Detailed breakdown of 8 major components
4. **Architecture** - System design, data flow, message patterns
5. **Dependencies & Requirements** - All libraries and system requirements
6. **API Endpoints & Integration Points** - 40+ endpoints fully documented
7. **Frontend Components** - UI, technology stack, features
8. **Integration with Healthcare AI Live2D** - Integration strategies and examples
9. **Database Schema** - Complete database design
10. **Workflow & Data Flow** - How data moves through the system
11. **Configuration & Environment** - All settings and deployment options
12. **Testing & Deployment** - Test suite and deployment checklist

---

## Key Components at a Glance

### Core Modules

| Module | Location | Purpose |
|--------|----------|---------|
| Video Processing | `/src/video/` | MediaPipe pose, face, hand detection |
| Emotion Detection | `/src/emotion/` | ML-based emotion classification with smoothing |
| Intervention Engine | `/src/intervention/` | Rules-based behavior monitoring and intervention |
| Recording & Tracking | `/src/utils/` | Frame capture and session recording |
| Database Models | `/src/models/` | ORM models for PostgreSQL |
| Report Generation | `/src/reports/` | Post-session analysis with AI insights |
| API Layer | `/src/api/` | REST endpoints and WebSocket handlers |
| Frontend | `/src/static/` | Web UI with real-time visualization |

### Key Features

- **Real-time Detection**: 30-60 FPS pose, face, hand tracking
- **Emotion Analysis**: 7 emotions with confidence scores
- **Intervention System**: Posture, emotion, break, engagement monitoring
- **Recording**: Full frame data storage (database or JSON)
- **Reports**: Timeline analysis, behavioral insights, AI recommendations
- **REST API**: 40+ endpoints for session and emotion management
- **WebSocket**: Real-time streaming with batching and heartbeat
- **Live2D Integration**: Emotion→expression, Posture→pose mapping

---

## Integration Overview

### How to Integrate with Healthcare AI Live2D

**Option 1: Separate Deployment (Recommended)**
```
Healthcare AI Live2D          Custom Live AI
       ↓                             ↑
    Control              REST/WebSocket
       ↓                             ↑
    Start/Stop Session              
    Monitor Status
    Trigger Interventions
    Retrieve Reports
```

**Option 2: Integrated Deployment**
```
Single Docker Compose
  • Healthcare AI (port 8000)
  • Custom Live AI (port 8001)
  • Shared PostgreSQL (optional)
```

### Integration Flow

1. **Start Session**: `POST /api/healthcare/session/start`
2. **Subscribe**: `WS /ws/integration/{session_id}`
3. **Monitor**: `GET /api/healthcare/session/{id}/status`
4. **Control**: `POST /api/healthcare/intervention/trigger`
5. **Get Report**: `GET /api/reports/session/{id}`

---

## File Structure

```
custom_live_ai/
├── Documentation (this folder)
│   ├── ARCHITECTURE_AND_INTEGRATION_GUIDE.md   (1,904 lines)
│   ├── QUICK_INTEGRATION_REFERENCE.md          (434 lines)
│   ├── QUICK_START.md                          (Setup guide)
│   ├── DEMO_READY.md                           (Demo script)
│   ├── DOCUMENTATION_INDEX.md                  (This file)
│   └── *.md                                    (Other guides)
│
├── src/                           (Application code)
│   ├── video/                     (MediaPipe analysis)
│   ├── emotion/                   (ML emotion detection)
│   ├── intervention/              (Behavior monitoring)
│   ├── api/                       (REST/WebSocket endpoints)
│   ├── models/                    (Database ORM)
│   ├── reports/                   (Analysis generation)
│   ├── utils/                     (Recording, metrics)
│   └── static/                    (HTML UI files)
│
├── tests/                         (Test suite)
│   ├── test_emotion_*.py
│   ├── test_intervention_*.py
│   ├── test_api_*.py
│   └── *.py
│
├── Docker Configuration
│   ├── docker-compose.yml         (Multi-service setup)
│   ├── Dockerfile                 (Container spec)
│   ├── requirements.txt            (Python deps)
│   └── requirements_docker.txt     (Lean deps)
│
└── Configuration
    ├── env.example                (Environment template)
    ├── migrations/                (Database SQL)
    └── init_db.sql                (Database init)
```

---

## Quick Start

### 1. Start the System
```bash
cd custom_live_ai
docker-compose up -d
```

### 2. Verify Health
```bash
curl http://localhost:8001/health
```

### 3. Open in Browser
```
http://localhost:8001/
```

### 4. Try a Test
```bash
# Test emotion analysis
curl -X POST http://localhost:8001/api/test-video \
  -F "image_file=@test_image.jpg"
```

---

## Common Tasks

### Create a User
```bash
POST /api/db/users
Body: {user_id, name, age, gender}
```

### Start a Session
```bash
POST /api/healthcare/session/start
Body: {user_id}
Returns: {session_id, start_time}
```

### Get Real-time Stream
```bash
WS /ws/integration/{session_id}
Receives: emotion, posture, engagement every 1-5 seconds
```

### Trigger Intervention
```bash
POST /api/healthcare/intervention/trigger
Body: {session_id, intervention_type, reason, message}
```

### Get Report
```bash
GET /api/reports/session/{session_id}
Returns: Complete analysis with insights
```

---

## Key Statistics

| Metric | Value |
|--------|-------|
| **Code Lines** | ~3,000+ Python |
| **Documentation** | ~2,300+ lines |
| **API Endpoints** | 40+ |
| **Database Tables** | 4+ |
| **Frontend Pages** | 4 (demo, dev, playback, reports) |
| **Test Files** | 13+ |
| **Test Coverage** | Comprehensive |
| **Dependencies** | 40+ Python packages |

---

## Architecture Summary

### Technology Stack
- **Backend**: FastAPI 0.104.1 with uvicorn
- **Computer Vision**: MediaPipe 0.10.14, OpenCV 4.8.1
- **Emotion Detection**: face-api.js + LightGBM/XGBoost
- **Database**: PostgreSQL 15 with SQLAlchemy ORM
- **Real-time**: WebSocket with automatic batching
- **Frontend**: Vanilla JavaScript, HTML5 Canvas
- **Deployment**: Docker & Docker Compose

### Core Capabilities
1. **Video Analysis**: 33-point pose, 468-point face mesh, 21-point hands
2. **Emotion Detection**: 7 emotions with confidence and temporal smoothing
3. **Behavior Monitoring**: Posture, engagement, fidgeting detection
4. **Interventions**: Rules-based with cooldown management
5. **Recording**: Full frame capture and playback
6. **Reports**: Timeline analysis with AI-generated insights
7. **Integration**: REST API + WebSocket for external systems

---

## Deployment Checklist

- [ ] Docker & Docker Compose installed
- [ ] Ports available (8001, 5433, 5051)
- [ ] 4GB+ RAM available
- [ ] Read QUICK_START.md
- [ ] Read ARCHITECTURE_AND_INTEGRATION_GUIDE.md
- [ ] Run `docker-compose up -d`
- [ ] Test `http://localhost:8001/`
- [ ] Test camera in browser
- [ ] Review API docs at `/docs`
- [ ] Run tests with pytest

---

## Testing

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Test
```bash
pytest tests/test_intervention_system.py -v
```

### With Coverage
```bash
pytest tests/ --cov=src --cov-report=html
```

---

## Support & Resources

### Documentation Files
- **Full Guide**: ARCHITECTURE_AND_INTEGRATION_GUIDE.md
- **Quick Ref**: QUICK_INTEGRATION_REFERENCE.md
- **Quick Start**: QUICK_START.md
- **Demo Script**: DEMO_READY.md

### Online Resources
- **API Docs**: http://localhost:8001/docs (Swagger UI)
- **ReDoc**: http://localhost:8001/redoc
- **Health Check**: http://localhost:8001/health
- **pgAdmin**: http://localhost:5051 (Database management)

### Troubleshooting
See QUICK_INTEGRATION_REFERENCE.md section "Troubleshooting" for:
- Camera not starting
- 404/422 errors
- API connection issues
- Performance optimization

---

## Version Information

| Component | Version |
|-----------|---------|
| Custom Live AI | 1.0.0 |
| FastAPI | 0.104.1 |
| MediaPipe | 0.10.14 |
| PostgreSQL | 15 |
| Python | 3.11+ |
| Status | Production Ready |

---

## Architecture Diagram

```
┌─────────────────────────────────────┐
│   Browser (Frontend)                 │
│  MediaPipe + face-api.js            │
│  WebSocket + REST Client             │
└────────────────┬──────────────────────┘
                 │ HTTP/WebSocket
                 ▼
┌────────────────────────────────────────┐
│   FastAPI Backend (port 8001)         │
│  - API Routes                         │
│  - WebSocket Handlers                 │
│  - Processing Layer                   │
│    • Video Analysis                   │
│    • Emotion Detection                │
│    • Intervention Engine              │
│    • Report Generation                │
└────────────────┬───────────────────────┘
                 │ SQL/JSON
                 ▼
┌────────────────────────────────────────┐
│   Data Layer                          │
│  - PostgreSQL (port 5433)             │
│  - JSON Files (/recordings)           │
│  - pgAdmin (port 5051)                │
└────────────────────────────────────────┘
```

---

## Getting Help

1. **Quick answers?** → See QUICK_INTEGRATION_REFERENCE.md
2. **Technical details?** → See ARCHITECTURE_AND_INTEGRATION_GUIDE.md
3. **Setup issues?** → See QUICK_START.md
4. **API questions?** → See http://localhost:8001/docs
5. **Integration help?** → See ARCHITECTURE_AND_INTEGRATION_GUIDE.md section "Integration with Healthcare AI Live2D"

---

**Generated**: 2025-11-09  
**Status**: Production Ready  
**Maintainer**: FYP Team

For detailed information, please refer to the appropriate documentation file listed above.
