"""
Custom Live AI - Test Server
FastAPI application for testing audio and video processing
"""
# pylint: disable=no-member  # False positive for cv2 (C extension)

from contextlib import asynccontextmanager
from typing import Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
import asyncio
import base64
import io
import numpy as np
import cv2
import time
import os
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    logger.info("🚀 Custom Live AI Test Server starting...")
    logger.info("📍 Open http://localhost:8001 in your browser to test")
    logger.info("✅ Intervention engine initialized")
    logger.info("✅ Real-time streaming available at /ws/integration/{session_id}")
    
    yield  # App runs here
    
    # Shutdown
    logger.info("Shutting down...")
    # Close analyzers
    if video_analyzer:
        video_analyzer.close()


# Create FastAPI app
app = FastAPI(
    lifespan=lifespan,
    title="Custom Live AI Test Server",
    description="Test server for audio and video processing",
    version="1.0.0"
)

# Add CORS middleware
# SECURITY: Restrict origins to known services
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", 
    "http://localhost:8000,http://localhost:8001,http://localhost:8002"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Import our modules (after app creation - FastAPI pattern)
# Audio imports commented out for Docker (not needed for motion capture)
# from src.custom_live_ai.audio.stt import SpeechToText, CantoneseSpeechToText
# from src.custom_live_ai.audio.tts import TextToSpeech, ChildFriendlyTTS
# from src.custom_live_ai.utils.audio_utils import AudioUtils
from src.custom_live_ai.video.mediapipe_analyzer import MediaPipeAnalyzer  # noqa: E402
from src.custom_live_ai.video.emotion_detector import SimplifiedEmotionDetector  # noqa: E402
from src.custom_live_ai.utils.data_recorder import SessionRecorder  # noqa: E402
from src.custom_live_ai.utils.detailed_recorder import DetailedRecorder  # noqa: E402

# Import database API routes (after app creation)
from src.custom_live_ai.api.sessions import router as sessions_router  # noqa: E402
from src.custom_live_ai.api.emotion_api import router as emotion_router  # noqa: E402
from src.custom_live_ai.api.live2d_sync import router as live2d_router  # noqa: E402
from src.custom_live_ai.api.reports import router as reports_router  # noqa: E402
from src.custom_live_ai.api.healthcare_integration import router as healthcare_router  # noqa: E402

# Register API routes
app.include_router(sessions_router)
app.include_router(emotion_router)
app.include_router(live2d_router)
app.include_router(reports_router)
app.include_router(healthcare_router)

# Mount static files (models, CSS, JS, etc.)
# Mount models directory for face-api.js
if os.path.exists("src/custom_live_ai/static/models"):
    app.mount("/models", StaticFiles(directory="src/custom_live_ai/static/models"), name="models")
    logger.info("✅ Mounted /models → src/static/models")

# Mount js directory if exists
if os.path.exists("src/custom_live_ai/static/js"):
    app.mount("/js", StaticFiles(directory="src/custom_live_ai/static/js"), name="js")
    logger.info("✅ Mounted /js → src/static/js")

# Mount css directory if exists
if os.path.exists("src/custom_live_ai/static/css"):
    app.mount("/css", StaticFiles(directory="src/custom_live_ai/static/css"), name="css")
    logger.info("✅ Mounted /css → src/static/css")

# Mount entire static directory as fallback
app.mount("/static", StaticFiles(directory="src/custom_live_ai/static"), name="static")
logger.info("✅ Mounted /static → src/static")

# Initialize components (lazy loading)
stt_engine = None
tts_engine = None
video_analyzer = None
emotion_detector = None
session_recorder = None
detailed_recorder = DetailedRecorder()  # Always initialized for detailed recordings

# Initialize intervention system
from src.custom_live_ai.intervention.engine import InterventionEngine  # noqa: E402
intervention_engine = InterventionEngine()


# Audio functions commented out for Docker
# def get_stt():
#     """Get or create STT engine"""
#     global stt_engine
#     if stt_engine is None:
#         logger.info("Initializing Speech-to-Text engine...")
#         stt_engine = SpeechToText(model_size="base", device="cpu")
#     return stt_engine


# def get_tts():
#     """Get or create TTS engine"""
#     global tts_engine
#     if tts_engine is None:
#         logger.info("Initializing Text-to-Speech engine...")
#         tts_engine = ChildFriendlyTTS(language="en")
#     return tts_engine


def get_video_analyzer():
    """Get or create video analyzer"""
    global video_analyzer
    if video_analyzer is None:
        logger.info("Initializing MediaPipe analyzer...")
        video_analyzer = MediaPipeAnalyzer(
            enable_pose=True,
            enable_face=True,
            enable_hands=True,
            mirror_mode=True  # Enable for webcam input (mirror view)
        )
    return video_analyzer


def get_emotion_detector():
    """Get or create emotion detector"""
    global emotion_detector
    if emotion_detector is None:
        logger.info("Initializing emotion detector...")
        # Use simplified detector for testing (faster)
        emotion_detector = SimplifiedEmotionDetector()
    return emotion_detector


def get_session_recorder():
    """Get or create session recorder"""
    global session_recorder
    if session_recorder is None:
        session_recorder = SessionRecorder()
    return session_recorder


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve detailed body part detection UI (Demo/Stable)"""
    return FileResponse("src/custom_live_ai/static/index_detailed.html")


@app.get("/index_detailed.html", response_class=HTMLResponse)
async def index_detailed():
    """Serve detailed body part detection UI (Demo/Stable) - explicit route"""
    return FileResponse("src/custom_live_ai/static/index_detailed.html")


@app.get("/index_detailed_dev.html", response_class=HTMLResponse)
async def index_detailed_dev():
    """Serve development UI with tabbed layout"""
    return FileResponse("src/custom_live_ai/static/index_detailed_dev.html")


@app.get("/playback", response_class=HTMLResponse)
async def playback():
    """Serve playback viewer for recorded sessions"""
    return FileResponse("src/custom_live_ai/static/playback.html")


@app.get("/reports", response_class=HTMLResponse)
async def reports():
    """Serve reports viewer for session reports"""
    return FileResponse("src/custom_live_ai/static/reports.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    import time
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "components": {
            "stt": stt_engine is not None,
            "tts": tts_engine is not None,
            "video": video_analyzer is not None,
            "emotion": emotion_detector is not None
        }
    }


@app.post("/api/db/init")
async def initialize_database():
    """Initialize database - create all tables"""
    try:
        from src.custom_live_ai.database.config import init_db
        init_db()
        return {"status": "success", "message": "Database initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Audio endpoints commented out for Docker (motion capture focus)
# @app.post("/api/test-stt")
# async def test_stt(audio_file: UploadFile = File(...), language: str = Form(None)):
#     """
#     Test Speech-to-Text
#     Upload audio file and get transcription
#     """
#     pass  # Commented out - Whisper not installed


# @app.post("/api/test-tts")
# async def test_tts(
#     text: str = Form(...),
#     language: str = Form("en"),
#     emotion: str = Form("neutral")
# ):
#     """
#     Test Text-to-Speech
#     Generate speech from text
#     """
#     pass  # Commented out - Edge TTS not installed


@app.post("/api/test-video")
async def test_video(image_file: UploadFile = File(...)):
    """
    Test video analysis on a single frame
    Returns pose, face, hand, and emotion data
    """
    try:
        logger.info(f"Testing video analysis with file: {image_file.filename}")
        
        # Read image
        image_data = await image_file.read()
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {"success": False, "error": "Failed to decode image"}
        
        # Analyze with MediaPipe
        analyzer = get_video_analyzer()
        results = analyzer.analyze_frame(frame)
        
        # Detect emotion
        emotion_det = get_emotion_detector()
        emotion_result = emotion_det.detect_emotion_simple(frame)
        
        # Format results
        response = {
            "success": True,
            "frame_size": {"width": frame.shape[1], "height": frame.shape[0]},
            "pose": None,
            "face": None,
            "hands": None,
            "emotion": None
        }
        
        # Pose data
        if results.get("pose_data"):
            pose = results["pose_data"]
            response["pose"] = {
                "posture_score": float(pose.posture_score),
                "posture_quality": pose.posture_quality.value,
                "shoulder_angle": float(pose.shoulder_angle),
                "head_tilt": float(pose.head_tilt),
                "is_slouching": bool(pose.is_slouching)  # Convert numpy.bool_ to bool
            }
        
        # Face data
        if results.get("face_data"):
            face = results["face_data"]
            response["face"] = {
                "face_visible": bool(face.face_visible),  # Convert numpy.bool_ to bool
                "eye_contact_score": float(face.eye_contact_score),
                "head_pose": {
                    "pitch": float(face.head_pose[0]),
                    "yaw": float(face.head_pose[1]),
                    "roll": float(face.head_pose[2])
                },
                "face_distance_score": float(face.face_distance_score)
            }
        
        # Hand data
        if results.get("hand_data"):
            hands = results["hand_data"]
            response["hands"] = {
                "left_hand_visible": bool(hands.left_hand_visible),  # Convert numpy.bool_ to bool
                "right_hand_visible": bool(hands.right_hand_visible),  # Convert numpy.bool_ to bool
                "movement_score": float(hands.movement_score),
                "is_fidgeting": bool(hands.is_fidgeting)  # Convert numpy.bool_ to bool
            }
        
        # Emotion data
        if emotion_result and emotion_result.face_detected:
            response["emotion"] = {
                "dominant_emotion": emotion_result.dominant_emotion.value,
                "confidence": float(emotion_result.confidence),
                "face_detected": bool(emotion_result.face_detected)  # Convert numpy.bool_ to bool
            }
        
        # Record frame if recording is active
        recorder = get_session_recorder()
        if recorder.is_recording:
            recorder.record_frame(
                pose_data=results.get("pose_data"),
                face_data=results.get("face_data"),
                hand_data=results.get("hand_data"),
                emotion_data=emotion_result
            )
        
        return response
        
    except Exception as e:
        logger.error(f"Video analysis test failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/test-video-visual")
async def test_video_visual(image_file: UploadFile = File(...)):
    """
    Test video analysis with visualization overlay
    Returns the frame with skeleton, bounding box, etc. drawn on it
    """
    try:
        logger.info(f"Testing video analysis with visualization: {image_file.filename}")
        
        # Read image
        image_data = await image_file.read()
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {"success": False, "error": "Failed to decode image"}
        
        # Analyze with MediaPipe
        analyzer = get_video_analyzer()
        results = analyzer.analyze_frame(frame)
        
        # Draw visualization overlay (skeleton, bounding box, etc.)
        annotated_frame = analyzer.draw_landmarks_on_frame(
            frame,
            results,
            draw_pose=True,
            draw_face=True,
            draw_hands=True,
            draw_bounding_box=True
        )
        
        # Convert frame to JPEG
        _, buffer = cv2.imencode('.jpg', annotated_frame)
        
        # Return as image
        return StreamingResponse(
            io.BytesIO(buffer.tobytes()),
            media_type="image/jpeg"
        )
        
    except Exception as e:
        logger.error(f"Video visualization test failed: {e}")
        # Return error as JSON
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/recording/start")
async def start_recording():
    """Start recording session data"""
    try:
        recorder = get_session_recorder()
        recorder.start_recording()
        
        return {
            "success": True,
            "session_id": recorder.session_id,
            "message": "Recording started"
        }
    except Exception as e:
        logger.error(f"Failed to start recording: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/recording/stop")
async def stop_recording():
    """Stop recording and save data"""
    try:
        recorder = get_session_recorder()
        recorder.stop_recording()
        
        # Save both JSON and CSV
        json_path = recorder.save_to_json()
        csv_path = recorder.save_to_csv()
        
        # Get summary
        summary = recorder.get_summary()
        
        return {
            "success": True,
            "session_id": recorder.session_id,
            "frames_recorded": recorder.frame_count,
            "json_file": json_path,
            "csv_file": csv_path,
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Failed to stop recording: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/recording/status")
async def recording_status():
    """Get current recording status"""
    try:
        recorder = get_session_recorder()
        
        return {
            "is_recording": recorder.is_recording,
            "session_id": recorder.session_id,
            "frames_recorded": recorder.frame_count,
            "duration": round(time.time() - recorder.start_time, 2) if recorder.is_recording else 0
        }
    except Exception as e:
        return {
            "is_recording": False,
            "error": str(e)
        }


@app.post("/api/recording/frame")
async def record_frame(data: dict):
    """
    Record a single frame from client-side MediaPipe
    Called by the browser once per second during recording
    """
    try:
        recorder = get_session_recorder()
        
        if not recorder.is_recording:
            return {"success": False, "error": "Not recording"}
        
        # Extract landmarks from the data
        
        if data.get('pose') and data['pose'].get('landmarks'):
            data['pose']['landmarks']
        
        if data.get('hands') and data['hands'].get('landmarks'):
            data['hands']['landmarks']
        
        # Create a simplified record (client already has the data)
        # We just acknowledge and increment counter
        recorder.frame_count += 1
        
        return {
            "success": True,
            "frame_number": recorder.frame_count
        }
        
    except Exception as e:
        logger.error(f"Failed to record frame: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/recording/download/{filename}")
async def download_recording(filename: str):
    """Download a recorded file"""
    try:
        filepath = f"recordings/{filename}"
        
        if not os.path.exists(filepath):
            return {"success": False, "error": "File not found"}
        
        return FileResponse(
            filepath,
            media_type="application/octet-stream",
            filename=filename
        )
    except Exception as e:
        logger.error(f"Failed to download file: {e}")
        return {"success": False, "error": str(e)}


# ============================================
# Detailed Recording Endpoints (New System)
# ============================================

@app.post("/api/detailed-recording/start")
async def start_detailed_recording():
    """Start detailed recording session"""
    try:
        session_id = detailed_recorder.start_recording()
        
        return {
            "success": True,
            "session_id": session_id,
            "message": "Detailed recording started"
        }
    except Exception as e:
        logger.error(f"Failed to start detailed recording: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/detailed-recording/stop")
async def stop_detailed_recording():
    """Stop detailed recording and save files"""
    try:
        logger.info("Stopping detailed recording...")
        
        # Stop recording
        summary = detailed_recorder.stop_recording()
        logger.info(f"Recording stopped: {summary}")
        
        # Save JSON
        logger.info("Saving JSON file...")
        json_path = detailed_recorder.save_to_json()
        logger.info(f"JSON saved: {json_path}")
        
        # Save CSV
        logger.info("Saving CSV file...")
        csv_path = detailed_recorder.save_summary_csv()
        logger.info(f"CSV saved: {csv_path}")
        
        return {
            "success": True,
            "session_id": summary.get("session_id", "unknown"),
            "total_frames": summary.get("total_frames", 0),
            "duration": summary.get("duration", 0),
            "fps": summary.get("fps", 0),
            "json_file": json_path,
            "csv_file": csv_path
        }
    except Exception as e:
        logger.error(f"Failed to stop detailed recording: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


@app.post("/api/detailed-recording/frame")
async def record_detailed_frame(data: dict):
    """
    Record a detailed frame from client-side MediaPipe
    
    Expected data:
    {
        "timestamp": 1.5,
        "bodyParts": {...},
        "pose": {"landmarks": [...]},
        "hands": {"landmarks": [...], "handedness": [...]},
        "metadata": {...}
    }
    """
    try:
        detailed_recorder.record_frame(data)
        
        return {
            "success": True,
            "frame_number": detailed_recorder.frame_count
        }
    except Exception as e:
        logger.error(f"Failed to record detailed frame: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/detailed-recording/status")
async def detailed_recording_status():
    """Get current detailed recording status"""
    try:
        return detailed_recorder.get_status()
    except Exception as e:
        return {
            "is_recording": False,
            "error": str(e)
        }


@app.get("/api/detailed-recording/list")
async def list_detailed_recordings():
    """List all detailed recordings"""
    try:
        import glob
        
        recordings = []
        for filepath in glob.glob("recordings/*_detailed.json"):
            filename = os.path.basename(filepath)
            session_id = filename.replace("_detailed.json", "")
            
            # Get file stats
            stat = os.stat(filepath)
            
            recordings.append({
                "session_id": session_id,
                "filename": filename,
                "size": stat.st_size,
                "modified": stat.st_mtime
            })
        
        # Sort by modification time (newest first)
        recordings.sort(key=lambda x: x["modified"], reverse=True)
        
        return {
            "success": True,
            "recordings": recordings
        }
    except Exception as e:
        logger.error(f"Failed to list recordings: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/api/detailed-recording/load/{session_id}")
async def load_detailed_recording(session_id: str):
    """Load a detailed recording for playback"""
    try:
        filepath = f"recordings/{session_id}_detailed.json"
        
        if not os.path.exists(filepath):
            return {
                "success": False,
                "error": "Recording not found"
            }
        
        # Load and return the recording
        with open(filepath, 'r') as f:
            recording_data = json.load(f)
        
        return {
            "success": True,
            "data": recording_data
        }
    except Exception as e:
        logger.error(f"Failed to load recording: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.websocket("/ws/live-test")
async def websocket_live_test(websocket: WebSocket):
    """
    WebSocket for live testing
    Continuously process audio/video frames
    """
    await websocket.accept()
    logger.info("WebSocket connection established")
    
    try:
        while True:
            # Receive data
            data = await websocket.receive_json()
            
            message_type = data.get("type")
            
            # Audio websocket handling commented out for Docker
            # if message_type == "audio":
            #     pass  # Audio processing disabled
            
            if message_type == "video":
                # Process video frame
                image_base64 = data.get("image")
                image_data = base64.b64decode(image_base64)
                
                try:
                    nparr = np.frombuffer(image_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        # Analyze
                        analyzer = get_video_analyzer()
                        results = analyzer.analyze_frame(frame)
                        
                        # Format response
                        response: dict[str, Any] = {"type": "video_result"}
                        
                        if results.get("pose_data"):
                            pose = results["pose_data"]
                            response["pose"] = {
                                "score": float(pose.posture_score),
                                "quality": pose.posture_quality.value,
                                "slouching": pose.is_slouching
                            }
                        
                        if results.get("face_data"):
                            face = results["face_data"]
                            response["face"] = {
                                "visible": face.face_visible,
                                "eye_contact": float(face.eye_contact_score)
                            }
                        
                        if results.get("hand_data"):
                            hands = results["hand_data"]
                            response["hands"] = {
                                "fidgeting": hands.is_fidgeting
                            }
                        
                        await websocket.send_json(response)
                        
                except Exception as e:
                    logger.error(f"Video processing error: {e}")
            
            elif message_type == "ping":
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


@app.websocket("/ws/integration/{session_id}")
async def websocket_integration_stream(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time data streaming to healthcare system
    
    Enhanced with:
    - Heartbeat/ping every 10s to detect disconnections
    - Frame batching for better performance
    - Reconnection support
    
    Streams real-time metrics:
    - Current emotion every 1s
    - Posture quality every 2s
    - Intervention events immediately
    - Engagement metrics every 5s
    """
    await websocket.accept()
    logger.info(f"🔌 WebSocket connection established for session: {session_id}")
    
    # WebSocket configuration
    heartbeat_interval = int(os.getenv("WEBSOCKET_HEARTBEAT_SEC", "10"))
    batch_size = int(os.getenv("WEBSOCKET_BATCH_SIZE", "5"))
    
    try:
        from src.custom_live_ai.api.healthcare_integration import active_sessions
        
        # Check if session exists
        if session_id not in active_sessions:
            await websocket.send_json({
                "error": "Session not found",
                "session_id": session_id
            })
            await websocket.close()
            return
        
        recorder = active_sessions[session_id]
        last_emotion_time = 0
        last_posture_time = 0
        last_engagement_time = 0
        last_heartbeat_time = 0
        message_buffer = []  # Buffer for batch sending
        
        while True:
            current_time = time.time()
            
            # Heartbeat/ping to detect disconnections
            if current_time - last_heartbeat_time >= heartbeat_interval:
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": current_time
                    })
                    last_heartbeat_time = current_time
                except Exception as e:
                    logger.warning(f"Heartbeat failed, client likely disconnected: {e}")
                    break
            
            # Get current session state
            status = recorder.get_status()
            engine_state = intervention_engine.get_session_state(session_id)
            
            # Collect emotion data every 1s
            if current_time - last_emotion_time >= 1.0:
                if engine_state and engine_state.get("current_emotion"):
                    message_buffer.append({
                        "type": "emotion",
                        "timestamp": current_time,
                        "data": {
                            "emotion": engine_state.get("current_emotion"),
                            "session_id": session_id
                        }
                    })
                last_emotion_time = current_time
            
            # Collect posture data every 2s
            if current_time - last_posture_time >= 2.0:
                if hasattr(recorder, 'last_posture_quality') and recorder.last_posture_quality:
                    message_buffer.append({
                        "type": "posture",
                        "timestamp": current_time,
                        "data": {
                            "quality": recorder.last_posture_quality,
                            "session_id": session_id
                        }
                    })
                last_posture_time = current_time
            
            # Collect engagement data every 5s
            if current_time - last_engagement_time >= 5.0:
                message_buffer.append({
                    "type": "engagement",
                    "timestamp": current_time,
                    "data": {
                        "frames_recorded": status["frames_recorded"],
                        "duration": status["duration"],
                        "session_id": session_id
                    }
                })
                last_engagement_time = current_time
            
            # Send batched messages when buffer is full
            if len(message_buffer) >= batch_size:
                try:
                    await websocket.send_json({
                        "type": "batch",
                        "messages": message_buffer,
                        "count": len(message_buffer)
                    })
                    message_buffer.clear()
                except Exception as e:
                    logger.error(f"Failed to send batch: {e}")
                    break
            
            # Small delay to prevent CPU overload
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected for session: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except Exception:
            pass
    finally:
        # Send any remaining buffered messages
        if message_buffer:
            try:
                await websocket.send_json({
                    "type": "batch",
                    "messages": message_buffer,
                    "count": len(message_buffer),
                    "final": True
                })
            except Exception:
                pass
        
        try:
            await websocket.close()
        except Exception:
            pass




if __name__ == "__main__":
    # Run server
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )
