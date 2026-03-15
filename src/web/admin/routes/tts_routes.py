"""
TTS Console Routes for Admin Panel
==================================

Provides admin interface for testing Edge TTS service.
Uses Microsoft Edge TTS for Hong Kong Cantonese and English speech synthesis.

Selected Voices:
- Cantonese: zh-HK-HiuMaanNeural (Female)
- English: en-US-AvaNeural (Female)
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import io

from ....core.logging import get_logger
from ....custom_live_ai.audio.edge_tts_service import get_tts_service, EdgeTTSService

logger = get_logger(__name__)

# Router
tts_router = APIRouter(prefix="/tts", tags=["TTS Console"])


class TTSTestRequest(BaseModel):
    """TTS test synthesis request"""
    text: str = Field(..., min_length=1, max_length=1000)
    language: str = Field(default="yue")  # yue for Cantonese, en for English


# =============================================================================
# TTS Console Page
# =============================================================================

@tts_router.get("/console", response_class=HTMLResponse)
async def tts_console_page():
    """Render TTS Console page"""
    return HTMLResponse(content=TTS_CONSOLE_HTML)


# =============================================================================
# API Endpoints
# =============================================================================

@tts_router.get("/api/status")
async def get_tts_status():
    """Get Edge TTS service status"""
    try:
        service = get_tts_service()
        voices = service.get_voices()
        return JSONResponse(content={
            "status": "healthy",
            "service": "Edge TTS",
            "voices": voices,
            "message": "Edge TTS is ready (no server required)"
        })
    except Exception as e:
        logger.error(f"TTS status check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )


@tts_router.get("/api/voices")
async def get_tts_voices():
    """Get available TTS voices"""
    try:
        service = get_tts_service()
        voices = service.get_voices()
        return JSONResponse(content={
            "voices": voices,
            "cantonese": EdgeTTSService.CANTONESE_VOICE,
            "english": EdgeTTSService.ENGLISH_VOICE
        })
    except Exception as e:
        logger.error(f"Failed to get voices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@tts_router.post("/api/test")
async def test_tts_synthesis(request: TTSTestRequest):
    """Test TTS synthesis and return audio (MP3)"""
    try:
        service = get_tts_service()
        result = await service.synthesize(
            text=request.text,
            language=request.language
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error_message)
        
        return StreamingResponse(
            io.BytesIO(result.audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=tts_test.mp3",
                "X-Audio-Length-Seconds": str(result.audio_length_seconds)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@tts_router.post("/api/synthesize")
async def synthesize_speech(request: TTSTestRequest):
    """Synthesize speech - main endpoint for frontend integration"""
    try:
        service = get_tts_service()
        result = await service.synthesize(
            text=request.text,
            language=request.language
        )
        
        if not result.success:
            raise HTTPException(status_code=500, detail=result.error_message)
        
        return StreamingResponse(
            io.BytesIO(result.audio_data),
            media_type="audio/mpeg",
            headers={
                "X-Audio-Length-Seconds": str(result.audio_length_seconds)
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# TTS Console HTML Template
# =============================================================================

TTS_CONSOLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS Console - Healthcare AI Admin</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        :root { --primary: #1d8fe3; --success: #10b981; }
        body { background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); min-height: 100vh; }
        .card { border: none; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
        .card-header { background: linear-gradient(135deg, var(--primary), #0ea5e9); color: white; border-radius: 16px 16px 0 0 !important; padding: 1rem 1.5rem; }
        .status-badge { padding: 0.5rem 1rem; border-radius: 50px; font-weight: 600; display: inline-flex; align-items: center; gap: 0.5rem; }
        .status-healthy { background: rgba(16, 185, 129, 0.15); color: var(--success); }
        .voice-info { background: rgba(29, 143, 227, 0.08); border-radius: 12px; padding: 1rem; }
        .form-control, .form-select { border-radius: 10px; border: 2px solid #e2e8f0; padding: 0.75rem 1rem; }
        .form-control:focus, .form-select:focus { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(29, 143, 227, 0.15); }
        .btn-primary { background: linear-gradient(135deg, var(--primary), #0ea5e9); border: none; border-radius: 10px; padding: 0.75rem 1.5rem; font-weight: 600; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(29, 143, 227, 0.3); }
        .audio-player { width: 100%; margin-top: 1rem; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; }
        .metric-card { background: white; border-radius: 12px; padding: 1rem; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }
        .metric-value { font-size: 1.5rem; font-weight: 700; color: var(--primary); }
        .metric-label { font-size: 0.85rem; color: #64748b; }
        .loading-spinner { display: none; width: 1.5rem; height: 1.5rem; border: 3px solid #e2e8f0; border-top-color: var(--primary); border-radius: 50%; animation: spin 1s linear infinite; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container py-4">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="h3 mb-1">🔊 TTS Console</h1>
                <p class="text-muted mb-0">Edge TTS - Hong Kong Cantonese & English</p>
            </div>
            <a href="/admin/" class="btn btn-outline-secondary"><i class="bi bi-arrow-left"></i> Back to Admin</a>
        </div>
        <div class="row g-4">
            <div class="col-lg-6">
                <div class="card h-100">
                    <div class="card-header"><h5 class="mb-0"><i class="bi bi-activity"></i> Service Status</h5></div>
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <span id="statusBadge" class="status-badge status-healthy"><i class="bi bi-circle-fill"></i><span id="statusText">Ready</span></span>
                            <button class="btn btn-sm btn-outline-primary" onclick="refreshStatus()"><i class="bi bi-arrow-clockwise"></i> Refresh</button>
                        </div>
                        <div class="voice-info">
                            <h6 class="mb-3"><i class="bi bi-mic"></i> Selected Voices</h6>
                            <div class="row">
                                <div class="col-6"><small class="text-muted">Cantonese (粵語)</small><div class="fw-bold">zh-HK-HiuMaanNeural</div><small class="text-success">Female</small></div>
                                <div class="col-6"><small class="text-muted">English</small><div class="fw-bold">en-US-AvaNeural</div><small class="text-success">Female</small></div>
                            </div>
                        </div>
                        <div class="mt-3"><small class="text-muted"><i class="bi bi-info-circle"></i> Edge TTS is free, no API key required</small></div>
                    </div>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="card h-100">
                    <div class="card-header"><h5 class="mb-0"><i class="bi bi-play-circle"></i> Voice Tester</h5></div>
                    <div class="card-body">
                        <form id="ttsForm" onsubmit="testTTS(event)">
                            <div class="mb-3"><label class="form-label">Text to Synthesize</label><textarea id="ttsText" class="form-control" rows="3" placeholder="你好，我係小星星，好高興認識你！">你好，我係小星星，好高興認識你！</textarea></div>
                            <div class="mb-3"><label class="form-label">Language</label><select id="ttsLanguage" class="form-select"><option value="yue" selected>Cantonese 粵語 (HiuMaan)</option><option value="en">English (Ava)</option></select></div>
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-primary flex-grow-1" id="synthesizeBtn"><span class="loading-spinner me-2" id="loadingSpinner"></span><i class="bi bi-play-fill"></i> Synthesize</button>
                                <button type="button" class="btn btn-outline-secondary" onclick="downloadAudio()" id="downloadBtn" disabled><i class="bi bi-download"></i></button>
                            </div>
                        </form>
                        <audio id="audioPlayer" class="audio-player" controls style="display: none;"></audio>
                        <div id="metrics" class="metrics-grid mt-3" style="display: none;">
                            <div class="metric-card"><div class="metric-value" id="audioLength">-</div><div class="metric-label">Audio Length</div></div>
                            <div class="metric-card"><div class="metric-value" id="genTime">-</div><div class="metric-label">Generation Time</div></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <div class="card mt-4">
            <div class="card-header"><h5 class="mb-0"><i class="bi bi-chat-quote"></i> Sample Texts</h5></div>
            <div class="card-body">
                <div class="row g-2">
                    <div class="col-md-6"><button class="btn btn-outline-primary w-100 text-start" onclick="setSampleText('你好，我係小星星，好高興認識你！', 'yue')">🇭🇰 你好，我係小星星，好高興認識你！</button></div>
                    <div class="col-md-6"><button class="btn btn-outline-primary w-100 text-start" onclick="setSampleText('Hello, I am your healthcare assistant. How can I help you today?', 'en')">🇺🇸 Hello, I am your healthcare assistant...</button></div>
                    <div class="col-md-6"><button class="btn btn-outline-primary w-100 text-start" onclick="setSampleText('今日天氣好好，記得飲多啲水，保持身體健康！', 'yue')">🇭🇰 今日天氣好好，記得飲多啲水...</button></div>
                    <div class="col-md-6"><button class="btn btn-outline-primary w-100 text-start" onclick="setSampleText('Take a deep breath and relax. Everything will be okay.', 'en')">🇺🇸 Take a deep breath and relax...</button></div>
                </div>
            </div>
        </div>
    </div>
    <script>
        let currentAudioBlob = null;
        document.addEventListener('DOMContentLoaded', () => { refreshStatus(); });
        async function refreshStatus() {
            try {
                const response = await fetch('/admin/tts/api/status');
                const data = await response.json();
                document.getElementById('statusBadge').className = 'status-badge status-healthy';
                document.getElementById('statusText').textContent = data.status === 'healthy' ? 'Ready' : data.status;
            } catch (error) { console.error('Status check failed:', error); }
        }
        function setSampleText(text, language) {
            document.getElementById('ttsText').value = text;
            document.getElementById('ttsLanguage').value = language;
        }
        async function testTTS(event) {
            event.preventDefault();
            const btn = document.getElementById('synthesizeBtn');
            const spinner = document.getElementById('loadingSpinner');
            const audioPlayer = document.getElementById('audioPlayer');
            const metrics = document.getElementById('metrics');
            const downloadBtn = document.getElementById('downloadBtn');
            btn.disabled = true;
            spinner.style.display = 'inline-block';
            const startTime = performance.now();
            try {
                const response = await fetch('/admin/tts/api/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: document.getElementById('ttsText').value, language: document.getElementById('ttsLanguage').value })
                });
                const genTime = ((performance.now() - startTime) / 1000).toFixed(2);
                if (response.ok) {
                    currentAudioBlob = await response.blob();
                    const audioUrl = URL.createObjectURL(currentAudioBlob);
                    audioPlayer.src = audioUrl;
                    audioPlayer.style.display = 'block';
                    audioPlayer.play();
                    const audioLength = parseFloat(response.headers.get('X-Audio-Length-Seconds') || '0');
                    document.getElementById('audioLength').textContent = audioLength.toFixed(2) + 's';
                    document.getElementById('genTime').textContent = genTime + 's';
                    metrics.style.display = 'grid';
                    downloadBtn.disabled = false;
                } else {
                    const error = await response.json();
                    alert('TTS Error: ' + (error.detail || 'Unknown error'));
                }
            } catch (error) { console.error('TTS test failed:', error); alert('TTS Error: ' + error.message); }
            finally { btn.disabled = false; spinner.style.display = 'none'; }
        }
        function downloadAudio() {
            if (!currentAudioBlob) return;
            const url = URL.createObjectURL(currentAudioBlob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'tts_test.mp3';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }
    </script>
</body>
</html>
"""
