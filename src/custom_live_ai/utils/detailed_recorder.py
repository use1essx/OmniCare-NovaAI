"""
Detailed Recording Module
Records full MediaPipe data for complete session recreation
"""

import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)


class DetailedRecorder:
    """
    Records complete MediaPipe data for session playback
    Saves all landmarks, body parts, and metadata
    Supports both JSON files and database-first storage
    """
    
    def __init__(self, use_database: Optional[bool] = None, db_session = None, user_id: Optional[str] = None):
        """
        Initialize detailed recorder
        
        Args:
            use_database: Use database storage (default from env var USE_DATABASE_RECORDER)
            db_session: SQLAlchemy database session for database storage
            user_id: User identifier for database session record
        """
        self.session_id = None
        self.start_time = None
        self.start_datetime = None
        self.frames: List[Dict[str, Any]] = []
        self.is_recording = False
        self.frame_count = 0
        self.metadata = {}
        
        # Real-time tracking for interventions
        self.emotion_timeline: List[Dict] = []  # List of {timestamp, emotion, confidence}
        self.posture_events: List[Dict] = []  # List of {timestamp, event_type, severity}
        self.intervention_triggers: List[Dict] = []  # List of {timestamp, trigger_type}
        self.last_emotion: Optional[str] = None
        self.last_posture_quality: Optional[str] = None
        
        # Database-first storage configuration
        if use_database is None:
            use_database = os.getenv("USE_DATABASE_RECORDER", "true").lower() == "true"
        self.use_database = use_database
        self.db_session = db_session
        self.user_id = user_id or "anonymous"
        
        # Frame buffering for batch database inserts
        self.frame_buffer: List[Dict[str, Any]] = []
        self.buffer_size = int(os.getenv("FRAME_BATCH_SIZE", "50"))
        self.auto_save_interval = int(os.getenv("AUTO_SAVE_INTERVAL_SEC", "30"))
        self.auto_save_task = None
        self.db_session_record = None  # Database Session model instance
        
        # Ensure recordings directory exists (for JSON fallback/export)
        os.makedirs("recordings", exist_ok=True)
        
        storage_mode = "database" if self.use_database else "JSON files"
        logger.info(f"Detailed recorder initialized with real-time tracking (storage: {storage_mode})")
    
    def _init_database_storage(self):
        """Create session record in database"""
        if not self.use_database or not self.db_session:
            # Fall back to JSON mode if database not available
            if self.use_database and not self.db_session:
                logger.warning("Database session not available, falling back to JSON mode")
                self.use_database = False
            return
        
        try:
            from src.custom_live_ai.models.database import Session as DBSession
            
            # Create session record
            self.db_session_record = DBSession(
                session_id=self.session_id,
                user_id=self.user_id,
                start_time=self.start_datetime,
                status="active",
                data_source="database",
                auto_save_enabled=1,
                frames_saved_count=0,
                total_frames=0
            )
            self.db_session.add(self.db_session_record)
            self.db_session.commit()
            logger.info(f"✅ Database session record created: {self.session_id}")
        except Exception as e:
            logger.error(f"Failed to create database session record: {e}")
            self.db_session.rollback()
            # Fall back to JSON mode
            self.use_database = False
    
    def _save_frames_to_db(self):
        """Batch insert frames buffer to database"""
        if not self.use_database or not self.db_session or not self.frame_buffer:
            return
        
        try:
            from src.custom_live_ai.models.database import Frame
            
            # Prepare frame data for bulk insert
            frame_mappings = []
            for frame in self.frame_buffer:
                frame_mappings.append({
                    'session_id': self.session_id,
                    'frame_number': frame.get('frame_number', 0),
                    'timestamp': frame.get('timestamp', 0),
                    'body_parts': frame.get('bodyParts'),
                    'pose_landmarks': frame.get('pose'),
                    'hand_landmarks': frame.get('hands'),
                    'face_mesh_landmarks': frame.get('faceMesh'),
                    'emotion_data': frame.get('emotion'),
                    'frame_metadata': frame.get('metadata')
                })
            
            # Bulk insert frames
            self.db_session.bulk_insert_mappings(Frame, frame_mappings)
            
            # Update session record - re-query to avoid detached instance error
            from src.custom_live_ai.models.database import Session as DBSession
            db_session_record = self.db_session.query(DBSession).filter(
                DBSession.session_id == self.session_id
            ).first()
            
            if db_session_record:
                db_session_record.frames_saved_count = (db_session_record.frames_saved_count or 0) + len(self.frame_buffer)
                db_session_record.last_save_timestamp = time.time()
                db_session_record.total_frames = self.frame_count
            
            self.db_session.commit()
            logger.debug(f"✅ Saved {len(self.frame_buffer)} frames to database")
            
            # Clear buffer after successful save
            self.frame_buffer.clear()
            
        except Exception as e:
            logger.error(f"Failed to save frames to database: {e}")
            self.db_session.rollback()
    
    def _save_timeline_to_db(self):
        """Save timeline events to database"""
        if not self.use_database or not self.db_session:
            return
        
        try:
            from src.custom_live_ai.models.database import SessionTimeline
            
            timeline_mappings = []
            
            # Save emotion timeline
            for event in self.emotion_timeline:
                if not event.get('saved_to_db'):
                    timeline_mappings.append({
                        'session_id': self.session_id,
                        'timestamp': event.get('timestamp', 0),
                        'event_type': 'emotion',
                        'data': {
                            'emotion': event.get('emotion'),
                            'confidence': event.get('confidence')
                        }
                    })
                    event['saved_to_db'] = True
            
            # Save posture events
            for event in self.posture_events:
                if not event.get('saved_to_db'):
                    timeline_mappings.append({
                        'session_id': self.session_id,
                        'timestamp': event.get('timestamp', 0),
                        'event_type': 'posture',
                        'data': {
                            'event_type': event.get('event_type'),
                            'severity': event.get('severity')
                        }
                    })
                    event['saved_to_db'] = True
            
            # Save intervention triggers
            for event in self.intervention_triggers:
                if not event.get('saved_to_db'):
                    timeline_mappings.append({
                        'session_id': self.session_id,
                        'timestamp': event.get('timestamp', 0),
                        'event_type': 'intervention',
                        'data': {
                            'trigger_type': event.get('trigger_type')
                        }
                    })
                    event['saved_to_db'] = True
            
            if timeline_mappings:
                self.db_session.bulk_insert_mappings(SessionTimeline, timeline_mappings)
                self.db_session.commit()
                logger.debug(f"✅ Saved {len(timeline_mappings)} timeline events to database")
                
        except Exception as e:
            logger.error(f"Failed to save timeline to database: {e}")
            self.db_session.rollback()
    
    async def _auto_save_loop(self):
        """Background task - save every N seconds"""
        import asyncio
        while self.is_recording:
            try:
                await asyncio.sleep(self.auto_save_interval)
                if self.is_recording:
                    self._save_frames_to_db()
                    self._save_timeline_to_db()
                    logger.info(f"🔄 Auto-save: {self.frame_count} frames recorded, {len(self.frame_buffer)} buffered")
            except asyncio.CancelledError:
                logger.info("Auto-save task cancelled")
                break
            except Exception as e:
                logger.error(f"Auto-save error: {e}")
    
    def start_recording(self) -> str:
        """
        Start recording session
        
        Returns:
            session_id: Unique session identifier
        """
        timestamp = int(time.time())
        self.start_datetime = datetime.now()
        date_str = self.start_datetime.strftime("%Y%m%d_%H%M%S")
        self.session_id = f"session_{timestamp}_{date_str}"
        
        self.start_time = time.time()
        self.frames = []
        self.frame_buffer = []
        self.frame_count = 0
        self.is_recording = True
        
        # Reset real-time tracking
        self.emotion_timeline = []
        self.posture_events = []
        self.intervention_triggers = []
        self.last_emotion = None
        self.last_posture_quality = None
        
        self.metadata = {
            "session_id": self.session_id,
            "start_time": timestamp,
            "start_datetime": datetime.now().isoformat(),
            "version": "2.2",  # Updated version with database-first support
            "type": "detailed_body_part_detection"
        }
        
        # Initialize database storage if enabled
        if self.use_database:
            self._init_database_storage()
            # Start auto-save background task
            if self.auto_save_task is None:
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                self.auto_save_task = loop.create_task(self._auto_save_loop())
                logger.info(f"🔄 Auto-save task started (interval: {self.auto_save_interval}s)")
        
        storage_info = "database + auto-save" if self.use_database else "JSON files"
        logger.info(f"Recording started with real-time tracking: {self.session_id} ({storage_info})")
        return self.session_id
    
    def stop_recording(self) -> Dict[str, Any]:
        """
        Stop recording and return summary
        
        Returns:
            Summary of recording session
        """
        self.is_recording = False
        
        # Stop auto-save task if running
        if self.auto_save_task:
            self.auto_save_task.cancel()
            self.auto_save_task = None
            logger.info("Auto-save task stopped")
        
        # Calculate duration safely
        if self.start_time is not None:
            duration = time.time() - self.start_time
        else:
            duration = 0
            logger.warning("stop_recording called but start_time is None")
        
        # Final save to database if enabled
        if self.use_database:
            # Save remaining frames in buffer
            if self.frame_buffer:
                self._save_frames_to_db()
                logger.info(f"💾 Final save: {len(self.frame_buffer)} buffered frames")
            
            # Save timeline events
            self._save_timeline_to_db()
            
            # Update session status to completed - re-query to avoid detached instance
            if self.db_session and self.session_id:
                try:
                    from src.custom_live_ai.models.database import Session as DBSession
                    db_session_record = self.db_session.query(DBSession).filter(
                        DBSession.session_id == self.session_id
                    ).first()
                    
                    if db_session_record:
                        db_session_record.status = "completed"
                        db_session_record.end_time = datetime.now()
                        db_session_record.duration = duration
                        db_session_record.total_frames = self.frame_count
                        db_session_record.avg_fps = self.frame_count / duration if duration > 0 else 0
                        self.db_session.commit()
                        logger.info(f"✅ Database session record completed: {self.session_id}")
                except Exception as e:
                    logger.error(f"Failed to update session status: {e}")
                    self.db_session.rollback()
        
        summary = {
            "session_id": self.session_id or "unknown",
            "total_frames": self.frame_count,
            "duration": duration,
            "fps": self.frame_count / duration if duration > 0 else 0,
            "storage_mode": "database" if self.use_database else "json"
        }
        
        logger.info(f"Recording stopped: {self.session_id} ({self.frame_count} frames, {duration:.2f}s)")
        return summary
    
    def record_frame(self, frame_data: Dict[str, Any]):
        """
        Record a complete frame with all data
        
        Args:
            frame_data: Dictionary containing:
                - timestamp: Frame timestamp
                - bodyParts: Dict of body part detections
                - pose: Pose landmarks
                - hands: Hand landmarks
                - faceMesh: Face mesh landmarks (468 points)
                - emotion: Emotion detection data (label, emoji, confidence, scores)
                - metadata: Additional frame metadata
        """
        if not self.is_recording:
            return
        
        self.frame_count += 1
        
        # Create complete frame record
        frame_record = {
            "frame_number": self.frame_count,
            "timestamp": frame_data.get("timestamp", time.time() - self.start_time),
            "bodyParts": frame_data.get("bodyParts", {}),
            "pose": {
                "landmarks": frame_data.get("pose", {}).get("landmarks", [])
            },
            "hands": {
                "landmarks": frame_data.get("hands", {}).get("landmarks", []),
                "handedness": frame_data.get("hands", {}).get("handedness", [])
            },
            "faceMesh": {
                "landmarks": frame_data.get("faceMesh", {}).get("landmarks", [])
            },
            "emotion": frame_data.get("emotion", {
                "label": "Neutral",
                "emoji": "😐",
                "confidence": 0,
                "scores": {}
            }),
            "metadata": frame_data.get("metadata", {})
        }
        
        # Add to appropriate storage
        if self.use_database:
            # Add to buffer for batch insertion
            self.frame_buffer.append(frame_record)
            
            # Trigger batch save when buffer is full
            if len(self.frame_buffer) >= self.buffer_size:
                self._save_frames_to_db()
                logger.debug(f"Buffer full - saved {self.buffer_size} frames to database")
        else:
            # Fallback to in-memory frames list (for JSON export)
            self.frames.append(frame_record)
        
        if self.frame_count % 10 == 0:
            logger.debug(f"Recorded {self.frame_count} frames")
    
    def save_to_json(self, filepath: Optional[str] = None) -> str:
        """
        Save recording to JSON file
        
        Args:
            filepath: Optional custom filepath
            
        Returns:
            Path to saved file
        """
        session_id = self.session_id or f"session_unknown_{int(time.time())}"
        
        if filepath is None:
            filepath = f"recordings/{session_id}_detailed.json"
        
        # Calculate statistics safely
        if self.start_time is not None:
            duration = time.time() - self.start_time
        else:
            duration = 0
            logger.warning("save_to_json called but start_time is None")
        
        output = {
            **self.metadata,
            "end_time": int(time.time()),
            "end_datetime": datetime.now().isoformat(),
            "duration": duration,
            "total_frames": self.frame_count,
            "avg_fps": self.frame_count / duration if duration > 0 else 0,
            "frames": self.frames
        }
        
        # Save to file
        with open(filepath, 'w') as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Saved recording to: {filepath}")
        return filepath
    
    def save_summary_csv(self, filepath: Optional[str] = None) -> str:
        """
        Save ENHANCED session summary to CSV with emotion metrics
        
        Args:
            filepath: Optional custom filepath
            
        Returns:
            Path to saved file
        """
        import csv
        
        session_id = self.session_id or f"session_unknown_{int(time.time())}"
        
        if filepath is None:
            filepath = f"recordings/{session_id}_summary.csv"
        
        # Extract enhanced summary data
        rows = []
        for frame in self.frames:
            body_parts = frame.get("bodyParts", {}) or {}
            pose = frame.get("pose", {})
            hands = frame.get("hands", {})
            face_mesh = frame.get("faceMesh", {})
            metadata = frame.get("metadata", {})
            
            # Helper function to safely get confidence
            def get_confidence(part_name):
                part = body_parts.get(part_name)
                if part and isinstance(part, dict):
                    return round(part.get("confidence", 0), 2)
                return 0
            
            # Count landmarks
            pose_landmarks = pose.get("landmarks", [])
            hand_landmarks = hands.get("landmarks", [])
            face_landmarks = face_mesh.get("landmarks", [])
            
            pose_count = len(pose_landmarks) if pose_landmarks else 0
            hands_count = sum(len(h) for h in hand_landmarks) if hand_landmarks else 0
            face_count = sum(len(f) for f in face_landmarks) if face_landmarks else 0
            
            # Calculate emotion indicators from face mesh
            smile_score = 0
            eye_openness_left = 0
            eye_openness_right = 0
            eyebrow_height = 0
            mouth_openness = 0
            face_detected = "No"
            
            if face_landmarks and len(face_landmarks) > 0:
                face = face_landmarks[0]
                face_detected = "Yes"
                
                if len(face) >= 478:  # Full face mesh with refinement
                    # Smile score (mouth corners)
                    # Landmark 61: left mouth corner, 291: right mouth corner
                    # Landmark 13: upper lip, 14: lower lip
                    try:
                        mouth_left = face[61] if len(face) > 61 else None
                        mouth_right = face[291] if len(face) > 291 else None
                        upper_lip = face[13] if len(face) > 13 else None
                        lower_lip = face[14] if len(face) > 14 else None
                        
                        if mouth_left and mouth_right:
                            mouth_width = abs(mouth_right['x'] - mouth_left['x'])
                            if upper_lip and lower_lip:
                                mouth_height = abs(lower_lip['y'] - upper_lip['y'])
                                if mouth_height > 0:
                                    smile_score = round((mouth_width / mouth_height) * 100, 2)
                        
                        # Eye openness (vertical distance)
                        # Left eye: 159 (top), 145 (bottom)
                        # Right eye: 386 (top), 374 (bottom)
                        left_eye_top = face[159] if len(face) > 159 else None
                        left_eye_bottom = face[145] if len(face) > 145 else None
                        right_eye_top = face[386] if len(face) > 386 else None
                        right_eye_bottom = face[374] if len(face) > 374 else None
                        
                        if left_eye_top and left_eye_bottom:
                            eye_openness_left = round(abs(left_eye_bottom['y'] - left_eye_top['y']) * 1000, 2)
                        
                        if right_eye_top and right_eye_bottom:
                            eye_openness_right = round(abs(right_eye_bottom['y'] - right_eye_top['y']) * 1000, 2)
                        
                        # Eyebrow height (inner eyebrow to eye)
                        # Left eyebrow inner: 55, Left eye top: 159
                        left_brow = face[55] if len(face) > 55 else None
                        if left_brow and left_eye_top:
                            eyebrow_height = round((left_eye_top['y'] - left_brow['y']) * 1000, 2)
                        
                        # Mouth openness
                        if upper_lip and lower_lip:
                            mouth_openness = round(abs(lower_lip['y'] - upper_lip['y']) * 1000, 2)
                    
                    except (KeyError, TypeError, IndexError) as e:
                        logger.debug(f"Error calculating emotion metrics: {e}")
            
            # Build comprehensive row
            row = {
                # Basic info
                "frame_number": frame.get("frame_number", 0),
                "timestamp": round(frame.get("timestamp", 0), 3),
                
                # Body parts confidence
                "head_conf": get_confidence("head"),
                "left_hand_conf": get_confidence("leftHand"),
                "right_hand_conf": get_confidence("rightHand"),
                "upper_body_conf": get_confidence("upperBody"),
                "lower_body_conf": get_confidence("lowerBody"),
                "parts_detected": len([p for p in body_parts.values() if p and isinstance(p, dict)]),
                
                # Landmark counts
                "pose_landmarks": pose_count,
                "hand_landmarks": hands_count,
                "face_landmarks": face_count,
                
                # Face detection
                "face_detected": face_detected,
                
                # Emotion indicators (from face mesh)
                "smile_score": smile_score,
                "eye_open_left": eye_openness_left,
                "eye_open_right": eye_openness_right,
                "eyebrow_height": eyebrow_height,
                "mouth_open": mouth_openness,
                
                # Metadata
                "fps": round(metadata.get("fps", 0), 1),
            }
            rows.append(row)
        
        # Write CSV
        if rows:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            
            logger.info(f"Saved ENHANCED summary CSV to: {filepath}")
        
        return filepath
    
    def export_to_json(self, session_id: Optional[str] = None, output_dir: str = "recordings") -> str:
        """
        Export session data from database to JSON file
        
        Args:
            session_id: Session ID to export (uses current if None)
            output_dir: Output directory for JSON file
            
        Returns:
            Path to exported JSON file
        """
        if session_id is None:
            session_id = self.session_id
        
        if not session_id:
            raise ValueError("No session_id provided and no active session")
        
        if not self.db_session:
            raise ValueError("Database session required for export")
        
        try:
            from src.custom_live_ai.models.database import Frame, SessionTimeline, Session as DBSession
            
            # Query session record
            db_session_record = self.db_session.query(DBSession).filter(
                DBSession.session_id == session_id
            ).first()
            
            if not db_session_record:
                raise ValueError(f"Session {session_id} not found in database")
            
            # Query all frames
            frames = self.db_session.query(Frame).filter(
                Frame.session_id == session_id
            ).order_by(Frame.frame_number).all()
            
            # Query timeline events
            timeline_events = self.db_session.query(SessionTimeline).filter(
                SessionTimeline.session_id == session_id
            ).order_by(SessionTimeline.timestamp).all()
            
            # Build frame data
            frame_data = []
            for frame in frames:
                frame_data.append({
                    "frame_number": frame.frame_number,
                    "timestamp": frame.timestamp,
                    "bodyParts": frame.body_parts or {},
                    "pose": frame.pose_landmarks or {"landmarks": []},
                    "hands": frame.hand_landmarks or {"landmarks": [], "handedness": []},
                    "faceMesh": frame.face_mesh_landmarks or {"landmarks": []},
                    "emotion": frame.emotion_data or {"label": "Neutral", "emoji": "😐", "confidence": 0, "scores": {}},
                    "metadata": frame.frame_metadata or {}
                })
            
            # Build timeline data
            emotion_timeline = []
            posture_events = []
            intervention_triggers = []
            
            for event in timeline_events:
                if event.event_type == "emotion":
                    emotion_timeline.append({
                        "timestamp": event.timestamp,
                        "emotion": event.data.get("emotion", "unknown"),
                        "confidence": event.data.get("confidence", 0)
                    })
                elif event.event_type == "posture":
                    posture_events.append({
                        "timestamp": event.timestamp,
                        "event_type": event.data.get("event_type", "unknown"),
                        "severity": event.data.get("severity", 0)
                    })
                elif event.event_type == "intervention":
                    intervention_triggers.append({
                        "timestamp": event.timestamp,
                        "trigger_type": event.data.get("trigger_type", "unknown")
                    })
            
            # Build complete JSON structure
            output = {
                "session_id": session_id,
                "start_time": int(db_session_record.start_time.timestamp()) if db_session_record.start_time else 0,
                "start_datetime": db_session_record.start_time.isoformat() if db_session_record.start_time else "",
                "end_time": int(db_session_record.end_time.timestamp()) if db_session_record.end_time else 0,
                "end_datetime": db_session_record.end_time.isoformat() if db_session_record.end_time else "",
                "duration": db_session_record.duration or 0,
                "total_frames": db_session_record.total_frames or len(frame_data),
                "avg_fps": db_session_record.avg_fps or 0,
                "version": "2.2",
                "type": "detailed_body_part_detection",
                "data_source": "database",
                "frames": frame_data,
                "emotion_timeline": emotion_timeline,
                "posture_events": posture_events,
                "intervention_triggers": intervention_triggers
            }
            
            # Save to file
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, f"{session_id}_detailed.json")
            
            with open(filepath, 'w') as f:
                json.dump(output, f, indent=2)
            
            logger.info(f"✅ Exported session {session_id} from database to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export session to JSON: {e}")
            raise
    
    def detect_emotion_change(
        self,
        current_emotion: str,
        confidence: float,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Detect if emotion has changed significantly
        
        Args:
            current_emotion: Current detected emotion
            confidence: Confidence of current emotion
            timestamp: Frame timestamp (optional)
            
        Returns:
            True if emotion changed, False otherwise
        """
        if timestamp is None:
            timestamp = time.time() - self.start_time if self.start_time else 0
        
        # Check for change
        emotion_changed = False
        if self.last_emotion is None:
            # First emotion counts as a change
            emotion_changed = True
            logger.debug(f"First emotion detected: {current_emotion}")
        elif self.last_emotion != current_emotion:
            emotion_changed = True
            logger.debug(f"Emotion changed: {self.last_emotion} -> {current_emotion}")
        
        # Only record in timeline if emotion changed
        if emotion_changed:
            self.emotion_timeline.append({
                "timestamp": timestamp,
                "emotion": current_emotion,
                "confidence": confidence
            })
        
        self.last_emotion = current_emotion
        return emotion_changed
    
    def detect_posture_decline(
        self,
        posture_quality: str,
        is_slouching: bool,
        timestamp: Optional[float] = None
    ) -> bool:
        """
        Detect posture decline or poor posture event
        
        Args:
            posture_quality: Posture quality ("excellent", "good", "fair", "poor")
            is_slouching: Whether user is currently slouching
            timestamp: Frame timestamp (optional)
            
        Returns:
            True if posture declined, False otherwise
        """
        if timestamp is None:
            timestamp = time.time() - self.start_time if self.start_time else 0
        
        # Map quality to severity (higher = worse)
        quality_to_severity = {
            "excellent": 0.0,
            "good": 0.3,
            "fair": 0.6,
            "poor": 1.0
        }
        severity = quality_to_severity.get(posture_quality, 0.5)
        
        # Record event
        event_type = "slouch" if is_slouching else posture_quality.lower() + "_posture"
        self.posture_events.append({
            "timestamp": timestamp,
            "event_type": event_type,
            "severity": severity
        })
        
        # Check for decline
        posture_declined = False
        if self.last_posture_quality is not None:
            last_severity = quality_to_severity.get(self.last_posture_quality, 0.5)
            if severity > last_severity:  # Severity increased = posture worsened
                posture_declined = True
                logger.debug(f"Posture declined: {self.last_posture_quality} -> {posture_quality}")
        
        self.last_posture_quality = posture_quality
        return posture_declined
    
    def add_intervention_trigger(self, trigger_type: str, timestamp: Optional[float] = None):
        """
        Record an intervention trigger
        
        Args:
            trigger_type: Type of intervention triggered
            timestamp: Trigger timestamp (optional)
        """
        if timestamp is None:
            timestamp = time.time() - self.start_time if self.start_time else 0
        
        self.intervention_triggers.append({
            "timestamp": timestamp,
            "trigger_type": trigger_type
        })
        logger.debug(f"Intervention triggered: {trigger_type}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current recording status with real-time metrics"""
        return {
            "is_recording": self.is_recording,
            "session_id": self.session_id,
            "frames_recorded": self.frame_count,
            "duration": time.time() - self.start_time if self.is_recording else 0,
            "emotion_changes": len(self.emotion_timeline),
            "posture_events": len(self.posture_events),
            "interventions_triggered": len(self.intervention_triggers)
        }

