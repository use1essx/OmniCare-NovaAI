"""
Parquet logging for emotion detection data
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class ParquetLogger:
    """
    Writes per-frame emotion detection data to partitioned parquet files
    """
    
    def __init__(self, root: str = "./data/logs"):
        """
        Args:
            root: Root directory for parquet files
        """
        self.root = Path(root)
        self.buffer: List[Dict] = []
        self.buffer_size = 100  # Flush every 100 frames
        
    def log_frame(
        self,
        session_id: str,
        frame_idx: int,
        landmarks_468: np.ndarray,
        base_features: Dict[str, float],
        faceapi_emotions: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Log a single frame's data
        
        Args:
            session_id: Session identifier
            frame_idx: Frame index in session
            landmarks_468: Face landmarks array (468, 2) or (468, 3)
            base_features: Dictionary of extracted features
            faceapi_emotions: Optional face-api.js emotion scores
        """
        try:
            # Flatten landmarks to list for storage
            if isinstance(landmarks_468, np.ndarray):
                if landmarks_468.shape[0] == 468:
                    landmarks_flat = landmarks_468[:, :2].flatten().tolist()
                else:
                    landmarks_flat = []
            else:
                landmarks_flat = []
            
            record = {
                'timestamp': datetime.utcnow().isoformat(),
                'session_id': session_id,
                'frame_idx': frame_idx,
                'landmarks_468': json.dumps(landmarks_flat),  # Store as JSON string
                'base_features': json.dumps(base_features),
                'faceapi_emotions': json.dumps(faceapi_emotions) if faceapi_emotions else None
            }
            
            self.buffer.append(record)
            
            # Flush if buffer is full
            if len(self.buffer) >= self.buffer_size:
                self.flush()
                
        except Exception as e:
            logger.error(f"Error logging frame: {e}")
            
    def flush(self) -> None:
        """
        Write buffered records to parquet file
        """
        if not self.buffer:
            return
            
        try:
            # Create DataFrame
            df = pd.DataFrame(self.buffer)
            
            # Partition by date (YYYY/MM/DD)
            now = datetime.utcnow()
            partition_path = self.root / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"
            partition_path.mkdir(parents=True, exist_ok=True)
            
            # Generate filename with timestamp
            filename = f"emotion_log_{now.strftime('%H%M%S_%f')}.parquet"
            filepath = partition_path / filename
            
            # Write parquet (append mode)
            df.to_parquet(filepath, engine='pyarrow', compression='snappy', index=False)
            
            logger.debug(f"Flushed {len(self.buffer)} records to {filepath}")
            
            # Clear buffer
            self.buffer.clear()
            
        except Exception as e:
            logger.error(f"Error flushing parquet: {e}")
            # Clear buffer anyway to avoid memory issues
            self.buffer.clear()
            
    def close(self) -> None:
        """
        Flush remaining records and close logger
        """
        self.flush()


# Global logger instance (lazy initialization)
_global_logger: Optional[ParquetLogger] = None


def get_logger() -> ParquetLogger:
    """
    Get or create the global parquet logger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = ParquetLogger()
    return _global_logger

