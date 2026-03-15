/**
 * Smart Voice Input System for Healthcare AI Live2D
 * 
 * Features:
 * - Hybrid STT engine (Web Speech API + Whisper fallback)
 * - Smart speech end detection (2s pause, 3s silence threshold)
 * - Direct voice-to-AI transmission (no input box)
 * - Mixed language support (Cantonese/English code-switching)
 * - Noise cancellation
 * - TTS coordination
 * 
 * @version 1.0.0
 */

// ============================================================================
// AUDIO PROCESSOR - Handles audio capture with noise cancellation
// ============================================================================

class AudioProcessor {
    constructor(config = {}) {
        this.config = {
            noiseSuppression: config.noiseSuppression !== false,
            echoCancellation: config.echoCancellation !== false,
            autoGainControl: config.autoGainControl !== false
        };
        this.stream = null;
        this.audioContext = null;
        this.analyser = null;
        this.noiseLevel = 0;
    }

    /**
     * Initialize audio capture with noise cancellation constraints
     * @returns {Promise<MediaStream>}
     */
    async initialize() {
        try {
            const constraints = {
                audio: {
                    echoCancellation: this.config.echoCancellation,
                    noiseSuppression: this.config.noiseSuppression,
                    autoGainControl: this.config.autoGainControl,
                    channelCount: 1,
                    sampleRate: 16000
                }
            };

            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            
            // Set up audio analysis for noise level detection
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(this.stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            source.connect(this.analyser);
            
            // Start noise level monitoring
            this._monitorNoiseLevel();
            
            console.log('[AudioProcessor] Initialized with noise cancellation');
            return this.stream;
        } catch (error) {
            console.error('[AudioProcessor] Failed to initialize:', error);
            throw error;
        }
    }

    /**
     * Monitor noise level continuously
     * @private
     */
    _monitorNoiseLevel() {
        if (!this.analyser) return;
        
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        
        const update = () => {
            if (!this.analyser) return;
            
            this.analyser.getByteFrequencyData(dataArray);
            const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
            this.noiseLevel = average / 255; // Normalize to 0-1
            
            requestAnimationFrame(update);
        };
        
        update();
    }

    /**
     * Get current noise level (0-1 scale)
     * @returns {number}
     */
    getNoiseLevel() {
        return this.noiseLevel;
    }

    /**
     * Check if noise level is too high
     * @param {number} threshold - Threshold value (default 0.7)
     * @returns {boolean}
     */
    isNoiseTooHigh(threshold = 0.7) {
        return this.noiseLevel > threshold;
    }

    /**
     * Clean up resources
     */
    destroy() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        this.analyser = null;
        console.log('[AudioProcessor] Destroyed');
    }
}


// ============================================================================
// SILENCE DETECTOR - Detects speech pauses and determines when to send
// ============================================================================

class SilenceDetector {
    constructor(config = {}) {
        this.config = {
            pauseThreshold: config.pauseThreshold || 2000,    // Show "Still listening..." (ms)
            silenceThreshold: config.silenceThreshold || 3000  // Send message (ms)
        };
        
        this.lastSpeechTime = null;
        this.pauseTimer = null;
        this.silenceTimer = null;
        this.isPaused = false;
        
        // Callbacks
        this.onPauseDetected = config.onPauseDetected || (() => {});
        this.onSilenceComplete = config.onSilenceComplete || (() => {});
        this.onSpeechResumed = config.onSpeechResumed || (() => {});
    }

    /**
     * Called when speech is detected
     */
    onSpeechDetected() {
        this.lastSpeechTime = Date.now();
        
        // Clear existing timers
        this._clearTimers();
        
        // If we were paused, notify that speech resumed
        if (this.isPaused) {
            this.isPaused = false;
            this.onSpeechResumed();
        }
        
        // Start new timers
        this._startTimers();
    }

    /**
     * Start pause and silence detection timers
     * @private
     */
    _startTimers() {
        // Pause detection timer (2 seconds)
        this.pauseTimer = setTimeout(() => {
            this.isPaused = true;
            this.onPauseDetected();
        }, this.config.pauseThreshold);
        
        // Silence complete timer (3 seconds)
        this.silenceTimer = setTimeout(() => {
            this.onSilenceComplete();
        }, this.config.silenceThreshold);
    }

    /**
     * Clear all timers
     * @private
     */
    _clearTimers() {
        if (this.pauseTimer) {
            clearTimeout(this.pauseTimer);
            this.pauseTimer = null;
        }
        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
            this.silenceTimer = null;
        }
    }

    /**
     * Reset the detector
     */
    reset() {
        this._clearTimers();
        this.lastSpeechTime = null;
        this.isPaused = false;
    }

    /**
     * Update thresholds
     * @param {Object} config - New threshold values
     */
    updateConfig(config) {
        if (config.pauseThreshold) this.config.pauseThreshold = config.pauseThreshold;
        if (config.silenceThreshold) this.config.silenceThreshold = config.silenceThreshold;
    }
}

// ============================================================================
// WEB SPEECH ENGINE - Browser-native speech recognition
// ============================================================================

class WebSpeechEngine {
    constructor() {
        this.name = 'Web Speech API';
        this.recognition = null;
        this.isAvailable = this._checkAvailability();
        this.isListening = false;
        this.language = 'zh-HK';
        this.continuous = true;
        
        // Callbacks
        this.onResult = () => {};
        this.onError = () => {};
        this.onEnd = () => {};
        this.onSpeechStart = () => {};
    }

    /**
     * Check if Web Speech API is available
     * @private
     */
    _checkAvailability() {
        const hasAPI = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
        const hasMediaDevices = 'mediaDevices' in navigator && 'getUserMedia' in navigator.mediaDevices;
        
        console.log('[WebSpeechEngine] Checking availability - API:', hasAPI, 'MediaDevices:', hasMediaDevices);
        return hasAPI;
    }

    /**
     * Start speech recognition
     * @param {string} language - Language code (zh-HK, en-US, auto)
     */
    start(language = 'zh-HK') {
        if (!this.isAvailable) {
            this.onError({ code: 'no-web-speech', message: 'Web Speech API not available', recoverable: true });
            return;
        }

        // If already listening, don't start again
        if (this.isListening) {
            console.log('[WebSpeechEngine] Already listening, ignoring start request');
            return;
        }

        try {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            
            // Configuration
            // Use zh-HK for 'auto' mode as it handles code-switching well
            this.language = language === 'auto' ? 'zh-HK' : language;
            this.recognition.lang = this.language;
            this.recognition.continuous = this.continuous;
            this.recognition.interimResults = true;
            this.recognition.maxAlternatives = 1;

            // Event handlers
            this.recognition.onstart = () => {
                this.isListening = true;
                console.log('[WebSpeechEngine] Started listening in', this.language);
            };

            this.recognition.onspeechstart = () => {
                this.onSpeechStart();
            };

            this.recognition.onresult = (event) => {
                const result = event.results[event.results.length - 1];
                const transcript = result[0].transcript;
                const confidence = result[0].confidence || 0.9;
                
                this.onResult({
                    text: transcript,
                    isFinal: result.isFinal,
                    confidence: confidence,
                    language: this.language
                });
            };

            this.recognition.onerror = (event) => {
                console.error('[WebSpeechEngine] Error:', event.error);
                
                const errorMap = {
                    'no-speech': { code: 'no-speech', message: 'No speech detected', recoverable: true },
                    'audio-capture': { code: 'audio-error', message: 'Audio capture failed', recoverable: false },
                    'not-allowed': { code: 'mic-denied', message: 'Microphone permission denied', recoverable: false },
                    'network': { code: 'network-error', message: 'Network error', recoverable: true },
                    'aborted': { code: 'aborted', message: 'Recognition aborted', recoverable: true }
                };
                
                const error = errorMap[event.error] || { code: event.error, message: event.error, recoverable: true };
                this.onError(error);
            };

            this.recognition.onend = () => {
                this.isListening = false;
                console.log('[WebSpeechEngine] Ended');
                this.onEnd();
            };

            // Add a more specific check for user interaction requirement
            const startAttempt = () => {
                try {
                    this.recognition.start();
                } catch (error) {
                    console.error('[WebSpeechEngine] Failed to start:', error);
                    // If it's an "already started" error, just ignore it
                    if (error.message && error.message.includes('already')) {
                        console.log('[WebSpeechEngine] Recognition already started, ignoring error');
                        this.isListening = true;
                    } else if (error.name === 'NotAllowedError' || (error.message && error.message.includes('not-allowed'))) {
                        // Handle explicit permission denied errors
                        console.error('[WebSpeechEngine] Microphone permission denied:', error);
                        this.onError({ 
                            code: 'mic-denied', 
                            message: 'Microphone access denied. Please allow microphone access in browser settings.', 
                            recoverable: false 
                        });
                    } else {
                        this.onError({ code: 'start-error', message: error.message, recoverable: true });
                    }
                }
            };
            
            // Try to start the recognition
            startAttempt();
        } catch (error) {
            console.error('[WebSpeechEngine] Unexpected error starting:', error);
            this.onError({ code: 'start-error', message: error.message, recoverable: true });
        }
    }

    /**
     * Stop speech recognition
     */
    stop() {
        if (this.recognition) {
            try {
                this.recognition.stop();
                this.isListening = false;
            } catch (error) {
                console.warn('[WebSpeechEngine] Error stopping recognition:', error);
            }
        }
    }

    /**
     * Abort speech recognition immediately
     */
    abort() {
        if (this.recognition) {
            try {
                this.recognition.abort();
                this.isListening = false;
            } catch (error) {
                console.warn('[WebSpeechEngine] Error aborting recognition:', error);
            }
        }
    }
}
    }

    /**
     * Check if Web Speech API is available
     * @private
     */
    _checkAvailability() {
        // More comprehensive check for availability
        const hasAPI = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
        const hasMediaDevices = 'mediaDevices' in navigator && 'getUserMedia' in navigator.mediaDevices;
        
        console.log('[WebSpeechEngine] Checking availability - API:', hasAPI, 'MediaDevices:', hasMediaDevices);
        
        return hasAPI;
    }

    /**
     * Start speech recognition
     * @param {string} language - Language code (zh-HK, en-US, auto)
     */
    start(language = 'zh-HK') {
        if (!this.isAvailable) {
            this.onError({ code: 'no-web-speech', message: 'Web Speech API not available', recoverable: true });
            return;
        }

        // If already listening, don't start again
        if (this.isListening) {
            console.log('[WebSpeechEngine] Already listening, ignoring start request');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        // Configuration
        // Use zh-HK for 'auto' mode as it handles code-switching well
        this.language = language === 'auto' ? 'zh-HK' : language;
        this.recognition.lang = this.language;
        this.recognition.continuous = this.continuous;
        this.recognition.interimResults = true;
        this.recognition.maxAlternatives = 1;

        // Event handlers
        this.recognition.onstart = () => {
            this.isListening = true;
            console.log('[WebSpeechEngine] Started listening in', this.language);
        };

        this.recognition.onspeechstart = () => {
            this.onSpeechStart();
        };

        this.recognition.onresult = (event) => {
            const result = event.results[event.results.length - 1];
            const transcript = result[0].transcript;
            const confidence = result[0].confidence || 0.9;
            
            this.onResult({
                text: transcript,
                isFinal: result.isFinal,
                confidence: confidence,
                language: this.language
            });
        };

        this.recognition.onerror = (event) => {
            console.error('[WebSpeechEngine] Error:', event.error);
            
            const errorMap = {
                'no-speech': { code: 'no-speech', message: 'No speech detected', recoverable: true },
                'audio-capture': { code: 'audio-error', message: 'Audio capture failed', recoverable: false },
                'not-allowed': { code: 'mic-denied', message: 'Microphone permission denied', recoverable: false },
                'network': { code: 'network-error', message: 'Network error', recoverable: true },
                'aborted': { code: 'aborted', message: 'Recognition aborted', recoverable: true }
            };
            
            const error = errorMap[event.error] || { code: event.error, message: event.error, recoverable: true };
            this.onError(error);
        };

        this.recognition.onend = () => {
            this.isListening = false;
            console.log('[WebSpeechEngine] Ended');
            this.onEnd();
        };

try {
            this.recognition.start();
        } catch (error) {
            console.error('[WebSpeechEngine] Failed to start:', error);
            // If it's an "already started" error, just ignore it
            if (error.message && error.message.includes('already')) {
                console.log('[WebSpeechEngine] Recognition already started, ignoring error');
                this.isListening = true;
            } else if (error.name === 'NotAllowedError' || (error.message && error.message.includes('not-allowed'))) {
                // Handle explicit permission denied errors
                console.error('[WebSpeechEngine] Microphone permission denied:', error);
                this.onError({ 
                    code: 'mic-denied', 
                    message: 'Microphone access denied. Please allow microphone access in browser settings.', 
                    recoverable: false 
                });
            } else {
                this.onError({ code: 'start-error', message: error.message, recoverable: true });
            }
        }
    }

    /**
     * Stop speech recognition
     */
    stop() {
        if (this.recognition) {
            this.recognition.stop();
            this.isListening = false;
        }
    }

    /**
     * Abort speech recognition immediately
     */
    abort() {
        if (this.recognition) {
            this.recognition.abort();
            this.isListening = false;
        }
    }
}


// ============================================================================
// WHISPER ENGINE - Server-side speech recognition fallback
// ============================================================================

class WhisperEngine {
    constructor() {
        this.name = 'Whisper (Private)';
        this.isAvailable = true; // Assume available, will fail gracefully
        this.isListening = false;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.stream = null;
        this.language = 'zh-HK';
        
        // Callbacks
        this.onResult = () => {};
        this.onError = () => {};
        this.onEnd = () => {};
        this.onSpeechStart = () => {};
    }

    /**
     * Start recording for Whisper processing
     * @param {string} language - Language code
     */
    async start(language = 'zh-HK') {
        this.language = language === 'auto' ? 'zh' : language;
        
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') 
                ? 'audio/webm;codecs=opus' 
                : 'audio/webm';
            
            this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = async () => {
                await this._processAudio();
            };

            this.mediaRecorder.onerror = (event) => {
                console.error('[WhisperEngine] MediaRecorder error:', event.error);
                this.onError({ code: 'recorder-error', message: 'Recording failed', recoverable: true });
            };

            // Add explicit user interaction check before starting
            if (this.mediaRecorder && typeof this.mediaRecorder.start === 'function') {
                this.mediaRecorder.start(1000); // Collect data every second
                this.isListening = true;
                this.onSpeechStart();
                
                console.log('[WhisperEngine] Started recording');
            } else {
                throw new Error('MediaRecorder not properly initialized or start() method not available');
            }
        } catch (error) {
            console.error('[WhisperEngine] Failed to start:', error);
            if (error.name === 'NotAllowedError') {
                this.onError({ code: 'mic-denied', message: 'Microphone permission denied', recoverable: false });
            } else if (error.name === 'NotFoundError' || error.message.includes('media')) {
                this.onError({ code: 'no-microphone', message: 'No microphone found', recoverable: false });
            } else {
                this.onError({ code: 'audio-error', message: error.message, recoverable: false });
            }
        }
    }

    /**
     * Stop recording and process audio
     */
    stop() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            try {
                this.mediaRecorder.stop();
                this.isListening = false;
            } catch (error) {
                console.warn('[WhisperEngine] Error stopping recorder:', error);
                this.isListening = false;
            }
        }
    }

    /**
     * Abort recording without processing
     */
    abort() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            try {
                this.mediaRecorder.stop();
            } catch (error) {
                console.warn('[WhisperEngine] Error aborting recorder:', error);
            }
        }
        this._cleanup();
        this.isListening = false;
        this.onEnd();
    }

    /**
     * Process recorded audio through Whisper backend
     * @private
     */
    async _processAudio() {
        if (this.audioChunks.length === 0) {
            this.onError({ code: 'no-audio', message: 'No audio recorded', recoverable: true });
            this._cleanup();
            this.onEnd();
            return;
        }

        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
        
        try {
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            formData.append('lang', this.language);

            // Add a timeout to prevent hanging requests
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 second timeout

            const response = await fetch('/live2d/stt/stream', {
                method: 'POST',
                body: formData,
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`Server error: ${response.status} - ${response.statusText}`);
            }

            const result = await response.json();
            
            if (result.text) {
                this.onResult({
                    text: result.text,
                    isFinal: true,
                    confidence: result.confidence || 0.9,
                    language: this.language
                });
            } else {
                this.onError({ code: 'no-speech', message: 'No speech detected', recoverable: true });
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.error('[WhisperEngine] Processing timeout:', error);
                this.onError({ code: 'timeout', message: 'Processing timed out', recoverable: true });
            } else {
                console.error('[WhisperEngine] Processing error:', error);
                this.onError({ code: 'whisper-unavailable', message: 'Whisper service unavailable', recoverable: false });
            }
        }

        this._cleanup();
        this.onEnd();
    }

    /**
     * Clean up resources
     * @private
     */
    _cleanup() {
        if (this.stream) {
            try {
                this.stream.getTracks().forEach(track => track.stop());
            } catch (error) {
                console.warn('[WhisperEngine] Error stopping tracks:', error);
            }
            this.stream = null;
        }
        this.audioChunks = [];
        this.mediaRecorder = null;
    }
}


// ============================================================================
// SMART VOICE INPUT - Main controller component
// ============================================================================

class SmartVoiceInput {
    constructor(config = {}) {
        // Configuration with defaults
        this.config = {
            language: config.language || 'auto',           // zh-HK, en-US, auto
            mode: config.mode || 'continuous',             // continuous, push-to-talk
            silenceThreshold: config.silenceThreshold || 3000,
            pauseThreshold: config.pauseThreshold || 2000,
            privacyMode: config.privacyMode || false,
            highNoiseThreshold: config.highNoiseThreshold || 0.7
        };

        // State
        this.state = {
            isActive: false,
            status: 'idle',  // idle, listening, paused, processing, sending, error
            currentEngine: null,
            interimTranscript: '',
            finalTranscript: '',
            noiseLevel: 0,
            error: null
        };

        // Callbacks
        this.onTranscript = config.onTranscript || (() => {});
        this.onStatusChange = config.onStatusChange || (() => {});
        this.onError = config.onError || (() => {});
        this.onInterimUpdate = config.onInterimUpdate || (() => {});
        this.onSend = config.onSend || (() => {});

        // Components
        this.audioProcessor = new AudioProcessor({
            noiseSuppression: true,
            echoCancellation: true,
            autoGainControl: true
        });

        this.silenceDetector = new SilenceDetector({
            pauseThreshold: this.config.pauseThreshold,
            silenceThreshold: this.config.silenceThreshold,
            onPauseDetected: () => this._onPauseDetected(),
            onSilenceComplete: () => this._onSilenceComplete(),
            onSpeechResumed: () => this._onSpeechResumed()
        });

        this.webSpeechEngine = new WebSpeechEngine();
        this.whisperEngine = new WhisperEngine();
        this.currentEngine = null;

        // TTS coordination
        this.isTTSPlaying = false;
        this.wasListeningBeforeTTS = false;

        // Load saved settings
        this._loadSettings();

        console.log('[SmartVoiceInput] Initialized with config:', this.config);
    }

    // ========================================================================
    // PUBLIC METHODS
    // ========================================================================

    /**
     * Start voice input
     */
async start() {
        if (this.state.isActive) {
            console.log('[SmartVoiceInput] Already active');
            return;
        }

        // Check if TTS is playing
        if (this.isTTSPlaying) {
            console.log('[SmartVoiceInput] TTS is playing, waiting...');
            return;
        }

        try {
            // Verify Web Speech API is available before proceeding
            if (!this.webSpeechEngine.isAvailable) {
                console.error('[SmartVoiceInput] Web Speech API not available');
                this._handleError({ 
                    code: 'no-web-speech', 
                    message: 'Web Speech API not supported in this browser', 
                    recoverable: true 
                });
                return;
            }

            // Select engine first
            this._selectEngine();

            // IMPORTANT: Do NOT initialize AudioProcessor for Web Speech API
            // Web Speech API handles its own audio capture internally
            // Only initialize for Whisper mode which needs manual audio processing
            if (this.state.currentEngine === 'whisper') {
                await this.audioProcessor.initialize();
            }

            // CRITICAL: Clear ALL transcript state before starting new session
            // This prevents duplicate messages when user clicks speak button again
            this.state.interimTranscript = '';
            this.state.finalTranscript = '';
            this.state.error = null;
            this.silenceDetector.reset();
            
            // Clear any pending message flag
            this._lastSentMessage = null;

            // Start listening
            this.state.isActive = true;
            this._setStatus('listening');

            // Add a small delay to ensure proper timing for browser permission handling
            setTimeout(() => {
                if (this.state.isActive) {
                    this.currentEngine.start(this.config.language);
                }
            }, 10);

        } catch (error) {
            console.error('[SmartVoiceInput] Failed to start:', error);
            // More specific error handling for permission issues
            if (error.message && error.message.includes('not-allowed')) {
                this._handleError({ 
                    code: 'mic-denied', 
                    message: 'Microphone permission denied. Please allow microphone access in browser settings.', 
                    recoverable: false 
                });
            } else {
                this._handleError({ code: 'start-error', message: error.message, recoverable: false });
            }
        }
    }

    /**
     * Stop voice input
     */
    stop() {
        if (!this.state.isActive) return;

        this.silenceDetector.reset();
        
        if (this.currentEngine) {
            this.currentEngine.stop();
        }

        // Only destroy audio processor if it was initialized (Whisper mode)
        if (this.state.currentEngine === 'whisper') {
            this.audioProcessor.destroy();
        }
        
        // Clear transcript state on stop to prevent stale data
        this.state.interimTranscript = '';
        this.state.finalTranscript = '';
        this.state.isActive = false;
        this._setStatus('idle');
        
        console.log('[SmartVoiceInput] Stopped');
    }

    /**
     * Cancel voice input without sending
     */
    cancel() {
        if (!this.state.isActive) return;

        this.silenceDetector.reset();
        
        if (this.currentEngine) {
            this.currentEngine.abort();
        }

        // Only destroy audio processor if it was initialized (Whisper mode)
        if (this.state.currentEngine === 'whisper') {
            this.audioProcessor.destroy();
        }
        
        this.state.isActive = false;
        this.state.interimTranscript = '';
        this.state.finalTranscript = '';
        this._setStatus('idle');
        
        console.log('[SmartVoiceInput] Cancelled');
    }

    /**
     * Force send current transcript
     */
    sendNow() {
        if (this.state.finalTranscript || this.state.interimTranscript) {
            const text = this.state.finalTranscript || this.state.interimTranscript;
            this._sendMessage(text);
        }
    }

    /**
     * Switch language
     * @param {string} language - New language code
     */
    switchLanguage(language) {
        const wasActive = this.state.isActive;
        
        if (wasActive) {
            this.stop();
        }

        this.config.language = language;
        this._saveSettings();

        if (wasActive) {
            setTimeout(() => this.start(), 100);
        }

        console.log('[SmartVoiceInput] Language switched to:', language);
    }

    /**
     * Switch mode (continuous / push-to-talk)
     * @param {string} mode - New mode
     */
    switchMode(mode) {
        this.config.mode = mode;
        this._saveSettings();
        console.log('[SmartVoiceInput] Mode switched to:', mode);
    }

    /**
     * Toggle privacy mode (force Whisper)
     */
    togglePrivacyMode() {
        const wasActive = this.state.isActive;
        
        if (wasActive) {
            this.stop();
        }

        this.config.privacyMode = !this.config.privacyMode;
        this._saveSettings();

        if (wasActive) {
            setTimeout(() => this.start(), 100);
        }

        console.log('[SmartVoiceInput] Privacy mode:', this.config.privacyMode);
        return this.config.privacyMode;
    }

    /**
     * Notify that TTS started playing
     */
    onTTSStart() {
        this.isTTSPlaying = true;
        if (this.state.isActive) {
            this.wasListeningBeforeTTS = true;
            this.stop();
            console.log('[SmartVoiceInput] Paused for TTS playback');
        }
    }

    /**
     * Notify that TTS finished playing
     */
    onTTSEnd() {
        this.isTTSPlaying = false;
        if (this.wasListeningBeforeTTS) {
            this.wasListeningBeforeTTS = false;
            setTimeout(() => this.start(), 500); // Small delay before resuming
            console.log('[SmartVoiceInput] Resuming after TTS');
        }
    }

    /**
     * Get current state
     * @returns {Object}
     */
    getState() {
        return { ...this.state };
    }

    /**
     * Get current config
     * @returns {Object}
     */
    getConfig() {
        return { ...this.config };
    }

    // ========================================================================
    // PRIVATE METHODS
    // ========================================================================

/**
     * Select the appropriate STT engine
     * @private
     */
    _selectEngine() {
        // Check if Web Speech API is available before making selection
        if (!this.webSpeechEngine.isAvailable) {
            console.warn('[SmartVoiceInput] Web Speech API not available, falling back to Whisper');
            this.config.privacyMode = true;
        }
        
        // Use Whisper if privacy mode or Web Speech not available
        if (this.config.privacyMode || !this.webSpeechEngine.isAvailable) {
            this.currentEngine = this.whisperEngine;
            this.state.currentEngine = 'whisper';
        } else {
            this.currentEngine = this.webSpeechEngine;
            this.state.currentEngine = 'web-speech';
        }

        // Set up engine callbacks
        this.currentEngine.onResult = (result) => this._onResult(result);
        this.currentEngine.onError = (error) => this._onEngineError(error);
        this.currentEngine.onEnd = () => this._onEngineEnd();
        this.currentEngine.onSpeechStart = () => this._onSpeechStart();

        console.log('[SmartVoiceInput] Selected engine:', this.state.currentEngine);
    }

    /**
     * Handle speech recognition result
     * @private
     */
    _onResult(result) {
        // Update silence detector
        this.silenceDetector.onSpeechDetected();

        if (result.isFinal) {
            this.state.finalTranscript += result.text;
            this.state.interimTranscript = '';
            
            // In push-to-talk mode, we don't auto-send on final results
            // The user releases the button to send
            if (this.config.mode === 'continuous') {
                // Reset silence detector to wait for more speech or silence
                this.silenceDetector.onSpeechDetected();
            }
        } else {
            this.state.interimTranscript = result.text;
        }

        // Notify listeners
        this.onTranscript(result);
        this.onInterimUpdate(this.state.interimTranscript || this.state.finalTranscript);
    }

    /**
     * Handle speech start event
     * @private
     */
    _onSpeechStart() {
        this._setStatus('listening');
        this.silenceDetector.onSpeechDetected();
    }

    /**
     * Handle pause detected (2 seconds of silence)
     * @private
     */
    _onPauseDetected() {
        if (this.config.mode === 'continuous' && this.state.isActive) {
            this._setStatus('paused');
            console.log('[SmartVoiceInput] Pause detected, still listening...');
        }
    }

    /**
     * Handle speech resumed after pause
     * @private
     */
    _onSpeechResumed() {
        if (this.state.isActive) {
            this._setStatus('listening');
            console.log('[SmartVoiceInput] Speech resumed');
        }
    }

    /**
     * Handle silence complete (3 seconds) - send message
     * @private
     */
    _onSilenceComplete() {
        if (this.config.mode === 'continuous' && this.state.isActive) {
            const text = this.state.finalTranscript || this.state.interimTranscript;
            if (text && text.trim()) {
                this._sendMessage(text.trim());
            } else {
                // No text to send, just reset
                this._setStatus('listening');
            }
        }
    }

    /**
     * Send the transcribed message
     * @private
     */
    _sendMessage(text) {
        // DUPLICATE PREVENTION: Check if this exact message was just sent
        if (this._lastSentMessage === text) {
            console.log('[SmartVoiceInput] Duplicate message prevented:', text.substring(0, 30) + '...');
            // Reset state but don't send
            this.state.interimTranscript = '';
            this.state.finalTranscript = '';
            this.silenceDetector.reset();
            return;
        }
        
        this._setStatus('sending');
        
        // Stop current recognition
        if (this.currentEngine) {
            this.currentEngine.stop();
        }

        // Track last sent message to prevent duplicates
        this._lastSentMessage = text;
        
        // Clear the duplicate tracker after 2 seconds
        setTimeout(() => {
            if (this._lastSentMessage === text) {
                this._lastSentMessage = null;
            }
        }, 2000);

        // Notify listeners
        this.onSend(text);

        // Reset state
        this.state.interimTranscript = '';
        this.state.finalTranscript = '';
        this.silenceDetector.reset();

        // In continuous mode, restart listening after sending
        if (this.config.mode === 'continuous' && this.state.isActive) {
            setTimeout(() => {
                if (this.state.isActive && !this.isTTSPlaying) {
                    this._setStatus('listening');
                    this.currentEngine.start(this.config.language);
                }
            }, 500);
        } else {
            this.state.isActive = false;
            this._setStatus('idle');
        }

        console.log('[SmartVoiceInput] Message sent:', text.substring(0, 50) + '...');
    }

/**
     * Handle engine error
     * @private
     */
    _onEngineError(error) {
        console.error('[SmartVoiceInput] Engine error:', error);

        // Try fallback to Whisper if Web Speech fails and we're not already in privacy mode
        if (this.state.currentEngine === 'web-speech' && error.recoverable && !this.config.privacyMode) {
            console.log('[SmartVoiceInput] Falling back to Whisper due to error:', error.message);
            this.config.privacyMode = true;
            this._selectEngine();
            // Add a small delay to ensure proper state transition
            setTimeout(() => {
                if (this.state.isActive) {
                    this.currentEngine.start(this.config.language);
                }
            }, 100);
            return;
        }

        this._handleError(error);
    }

    /**
     * Handle engine end event
     * @private
     */
    _onEngineEnd() {
        // In continuous mode with Web Speech, auto-restart
        if (this.config.mode === 'continuous' && 
            this.state.isActive && 
            this.state.currentEngine === 'web-speech' &&
            !this.isTTSPlaying) {
            setTimeout(() => {
                if (this.state.isActive) {
                    this.currentEngine.start(this.config.language);
                }
            }, 100);
        }
    }

    /**
     * Handle errors
     * @private
     */
    _handleError(error) {
        this.state.error = error;
        this._setStatus('error');
        this.onError(error);

        // Auto-recover for recoverable errors
        if (error.recoverable && this.config.mode === 'continuous') {
            setTimeout(() => {
                if (this.state.status === 'error') {
                    this._setStatus('idle');
                }
            }, 3000);
        }
    }

    /**
     * Set status and notify listeners
     * @private
     */
    _setStatus(status) {
        this.state.status = status;
        this.onStatusChange(status, this.state.currentEngine);
    }

    // Settings version - increment this when settings format changes
    // This will force clear old incompatible settings
    static SETTINGS_VERSION = 2;

    /**
     * Load settings from localStorage
     * Includes version checking and auto-detection for China/HK users
     * @private
     */
    _loadSettings() {
        try {
            const saved = localStorage.getItem('voiceInputSettings');
            if (saved) {
                const settings = JSON.parse(saved);
                
                // Check settings version - clear if outdated
                if (settings.version !== SmartVoiceInput.SETTINGS_VERSION) {
                    console.log('[SmartVoiceInput] Outdated settings detected, clearing...');
                    localStorage.removeItem('voiceInputSettings');
                    // Don't load old settings, use defaults (which now default to Whisper)
                    return;
                }
                
                this.config.mode = settings.mode || this.config.mode;
                this.config.language = settings.language || this.config.language;
                this.config.privacyMode = settings.privacyMode ?? this.config.privacyMode;
                this.config.silenceThreshold = settings.silenceThreshold || this.config.silenceThreshold;
                console.log('[SmartVoiceInput] Loaded settings:', settings);
            } else {
                // No saved settings - this is first use or settings were cleared
                // Default to Whisper mode (privacyMode: true) for reliability
                // Users can switch to Web Speech if they want faster responses
                console.log('[SmartVoiceInput] No saved settings, using Whisper as default');
            }
        } catch (e) {
            console.warn('[SmartVoiceInput] Failed to load settings:', e);
            // On error, use defaults (Whisper mode for reliability)
        }
    }

    /**
     * Save settings to localStorage
     * @private
     */
    _saveSettings() {
        try {
            const settings = {
                version: SmartVoiceInput.SETTINGS_VERSION,
                mode: this.config.mode,
                language: this.config.language,
                privacyMode: this.config.privacyMode,
                silenceThreshold: this.config.silenceThreshold
            };
            localStorage.setItem('voiceInputSettings', JSON.stringify(settings));
            console.log('[SmartVoiceInput] Saved settings');
        } catch (e) {
            console.warn('[SmartVoiceInput] Failed to save settings:', e);
        }
    }

    /**
     * Test if Web Speech API servers are reachable
     * Returns false if Google servers are blocked (e.g., in China)
     * @returns {Promise<boolean>}
     */
    static async testWebSpeechAvailability() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            return false;
        }
        
        return new Promise((resolve) => {
            try {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                const recognition = new SpeechRecognition();
                recognition.lang = 'en-US';
                recognition.continuous = false;
                recognition.interimResults = false;
                
                let resolved = false;
                
                recognition.onstart = () => {
                    if (!resolved) {
                        resolved = true;
                        recognition.stop();
                        resolve(true);  // Web Speech works
                    }
                };
                
                recognition.onerror = (event) => {
                    if (!resolved) {
                        resolved = true;
                        if (event.error === 'network' || event.error === 'not-allowed') {
                            resolve(false);  // Network blocked or permission denied
                        } else {
                            resolve(true);  // Other errors might be recoverable
                        }
                    }
                };
                
                // Timeout after 3 seconds
                setTimeout(() => {
                    if (!resolved) {
                        resolved = true;
                        recognition.abort();
                        resolve(false);  // Timeout = probably blocked
                    }
                }, 3000);
                
                recognition.start();
            } catch (e) {
                resolve(false);
            }
        });
    }
}

// ============================================================================
// ERROR MESSAGES (Bilingual)
// ============================================================================

const VOICE_ERROR_MESSAGES = {
    'mic-denied': {
        'zh-HK': '請允許使用麥克風。點擊網址列嘅鎖頭圖示開啟權限。',
        'en-US': 'Please allow microphone access. Click the lock icon in the address bar.'
    },
    'network-error': {
        'zh-HK': '網絡連接有問題，已切換到私隱模式。',
        'en-US': 'Network issue detected, switched to privacy mode.'
    },
    'whisper-unavailable': {
        'zh-HK': '語音服務暫時無法使用，請用文字輸入。',
        'en-US': 'Voice service unavailable, please use text input.'
    },
    'high-noise': {
        'zh-HK': '背景噪音太大，請去安靜啲嘅地方。',
        'en-US': 'Background noise is too high, please move to a quieter location.'
    },
    'no-speech': {
        'zh-HK': '聽唔到你講嘢，請再試一次。',
        'en-US': 'No speech detected, please try again.'
    },
    'audio-error': {
        'zh-HK': '音訊錯誤，請重新整理頁面。',
        'en-US': 'Audio error, please refresh the page.'
    }
};

/**
 * Get error message in the specified language
 * @param {string} code - Error code
 * @param {string} language - Language code
 * @returns {string}
 */
function getVoiceErrorMessage(code, language = 'en-US') {
    const messages = VOICE_ERROR_MESSAGES[code];
    if (!messages) return code;
    return messages[language] || messages['en-US'] || code;
}

// Export for use in other modules
window.SmartVoiceInput = SmartVoiceInput;
window.AudioProcessor = AudioProcessor;
window.SilenceDetector = SilenceDetector;
window.WebSpeechEngine = WebSpeechEngine;
window.WhisperEngine = WhisperEngine;
window.getVoiceErrorMessage = getVoiceErrorMessage;
