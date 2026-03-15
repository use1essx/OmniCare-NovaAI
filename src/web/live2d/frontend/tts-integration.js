/**
 * Edge TTS Integration Module
 * ===========================
 * Integrates Edge TTS with Live2D chatbox for Hong Kong Cantonese
 * and English speech synthesis.
 * 
 * Selected Voices:
 * - Cantonese: zh-HK-HiuMaanNeural (Female)
 * - English: en-US-AvaNeural (Female)
 * 
 * Features:
 * - Edge TTS API integration (via backend)
 * - Audio queue for sequential playback
 * - Lip sync with Live2D avatar
 * - Language auto-detection
 * - Web Speech API fallback
 * - User preference persistence
 */

// =============================================================================
// AUDIO QUEUE CLASS
// =============================================================================

class AudioQueue {
    constructor() {
        this.queue = [];
        this.isPlaying = false;
        this.currentAudio = null;
        this.onPlayStart = null;
        this.onPlayEnd = null;
        this.onError = null;
    }

    enqueue(audioBlob, metadata = {}) {
        this.queue.push({ audioBlob, metadata });
        if (!this.isPlaying) {
            this.processQueue();
        }
    }

    async processQueue() {
        if (this.queue.length === 0) {
            this.isPlaying = false;
            return;
        }

        this.isPlaying = true;
        const item = this.queue.shift();

        try {
            await this.playAudio(item.audioBlob, item.metadata);
        } catch (error) {
            console.error('AudioQueue: Playback error', error);
            if (this.onError) this.onError(error);
        }

        this.processQueue();
    }

    playAudio(audioBlob, metadata) {
        return new Promise((resolve, reject) => {
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            this.currentAudio = audio;

            audio.volume = metadata.volume || 1.0;

            audio.onplay = () => {
                if (this.onPlayStart) this.onPlayStart(audio, metadata);
            };

            audio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                this.currentAudio = null;
                if (this.onPlayEnd) this.onPlayEnd(metadata);
                resolve();
            };

            audio.onerror = (e) => {
                URL.revokeObjectURL(audioUrl);
                this.currentAudio = null;
                reject(e);
            };

            audio.play().catch(reject);
        });
    }

    stop() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        this.queue = [];
        this.isPlaying = false;
    }

    get length() {
        return this.queue.length;
    }
}

// =============================================================================
// LIP SYNC CONTROLLER
// =============================================================================

class LipSyncController {
    constructor() {
        this.audioContext = null;
        this.analyser = null;
        this.animationFrame = null;
        this.live2dModel = null;
        this.smoothing = 0.3;
        this.lastValue = 0;
    }

    setLive2DModel(model) {
        this.live2dModel = model;
    }

    startLipSync(audioElement) {
        if (!this.live2dModel) {
            console.warn('LipSyncController: No Live2D model set');
            return;
        }

        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }

            if (this.audioContext.state === 'suspended') {
                this.audioContext.resume();
            }

            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = 0.8;

            const source = this.audioContext.createMediaElementSource(audioElement);
            source.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);

            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            this.animate();
        } catch (error) {
            console.error('LipSyncController: Error starting lip sync', error);
        }
    }

    animate() {
        if (!this.analyser || !this.live2dModel) return;

        this.animationFrame = requestAnimationFrame(() => this.animate());

        this.analyser.getByteFrequencyData(this.dataArray);

        const voiceStart = Math.floor(100 / (this.audioContext.sampleRate / this.analyser.fftSize));
        const voiceEnd = Math.floor(3000 / (this.audioContext.sampleRate / this.analyser.fftSize));
        
        let sum = 0;
        for (let i = voiceStart; i < voiceEnd && i < this.dataArray.length; i++) {
            sum += this.dataArray[i];
        }
        const average = sum / (voiceEnd - voiceStart);

        const targetValue = Math.min(1, average / 128);
        this.lastValue = this.lastValue * this.smoothing + targetValue * (1 - this.smoothing);

        this.updateMouthParam(this.lastValue);
    }

    updateMouthParam(value) {
        if (window.updateLive2DMouthParam) {
            window.updateLive2DMouthParam(value);
        }
    }

    stopLipSync() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
            this.animationFrame = null;
        }
        this.lastValue = 0;
        this.updateMouthParam(0);
    }
}

// =============================================================================
// TTS INTEGRATION CLASS
// =============================================================================

class TTSIntegration {
    constructor(options = {}) {
        // Configuration - use backend Edge TTS endpoint
        this.ttsEndpoint = options.ttsEndpoint || '/admin/tts/api/synthesize';
        this.timeout = options.timeout || 30000;
        this.maxRetries = options.maxRetries || 1;

        // State
        this.enabled = localStorage.getItem('tts_enabled') !== 'false';
        this.volume = parseFloat(localStorage.getItem('tts_volume') || '1.0');
        this.isSpeaking = false;

        // Components
        this.audioQueue = new AudioQueue();
        this.lipSync = new LipSyncController();

        // Callbacks
        this.onSpeakStart = null;
        this.onSpeakEnd = null;
        this.onError = null;
        this.onFallback = null;

        // Setup audio queue callbacks
        this.audioQueue.onPlayStart = (audio, metadata) => {
            this.isSpeaking = true;
            this.lipSync.startLipSync(audio);
            if (this.onSpeakStart) this.onSpeakStart(metadata);
        };

        this.audioQueue.onPlayEnd = (metadata) => {
            this.isSpeaking = false;
            this.lipSync.stopLipSync();
            if (this.onSpeakEnd) this.onSpeakEnd(metadata);
        };

        this.audioQueue.onError = (error) => {
            this.isSpeaking = false;
            this.lipSync.stopLipSync();
            if (this.onError) this.onError(error);
        };

        console.log('TTSIntegration: Initialized with Edge TTS');
    }

    // =========================================================================
    // PUBLIC METHODS
    // =========================================================================

    /**
     * Speak text with auto language detection
     */
    async speak(text, language = 'auto') {
        if (!this.enabled) {
            console.log('TTSIntegration: TTS is disabled');
            return false;
        }

        if (!text || !text.trim()) {
            console.log('TTSIntegration: Empty text');
            return false;
        }

        // Detect language if auto
        const detectedLanguage = this.detectLanguage(text, language);

        console.log(`TTSIntegration: Speaking "${text.substring(0, 50)}..." | lang=${detectedLanguage}`);

        try {
            const audioBlob = await this.synthesize(text, detectedLanguage);

            if (audioBlob) {
                this.audioQueue.enqueue(audioBlob, {
                    text,
                    language: detectedLanguage,
                    volume: this.volume
                });
                return true;
            }
        } catch (error) {
            console.warn('TTSIntegration: Edge TTS failed, falling back to Web Speech API', error);
            if (this.onFallback) this.onFallback(error);
        }

        // Fallback to Web Speech API
        return this.speakWithWebSpeech(text, detectedLanguage);
    }

    /**
     * Stop current speech and clear queue
     */
    stop() {
        this.audioQueue.stop();
        this.lipSync.stopLipSync();
        this.isSpeaking = false;
        
        if (window.speechSynthesis) {
            window.speechSynthesis.cancel();
        }
    }

    /**
     * Enable/disable TTS
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        localStorage.setItem('tts_enabled', enabled.toString());
        if (!enabled) {
            this.stop();
        }
    }

    /**
     * Set volume (0-1)
     */
    setVolume(volume) {
        this.volume = Math.max(0, Math.min(1, volume));
        localStorage.setItem('tts_volume', this.volume.toString());
    }

    /**
     * Check TTS service status
     */
    async checkStatus() {
        try {
            const response = await fetch('/admin/tts/api/status', {
                method: 'GET',
                signal: AbortSignal.timeout(5000)
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`TTSIntegration: Edge TTS status - ${data.status}`);
                return data;
            }
        } catch (error) {
            console.warn('TTSIntegration: Status check failed', error.message);
        }
        return null;
    }

    // =========================================================================
    // PRIVATE METHODS
    // =========================================================================

    /**
     * Synthesize speech using Edge TTS backend
     */
    async synthesize(text, language) {
        let lastError = null;
        
        for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
            try {
                const response = await fetch(this.ttsEndpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, language }),
                    signal: AbortSignal.timeout(this.timeout)
                });

                if (response.ok) {
                    const audioBlob = await response.blob();
                    const audioLength = response.headers.get('X-Audio-Length-Seconds');
                    console.log(`TTSIntegration: Synthesized ${audioLength}s audio`);
                    return audioBlob;
                } else {
                    const errorText = await response.text();
                    lastError = new Error(`Edge TTS error: ${response.status} - ${errorText}`);
                }
            } catch (error) {
                lastError = error;
                if (attempt < this.maxRetries) {
                    console.log(`TTSIntegration: Retry ${attempt + 1}/${this.maxRetries}`);
                    await new Promise(r => setTimeout(r, 500));
                }
            }
        }

        throw lastError;
    }

    /**
     * Detect language from text
     */
    detectLanguage(text, preferredLanguage) {
        if (preferredLanguage === 'zh-HK' || preferredLanguage === 'yue' || preferredLanguage === 'cantonese') {
            return 'yue';
        }
        if (preferredLanguage === 'en' || preferredLanguage === 'english') {
            return 'en';
        }

        // Auto-detect: Chinese characters = Cantonese, else English
        const hasChinese = /[\u4e00-\u9fff]/.test(text);
        return hasChinese ? 'yue' : 'en';
    }

    /**
     * Fallback to Web Speech API
     */
    speakWithWebSpeech(text, language) {
        if (!window.speechSynthesis) {
            console.warn('TTSIntegration: Web Speech API not available');
            return false;
        }

        const utterance = new SpeechSynthesisUtterance(text);
        
        if (language === 'yue' || language === 'zh-HK') {
            utterance.lang = 'zh-HK';
        } else {
            utterance.lang = 'en-US';
        }

        utterance.volume = this.volume;
        utterance.rate = 0.9;

        utterance.onstart = () => {
            this.isSpeaking = true;
            if (this.onSpeakStart) this.onSpeakStart({ text, language, fallback: true });
        };

        utterance.onend = () => {
            this.isSpeaking = false;
            if (this.onSpeakEnd) this.onSpeakEnd({ text, language, fallback: true });
        };

        utterance.onerror = (e) => {
            this.isSpeaking = false;
            console.error('TTSIntegration: Web Speech API error', e);
        };

        window.speechSynthesis.speak(utterance);
        return true;
    }
}

// =============================================================================
// GLOBAL INSTANCE
// =============================================================================

window.ttsIntegration = null;

/**
 * Initialize TTS integration
 */
function initTTSIntegration(options = {}) {
    if (window.ttsIntegration) {
        console.log('TTSIntegration: Already initialized');
        return window.ttsIntegration;
    }

    window.ttsIntegration = new TTSIntegration(options);
    return window.ttsIntegration;
}

/**
 * Get TTS integration instance
 */
function getTTSIntegration() {
    if (!window.ttsIntegration) {
        return initTTSIntegration();
    }
    return window.ttsIntegration;
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        TTSIntegration,
        AudioQueue,
        LipSyncController,
        initTTSIntegration,
        getTTSIntegration
    };
}
