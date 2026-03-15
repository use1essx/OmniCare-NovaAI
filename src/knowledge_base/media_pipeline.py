"""
Media ingestion pipeline for video/audio files:
- Extract audio (ffmpeg)
- Transcribe via STT server (existing Whisper service)
- Optional summarization via AI service
"""

import asyncio
import hashlib
import logging
import tempfile
import subprocess
from typing import List, Dict, Tuple, Optional

import httpx

from src.core.config import settings
from src.knowledge_base.document_ingestion import DocumentChunk

logger = logging.getLogger(__name__)


class MediaProcessingError(Exception):
    """Custom error for media processing."""


async def transcribe_audio_bytes(data: bytes, filename: str, language: str = "en-US") -> Dict:
    """Send audio bytes to the STT server and return JSON."""
    stt_url = settings.live2d_stt_service_url.rstrip("/") + "/stt/stream"
    files = {"audio": (filename, data, "audio/webm")}
    data_form = {"lang": language}
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(stt_url, files=files, data=data_form)
        resp.raise_for_status()
        return resp.json()


def extract_audio_with_ffmpeg(data: bytes, filename: str) -> bytes:
    """Extract mono 16k PCM WAV audio from input video/audio bytes."""
    try:
        with tempfile.NamedTemporaryFile(delete=True, suffix=filename) as src, \
             tempfile.NamedTemporaryFile(delete=True, suffix=".wav") as dst:
            src.write(data)
            src.flush()
            cmd = [
                "ffmpeg", "-y", "-i", src.name,
                "-ac", "1",
                "-ar", "16000",
                "-vn",
                "-acodec", "pcm_s16le",
                dst.name
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            dst.seek(0)
            return dst.read()
    except FileNotFoundError:
        raise MediaProcessingError("ffmpeg not installed")
    except subprocess.CalledProcessError:
        raise MediaProcessingError("ffmpeg failed to extract audio")


def probe_duration_seconds(data: bytes, filename: str) -> Optional[float]:
    """Return media duration in seconds using ffprobe if available."""
    try:
        with tempfile.NamedTemporaryFile(delete=True, suffix=filename) as src:
            src.write(data)
            src.flush()
            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                src.name,
            ]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
            return float(out)
    except Exception:
        return None


async def summarize_text(text: str, language: str = "en") -> str:
    """Lightweight summarization using existing AI service; fallback to truncation."""
    try:
        from src.ai.ai_service import get_ai_service

        ai = await get_ai_service()
        prompt = (
            "Summarize the following transcript in 3-5 concise sentences for retrieval. "
            "Keep clinical facts intact.\n\n" + text[:4000]
        )
        res = await ai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.2,
        )
        return res.get("content", "") or text[:400]
    except Exception as e:
        logger.warning(f"Summarization fallback: {e}")
        return text[:400]


async def process_media_for_kb(
    data: bytes,
    filename: str,
    language: str = "en-US",
    summary: bool = True,
    segment_seconds: int = 120,
    max_minutes: int = None,
) -> Tuple[str, List[DocumentChunk]]:
    """
    Process video/audio bytes to transcript and optional summary segments.

    Returns:
        doc_text: full transcript text
        chunks: list of DocumentChunk with timestamps (chunk_type transcript/summary)
    """
    # Enforce max length via duration estimate if provided
    if max_minutes:
        dur = probe_duration_seconds(data, filename)
        if dur and dur > max_minutes * 60:
            raise MediaProcessingError(f"Media too long (> {max_minutes} minutes)")
        if dur is None:
            # Fallback rough estimate: assume 160kbps audio -> 20KB/sec
            est_seconds = len(data) / 20000
            if est_seconds > max_minutes * 60:
                raise MediaProcessingError(f"Media too long (> {max_minutes} minutes, estimated)")

    audio_wav = extract_audio_with_ffmpeg(data, filename)

    stt_json = await transcribe_audio_bytes(audio_wav, filename, language)
    transcript = (stt_json.get("text") or "").strip()
    if not transcript:
        raise MediaProcessingError("No transcript returned from STT")

    # Build transcript chunks segmented by characters approximating time
    # (We don't have word timestamps from STT server; approximate by proportion)
    chunks: List[DocumentChunk] = []
    segment_chars = 2000  # rough segment size
    for i in range(0, len(transcript), segment_chars):
        seg = transcript[i : i + segment_chars]
        # Approximate timestamps by segment index * segment_seconds
        idx = i // segment_chars
        start_ts = idx * segment_seconds
        end_ts = start_ts + segment_seconds
        chunks.append(
            DocumentChunk(
                text=seg,
                index=idx,
                start_char=i,
                end_char=i + len(seg),
                chunk_type="transcript",
                page=None,
                timestamp_start=start_ts,
                timestamp_end=end_ts,
            )
        )

    if summary:
        summary_text = await summarize_text(transcript, language=language)
        chunks.append(
            DocumentChunk(
                text=summary_text,
                index=len(chunks),
                start_char=0,
                end_char=len(summary_text),
                chunk_type="summary",
                page=None,
                timestamp_start=0.0,
                timestamp_end=float(len(chunks) * segment_seconds),
            )
        )

    return transcript, chunks
