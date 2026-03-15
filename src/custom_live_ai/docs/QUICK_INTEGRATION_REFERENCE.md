# Custom Live AI - Quick Integration Reference

## TL;DR - What is Custom Live AI?

A **self-hosted, real-time motion capture & emotion detection system** that monitors:
- Body posture and pose
- Facial expressions and emotions
- Hand gestures and fidgeting
- Eye contact and engagement
- Provides intelligent interventions (breaks, posture alerts, emotional support)

Perfect as a microservice for healthcare AI systems.

---

## Quick Facts

| Aspect | Details |
|--------|---------|
| **Purpose** | Real-time behavior monitoring with AI interventions |
| **Tech Stack** | FastAPI, MediaPipe, face-api.js, PostgreSQL, Docker |
| **Default Port** | 8001 (FastAPI backend), 5433 (PostgreSQL) |
| **Start Command** | `docker-compose up -d` |
| **Access URL** | http://localhost:8001/ |
| **Dependencies** | Docker, webcam, 4GB RAM, browser |

---

## Architecture at a Glance

```
Browser (MediaPipe + face-api.js)
         ↓ WebSocket/REST
     FastAPI Backend (port 8001)
         ↓
    Processing Layer
    - Video Analysis (MediaPipe)
    - Emotion Detection (ML + face-api)
    - Intervention Engine (rules-based)
    - Report Generation (AI-powered)
         ↓
    PostgreSQL Database (port 5433)
    + JSON File Storage (/recordings)
```

---

## Core Components

### 1. Video Processing
- **MediaPipe Analyzer**: Detects pose (33 points), face (468 points), hands (21 points each)
- **Output**: Posture quality, head tilt, shoulder angle, hand movement, fidgeting

### 2. Emotion Detection
- **face-api.js**: Browser-side emotion scores
- **ML Classifier**: LightGBM/XGBoost for refined detection
- **Temporal Smoothing**: Prevents emotion flickering
- **Output**: Emotion + confidence + all emotion scores

### 3. Intervention Engine
- **Rules**: Posture (3min poor), Emotion (2min negative), Break (45min), Engagement (30sec face-off)
- **Cooldowns**: Prevents intervention spam
- **Tone Adaptation**: Supportive, motivational, gentle messaging

### 4. Recording & Reports
- **Frame-by-frame recording**: Pose, face, hands, emotion data
- **Database or JSON storage**: Configurable
- **Playback**: Reconstruct sessions from stored data
- **Reports**: Emotion timeline, posture analysis, behavioral insights

---

## Key Endpoints for Integration

### Start/Stop Sessions
```bash
# Start recording
POST /api/healthcare/session/start
Body: {user_id?, metadata?}
Returns: {session_id, start_time}

# Stop recording
POST /api/healthcare/session/stop
Body: {session_id}
Returns: {duration, total_frames, intervention_count, summary}
```

### Real-time Streaming
```bash
# WebSocket connection
WS /ws/integration/{session_id}

# Receives:
- Emotion every 1 second
- Posture every 2 seconds
- Engagement every 5 seconds
- Heartbeat ping every 10 seconds
```

### Get Status & Trigger Intervention
```bash
# Current session state
GET /api/healthcare/session/{session_id}/status

# Manually trigger intervention
POST /api/healthcare/intervention/trigger
Body: {session_id, intervention_type, reason?, message?}
```

### Get Results
```bash
# Get comprehensive report
GET /api/reports/session/{session_id}

# Get session data
GET /api/db/sessions/{session_id}
```

---

## Frontend Features

### UI Tabs
- **Recording**: Start/stop camera, recording status
- **Session**: Metrics, frames recorded, duration
- **Emotion**: Real-time emoji, confidence, emotion scores
- **Posture**: Body part visibility, slouch detection
- **Interventions**: Manual test buttons, intervention history
- **Stats**: FPS, face detection rate, eye contact %

### Real-time Visualization
- Video stream with skeleton overlay (colored boxes per body part)
- Emotion emoji that updates in real-time
- Intervention messages and history
- Stats dashboard with metrics

### Console System
- Multiple tabs: All Events, Errors Only, API Calls
- Color-coded logging (info, success, warning, error)
- Max 50 lines per tab (auto-scroll)
- Duplicate message throttling

---

## Database Schema Summary

```
Users
├── user_id (unique)
├── name, age, gender
└── notes

Sessions
├── session_id (unique)
├── user_id (FK)
├── timing (start_time, end_time, duration)
├── metrics (total_frames, avg_fps, face_detection_rate)
├── emotion_metrics (avg_smile, eye_open, mouth_open)
├── behavioral (blinks, smiles, surprises)
├── intervention_count, avg_response_time
└── file_paths (json_file, csv_file)

EmotionEvents
├── session_id (FK)
├── timestamp, emotion, confidence
└── emotion_scores (JSON)

InterventionLogs
├── session_id (FK)
├── timestamp, intervention_type, trigger_reason
└── message, tone, response_time
```

---

## Integration with Healthcare AI Live2D

### Data Flow
```
Custom Live AI
    ↓ Real-time stream (WebSocket)
    ├→ Emotion (for avatar expressions)
    ├→ Posture (for avatar pose)
    ├→ Interventions (for avatar animations)
    └→ Engagement metrics
    
    ↓ Reports (REST)
    └→ Session analysis, insights, recommendations
    
Healthcare AI Live2D
    ↓ Control commands
    ├→ Start/stop session
    ├→ Trigger interventions
    └→ Query status/reports
```

### Integration Options

**Option 1: Separate Deployment (Recommended)**
- Custom Live AI on separate Docker network/server
- Healthcare AI calls via HTTP/WebSocket
- Independent scaling and updates
- Easier debugging

**Option 2: Integrated Deployment**
- Both services in same Docker Compose
- Internal Docker DNS for communication
- Shared database possible
- Simplified deployment

### Example Integration Code
```python
# Start session from healthcare app
import httpx

session_response = httpx.post(
    "http://custom-live-ai:8001/api/healthcare/session/start",
    json={"user_id": "user123"}
)
session_id = session_response.json()["session_id"]

# Subscribe to real-time stream
ws_url = f"ws://custom-live-ai:8001/ws/integration/{session_id}"
# Use WebSocket client to connect

# Get final report
report = httpx.get(
    f"http://custom-live-ai:8001/api/reports/session/{session_id}"
).json()
```

---

## Configuration

### Key Environment Variables
```bash
DATABASE_URL=postgresql://user:pass@db:5432/custom_live_ai
PORT=8001
USE_DATABASE_RECORDER=true
FRAME_BATCH_SIZE=50
WEBSOCKET_HEARTBEAT_SEC=10
ENABLE_AI_ANALYSIS=false
```

### Docker Compose Services
- **db**: PostgreSQL 15 (port 5433)
- **pgadmin**: Web database manager (port 5051)
- **app**: FastAPI backend (port 8001)

### Quick Start
```bash
cd custom_live_ai
docker-compose up -d          # Start services
curl http://localhost:8001/   # Open in browser
```

---

## Troubleshooting

### Camera Not Starting
- Check webcam is connected and not in use
- Grant browser camera permission
- Try in Chrome/Firefox (not all browsers supported)

### 404 Errors
- Use `http://localhost:8001/` (with trailing slash)
- NOT `http://localhost:8001/detailed`

### 422 Validation Errors
- Normal initially (face detection takes time)
- Ensure good lighting and camera angle
- Face should be clearly visible in frame

### API Connection Issues
- Check Docker containers running: `docker-compose ps`
- View logs: `docker-compose logs app`
- Verify network: `docker network ls`

---

## Performance Expectations

| Metric | Expected |
|--------|----------|
| FPS | 30-60 (depends on hardware) |
| Face Detection Latency | 1-3 seconds initial |
| Emotion Update Frequency | Every 500ms |
| Emotion Smoothing | 200-500ms lag |
| WebSocket Batch Interval | When 5 messages or 1 second |
| Database Insert Batch | 50 frames per batch |

---

## API Documentation

### Full API Docs
```
http://localhost:8001/docs         # Interactive Swagger UI
http://localhost:8001/redoc        # ReDoc documentation
```

### Key Routes
```
POST /api/db/users                 # Create user
GET  /api/db/sessions/{id}         # Get session
POST /api/emotion/analyze          # Analyze emotion
POST /api/healthcare/session/start # Start session
POST /api/healthcare/session/stop  # Stop session
GET  /api/reports/session/{id}     # Get report
WS   /ws/integration/{id}          # Real-time stream
```

---

## File Structure

```
custom_live_ai/
├── src/
│   ├── video/              # MediaPipe video analysis
│   ├── emotion/            # Emotion detection (ML)
│   ├── intervention/       # Intervention engine
│   ├── api/                # REST API endpoints
│   ├── models/             # Database models (ORM)
│   ├── reports/            # Report generation
│   ├── utils/              # Recording, metrics, etc
│   ├── static/             # HTML UI files
│   └── main.py             # FastAPI app
├── tests/                  # Test suite
├── docker-compose.yml      # Docker setup
├── Dockerfile              # Container definition
├── requirements.txt        # Python dependencies
└── migrations/             # Database migrations (SQL)
```

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

### Test Endpoints
```bash
curl -X POST http://localhost:8001/api/test-video \
  -F "image_file=@test_image.jpg"
```

---

## Common Tasks

### Create User
```bash
curl -X POST http://localhost:8001/api/db/users \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "name": "John Doe", "age": 25}'
```

### Start Session
```bash
curl -X POST http://localhost:8001/api/healthcare/session/start \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1"}'
```

### Trigger Intervention Manually
```bash
curl -X POST http://localhost:8001/api/healthcare/intervention/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_abc123",
    "intervention_type": "posture_alert",
    "reason": "Poor posture detected"
  }'
```

### Get Session Report
```bash
curl http://localhost:8001/api/reports/session/session_abc123 \
  | python -m json.tool
```

---

## Deployment Checklist

- [ ] Docker & Docker Compose installed
- [ ] Ports available (8001, 5433, 5051)
- [ ] 4GB+ RAM available
- [ ] Webcam connected (for testing)
- [ ] Run `docker-compose up -d`
- [ ] Verify health: `curl http://localhost:8001/health`
- [ ] Test camera in browser
- [ ] Review logs: `docker-compose logs app`
- [ ] Configure .env if needed
- [ ] Run tests: `pytest tests/`

---

## Support Resources

- **Full Documentation**: `/ARCHITECTURE_AND_INTEGRATION_GUIDE.md`
- **Quick Start**: `/QUICK_START.md`
- **Demo Ready**: `/DEMO_READY.md`
- **API Docs**: http://localhost:8001/docs
- **Test Examples**: `/tests/` directory
- **GitHub Issues**: Report bugs and request features

---

## Version Info

- **Custom Live AI**: 1.0.0
- **FastAPI**: 0.104.1
- **MediaPipe**: 0.10.14
- **Python**: 3.11+
- **PostgreSQL**: 15
- **Status**: Production Ready

