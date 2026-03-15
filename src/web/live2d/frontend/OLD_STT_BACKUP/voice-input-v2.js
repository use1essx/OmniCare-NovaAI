/**
 * Voice Input System V2 - Clean Rework
 * =====================================
 * 
 * Reliable voice input system with proper state management and resource cleanup.
 * Fixes the "works first time only" bug through proper MediaStream lifecycle management.
 * 
 * Features:
 * - Hold Mode: Manual start/stop, review before send
 * - Auto Mode: Voice Activity Detection (VAD) auto-stop, auto-send
 * - Proper cleanup between recording sessions
 * - Clear state machine with validated transitions
 */

// =============================================================================
// STATE MACHINE
// =============================================================================

/**
 * StateMachine - Validates and manages recording state transitions
 * 
 * States:
 * - idle: Ready to start recording
 * - recording: Currently recording audio
 * - processing: Transcribing audio
 * - transcribed: Transcription complete
 * - error: Error occurred
 * 
 * Valid Transitions:
 * - idle → recording
 * - recording → processing, idle, error
 * - processing → transcribed, error
 * - transcribed → idle
 * - error → idle
 */
class StateMachine {
    constructor() {
        this.state = 'idle';
        
        // Define valid state transitions
        this.transitions = {
            'idle': ['recording'],
            'recording': ['processing', 'idle', 'error'],
            'processing': ['transcribed', 'error'],
            'transcribed': ['idle'],
            'error': ['idle']
        };
    }
    
    /**
     * Check if transition to new state is valid
     * @param {string} newState - Target state
     * @returns {boolean} True if transition is valid
     */
    canTransition(newState) {
        const validStates = this.transitions[this.state] || [];
        return validStates.includes(newState);
    }
    
    /**
     * Transition to new state
     * @param {string} newState - Target state
     * @throws {Error} If transition is invalid
     */
    transition(newState) {
        if (!this.canTransition(newState)) {
            throw new Error(
                `Invalid state transition: ${this.state} -> ${newState}`
            );
        }
        
        const oldState = this.state;
        this.state = newState;
        
        console.log(`[StateMachine] ${oldState} → ${newState}`);
    }
    
    /**
     * Get current state
     * @returns {string} Current state
     */
    getState() {
        return this.state;
    }
    
    /**
     * Reset to idle state (for testing/recovery)
     */
    reset() {
        this.state = 'idle';
        console.log('[StateMachine] Reset to idle');
    }
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { StateMachine };
}

// =============================================================================
// MEDIA STREAM MANAGER
// =============================================================================

/**
 * MediaStreamManager - Manages MediaStream lifecycle with proper cleanup
 * 
 * This is the KEY FIX for the "works first time only" bug.
 * Ensures complete cleanup of media streams between recording sessions.
 * 
 * Responsibilities:
 * - Acquire new MediaStream from browser
 * - Track active streams
 * - Stop all tracks when releasing
 * - Handle permission errors gracefully
 */
class MediaStreamManager {
    constructor() {
        this.stream = null;
    }
    
    /**
     * Acquire a new media stream from the browser
     * @returns {Promise<MediaStream>} The acquired media stream
     * @throws {Error} If permission denied or no microphone found
     */
    async acquire() {
        // CRITICAL: Release any existing stream first
        // This prevents the "works first time only" bug
        await this.release();
        
        try {
            console.log('[MediaStreamManager] Requesting microphone access...');
            
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            
            console.log('[MediaStreamManager] ✅ Media stream acquired');
            console.log(`[MediaStreamManager] Active tracks: ${this.stream.getTracks().length}`);
            
            return this.stream;
            
        } catch (error) {
            console.error('[MediaStreamManager] ❌ Failed to acquire stream:', error);
            
            // Categorize errors for better user feedback
            if (error.name === 'NotAllowedError') {
                throw new Error('Microphone permission denied. Please allow microphone access in your browser settings.');
            } else if (error.name === 'NotFoundError') {
                throw new Error('No microphone found. Please connect a microphone and try again.');
            } else if (error.name === 'NotReadableError') {
                throw new Error('Microphone is already in use by another application.');
            } else {
                throw new Error(`Failed to access microphone: ${error.message}`);
            }
        }
    }
    
    /**
     * Release the current media stream and stop all tracks
     * CRITICAL for preventing the "works first time only" bug
     */
    async release() {
        if (this.stream) {
            console.log('[MediaStreamManager] Releasing media stream...');
            
            // Stop all tracks
            const tracks = this.stream.getTracks();
            tracks.forEach(track => {
                console.log(`[MediaStreamManager] Stopping track: ${track.kind} (${track.label})`);
                track.stop();
            });
            
            // Clear reference
            this.stream = null;
            
            console.log('[MediaStreamManager] ✅ Media stream released');
        }
    }
    
    /**
     * Check if stream is currently active
     * @returns {boolean} True if stream exists and has live tracks
     */
    isActive() {
        if (!this.stream) {
            return false;
        }
        
        // Check if any track is still live
        const liveTracks = this.stream.getTracks().filter(
            track => track.readyState === 'live'
        );
        
        return liveTracks.length > 0;
    }
    
    /**
     * Get the current stream (for testing/debugging)
     * @returns {MediaStream|null} Current stream or null
     */
    getStream() {
        return this.stream;
    }
}

// =============================================================================
// AUDIO RECORDER
// =============================================================================

/**
 * AudioRecorder - Records audio using MediaRecorder API
 * 
 * Responsibilities:
 * - Initialize MediaRecorder with best supported mime type
 * - Collect audio chunks during recording
 * - Return audio blob when stopped
 * - Clean up resources properly
 * 
 * Supported formats (in order of preference):
 * 1. audio/webm;codecs=opus (best quality, widely supported)
 * 2. audio/webm (fallback)
 * 3. audio/ogg;codecs=opus (Firefox)
 * 4. audio/mp4 (Safari)
 */
class AudioRecorder {
    /**
     * @param {MediaStream} stream - The media stream to record from
     */
    constructor(stream) {
        this.stream = stream;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.mimeType = this._getBestMimeType();
        
        console.log(`[AudioRecorder] Initialized with mime type: ${this.mimeType}`);
    }
    
    /**
     * Start recording audio
     * @returns {Promise<void>}
     * @throws {Error} If recording fails to start
     */
    async start() {
        return new Promise((resolve, reject) => {
            try {
                console.log('[AudioRecorder] Starting recording...');
                
                // Create MediaRecorder
                this.mediaRecorder = new MediaRecorder(this.stream, {
                    mimeType: this.mimeType
                });
                
                // Reset audio chunks
                this.audioChunks = [];
                
                // Set up event handlers
                this.mediaRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0) {
                        this.audioChunks.push(event.data);
                        console.log(`[AudioRecorder] Chunk received: ${event.data.size} bytes`);
                    }
                };
                
                this.mediaRecorder.onerror = (event) => {
                    console.error('[AudioRecorder] ❌ Recording error:', event.error);
                    reject(new Error(`Recording error: ${event.error}`));
                };
                
                this.mediaRecorder.onstart = () => {
                    console.log('[AudioRecorder] ✅ Recording started');
                    resolve();
                };
                
                // Start recording (collect data every 100ms)
                this.mediaRecorder.start(100);
                
            } catch (error) {
                console.error('[AudioRecorder] ❌ Failed to start recording:', error);
                reject(new Error(`Failed to start recording: ${error.message}`));
            }
        });
    }
    
    /**
     * Stop recording and return audio blob
     * @returns {Promise<Blob>} The recorded audio as a blob
     * @throws {Error} If recorder is not active or stop fails
     */
    async stop() {
        return new Promise((resolve, reject) => {
            if (!this.mediaRecorder) {
                reject(new Error('Recorder not initialized'));
                return;
            }
            
            if (this.mediaRecorder.state === 'inactive') {
                reject(new Error('Recorder not active'));
                return;
            }
            
            console.log('[AudioRecorder] Stopping recording...');
            
            // Set up stop handler
            this.mediaRecorder.onstop = () => {
                console.log(`[AudioRecorder] Recording stopped. Total chunks: ${this.audioChunks.length}`);
                
                // Create blob from chunks
                const audioBlob = new Blob(this.audioChunks, {
                    type: this.mimeType
                });
                
                console.log(`[AudioRecorder] ✅ Audio blob created: ${audioBlob.size} bytes, type: ${audioBlob.type}`);
                
                resolve(audioBlob);
            };
            
            // Stop recording
            this.mediaRecorder.stop();
        });
    }
    
    /**
     * Cancel recording without returning blob
     * Useful when user cancels or error occurs
     */
    cancel() {
        console.log('[AudioRecorder] Cancelling recording...');
        
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }
        
        // Clear chunks
        this.audioChunks = [];
        
        console.log('[AudioRecorder] ✅ Recording cancelled');
    }
    
    /**
     * Clean up all resources
     * Should be called when done with recorder
     */
    cleanup() {
        console.log('[AudioRecorder] Cleaning up...');
        
        // Cancel any active recording
        this.cancel();
        
        // Clear references
        this.mediaRecorder = null;
        this.audioChunks = [];
        
        console.log('[AudioRecorder] ✅ Cleanup complete');
    }
    
    /**
     * Get the best supported mime type for recording
     * @returns {string} The best supported mime type, or empty string for default
     * @private
     */
    _getBestMimeType() {
        const types = [
            'audio/webm;codecs=opus',  // Best quality, Chrome/Edge
            'audio/webm',               // Fallback for Chrome/Edge
            'audio/ogg;codecs=opus',    // Firefox
            'audio/mp4'                 // Safari
        ];
        
        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                console.log(`[AudioRecorder] Selected mime type: ${type}`);
                return type;
            }
        }
        
        console.warn('[AudioRecorder] No preferred mime type supported, using default');
        return ''; // Use browser default
    }
    
    /**
     * Get current recording state
     * @returns {string} 'inactive', 'recording', or 'paused'
     */
    getState() {
        return this.mediaRecorder ? this.mediaRecorder.state : 'inactive';
    }
}

// =============================================================================
// VAD DETECTOR
// =============================================================================

/**
 * VADDetector - Voice Activity Detection for Auto Mode
 * 
 * Monitors audio levels and detects silence to automatically stop recording.
 * Uses Web Audio API (AudioContext + AnalyserNode) for real-time analysis.
 * 
 * Responsibilities:
 * - Monitor audio volume in real-time
 * - Detect when user stops speaking (silence)
 * - Reset timer when speech resumes
 * - Trigger callback when silence threshold reached
 */
class VADDetector {
    /**
     * @param {MediaStream} stream - The media stream to monitor
     * @param {Object} config - Configuration options
     * @param {number} config.silenceThreshold - Milliseconds of silence before triggering (default: 2000)
     * @param {number} config.volumeThreshold - Minimum volume to consider as speech (default: 0.01)
     * @param {Function} config.onSilenceDetected - Callback when silence detected
     */
    constructor(stream, config) {
        this.stream = stream;
        this.config = {
            silenceThreshold: config.silenceThreshold || 2000,
            volumeThreshold: config.volumeThreshold || 0.01,
            onSilenceDetected: config.onSilenceDetected || (() => {})
        };
        
        this.audioContext = null;
        this.analyser = null;
        this.silenceTimer = null;
        this.isMonitoring = false;
        
        console.log(`[VADDetector] Initialized with silence threshold: ${this.config.silenceThreshold}ms, volume threshold: ${this.config.volumeThreshold}`);
    }
    
    /**
     * Start monitoring audio for silence detection
     */
    start() {
        try {
            console.log('[VADDetector] Starting voice activity detection...');
            
            // Create audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Create analyser node
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = 0.8;
            
            // Connect stream to analyser
            const source = this.audioContext.createMediaStreamSource(this.stream);
            source.connect(this.analyser);
            
            // Start monitoring loop
            this.isMonitoring = true;
            this._monitor();
            
            console.log('[VADDetector] ✅ Voice activity detection started');
            
        } catch (error) {
            console.error('[VADDetector] ❌ Failed to start VAD:', error);
            throw new Error(`Failed to start voice activity detection: ${error.message}`);
        }
    }
    
    /**
     * Stop monitoring and cleanup resources
     */
    stop() {
        console.log('[VADDetector] Stopping voice activity detection...');
        
        this.isMonitoring = false;
        
        // Clear silence timer
        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
            this.silenceTimer = null;
        }
        
        // Close audio context
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        this.analyser = null;
        
        console.log('[VADDetector] ✅ Voice activity detection stopped');
    }
    
    /**
     * Monitor audio levels in real-time
     * @private
     */
    _monitor() {
        if (!this.isMonitoring || !this.analyser) {
            return;
        }
        
        // Get frequency data
        const dataArray = new Uint8Array(this.analyser.frequencyBinCount);
        this.analyser.getByteFrequencyData(dataArray);
        
        // Calculate average volume (0.0 to 1.0)
        const average = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
        const volume = average / 255;
        
        // Check if speaking or silent
        if (volume > this.config.volumeThreshold) {
            // Speaking detected - reset silence timer
            if (this.silenceTimer) {
                console.log(`[VADDetector] Speech detected (volume: ${volume.toFixed(3)}), resetting silence timer`);
                clearTimeout(this.silenceTimer);
                this.silenceTimer = null;
            }
        } else {
            // Silence detected - start timer if not already started
            if (!this.silenceTimer) {
                console.log(`[VADDetector] Silence detected (volume: ${volume.toFixed(3)}), starting ${this.config.silenceThreshold}ms timer`);
                this.silenceTimer = setTimeout(() => {
                    console.log('[VADDetector] ⏰ Silence threshold reached, triggering callback');
                    this.config.onSilenceDetected();
                }, this.config.silenceThreshold);
            }
        }
        
        // Continue monitoring (60 FPS)
        requestAnimationFrame(() => this._monitor());
    }
    
    /**
     * Get current monitoring status
     * @returns {boolean} True if currently monitoring
     */
    isActive() {
        return this.isMonitoring;
    }
}

// =============================================================================
// TRANSCRIPTION SERVICE
// =============================================================================

/**
 * TranscriptionService - Sends audio to backend for speech-to-text
 * 
 * Responsibilities:
 * - Send audio blob to STT backend endpoint
 * - Handle successful transcription responses
 * - Handle error responses (network, server, empty transcription)
 * - Apply timeout to prevent hanging requests
 */
class TranscriptionService {
    /**
     * @param {string} endpoint - STT endpoint URL (default: '/live2d/stt/stream')
     * @param {number} timeout - Request timeout in milliseconds (default: 30000)
     */
    constructor(endpoint = '/live2d/stt/stream', timeout = 30000) {
        this.endpoint = endpoint;
        this.timeout = timeout;
        
        console.log(`[TranscriptionService] Initialized with endpoint: ${this.endpoint}, timeout: ${this.timeout}ms`);
    }
    
    /**
     * Transcribe audio blob to text
     * @param {Blob} audioBlob - The audio blob to transcribe
     * @param {string} language - Language code (default: 'zh-HK')
     * @returns {Promise<string>} The transcribed text
     * @throws {Error} If transcription fails
     */
    async transcribe(audioBlob, language = 'zh-HK') {
        console.log(`[TranscriptionService] Starting transcription... (blob size: ${audioBlob.size} bytes, language: ${language})`);
        
        try {
            // Create form data
            const formData = new FormData();
            formData.append('audio', audioBlob, 'recording.webm');
            formData.append('lang', language);
            
            // Create abort controller for timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.timeout);
            
            try {
                // Send to backend
                const response = await fetch(this.endpoint, {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                // Check response status
                if (!response.ok) {
                    throw new Error(`Transcription failed: HTTP ${response.status}`);
                }
                
                // Parse JSON response
                const result = await response.json();
                
                // Validate response has text
                if (!result.text || result.text.trim() === '') {
                    console.warn('[TranscriptionService] ⚠️ Empty transcription received');
                    throw new Error('No speech detected. Please speak clearly and try again.');
                }
                
                const transcript = result.text.trim();
                console.log(`[TranscriptionService] ✅ Transcription successful: "${transcript}"`);
                
                return transcript;
                
            } catch (error) {
                clearTimeout(timeoutId);
                
                // Handle abort (timeout)
                if (error.name === 'AbortError') {
                    console.error('[TranscriptionService] ❌ Request timeout');
                    throw new Error('Transcription timeout. Please try again.');
                }
                
                throw error;
            }
            
        } catch (error) {
            console.error('[TranscriptionService] ❌ Transcription error:', error);
            
            // Categorize errors for better user feedback
            if (error.message.includes('No speech detected')) {
                throw error; // Already formatted
            } else if (error.message.includes('timeout')) {
                throw error; // Already formatted
            } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
                throw new Error('Network error. Please check your connection and try again.');
            } else if (error.message.includes('HTTP')) {
                throw new Error('Transcription service error. Please try again later.');
            } else {
                throw new Error(`Transcription failed: ${error.message}`);
            }
        }
    }
    
    /**
     * Set custom endpoint
     * @param {string} endpoint - New endpoint URL
     */
    setEndpoint(endpoint) {
        this.endpoint = endpoint;
        console.log(`[TranscriptionService] Endpoint updated to: ${this.endpoint}`);
    }
    
    /**
     * Set custom timeout
     * @param {number} timeout - New timeout in milliseconds
     */
    setTimeout(timeout) {
        this.timeout = timeout;
        console.log(`[TranscriptionService] Timeout updated to: ${this.timeout}ms`);
    }
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { StateMachine, MediaStreamManager, AudioRecorder, VADDetector, TranscriptionService };
}


// =============================================================================
// VOICE INPUT CONTROLLER
// =============================================================================

/**
 * VoiceInputController - Main orchestrator for voice input system
 * 
 * Coordinates all components (StateMachine, MediaStreamManager, AudioRecorder,
 * VADDetector, TranscriptionService) to provide a complete voice input solution.
 * 
 * Features:
 * - Hold Mode: Manual start/stop, user reviews transcript before sending
 * - Auto Mode: VAD auto-detects silence, auto-stops, auto-sends
 * - Mode persistence to localStorage
 * - Comprehensive error handling with cleanup
 * - State change notifications for UI updates
 */
class VoiceInputController {
    /**
     * @param {Object} config - Configuration options
     * @param {string} config.mode - Initial mode: 'hold' or 'auto' (default: 'hold')
     * @param {number} config.silenceThreshold - Silence duration for VAD in ms (default: 2000)
     * @param {number} config.volumeThreshold - Volume threshold for VAD (default: 0.01)
     * @param {Function} config.onTranscript - Callback when transcript ready: (text, mode) => void
     * @param {Function} config.onError - Callback when error occurs: (error) => void
     * @param {Function} config.onStateChange - Callback when state changes: (state) => void
     * @param {string} config.sttEndpoint - STT endpoint URL (default: '/live2d/stt/stream')
     * @param {string} config.language - Language code (default: 'zh-HK')
     */
    constructor(config = {}) {
        // Load saved mode from localStorage
        const savedMode = this._loadMode();
        
        this.config = {
            mode: savedMode || config.mode || 'hold',
            silenceThreshold: config.silenceThreshold || 2000,
            volumeThreshold: config.volumeThreshold || 0.01,
            onTranscript: config.onTranscript || null,
            onError: config.onError || null,
            onStateChange: config.onStateChange || null,
            sttEndpoint: config.sttEndpoint || '/live2d/stt/stream',
            language: config.language || 'zh-HK'
        };
        
        // Initialize components
        this.stateMachine = new StateMachine();
        this.mediaStreamMgr = new MediaStreamManager();
        this.audioRecorder = null;
        this.vadDetector = null;
        this.transcriptionService = new TranscriptionService(
            this.config.sttEndpoint
        );
        
        console.log(`[VoiceInputController] Initialized in ${this.config.mode} mode`);
    }
    
    /**
     * Start recording based on current mode
     * @returns {Promise<void>}
     */
    async startRecording() {
        console.log(`[VoiceInputController] Starting recording in ${this.config.mode} mode...`);
        
        // Validate state transition
        if (!this.stateMachine.canTransition('recording')) {
            const error = new Error(`Cannot start recording from ${this.stateMachine.getState()} state`);
            console.error('[VoiceInputController] ❌', error.message);
            throw error;
        }
        
        try {
            // Acquire media stream
            const stream = await this.mediaStreamMgr.acquire();
            
            // Create audio recorder
            this.audioRecorder = new AudioRecorder(stream);
            
            // Set up VAD if in auto mode
            if (this.config.mode === 'auto') {
                console.log('[VoiceInputController] Setting up VAD for auto mode...');
                this.vadDetector = new VADDetector(stream, {
                    silenceThreshold: this.config.silenceThreshold,
                    volumeThreshold: this.config.volumeThreshold,
                    onSilenceDetected: () => {
                        console.log('[VoiceInputController] VAD detected silence, auto-stopping...');
                        this.stopRecording();
                    }
                });
                this.vadDetector.start();
            }
            
            // Start recording
            await this.audioRecorder.start();
            
            // Update state
            this.stateMachine.transition('recording');
            this._notifyStateChange();
            
            console.log('[VoiceInputController] ✅ Recording started successfully');
            
        } catch (error) {
            console.error('[VoiceInputController] ❌ Failed to start recording:', error);
            await this.cleanup();
            this._handleError(error);
            throw error;
        }
    }
    
    /**
     * Stop recording and transcribe
     * @returns {Promise<void>}
     */
    async stopRecording() {
        const currentState = this.stateMachine.getState();
        
        if (currentState !== 'recording') {
            console.warn(`[VoiceInputController] Cannot stop recording from ${currentState} state`);
            return;
        }
        
        console.log('[VoiceInputController] Stopping recording...');
        
        try {
            // Stop VAD if active
            if (this.vadDetector) {
                this.vadDetector.stop();
                this.vadDetector = null;
            }
            
            // Stop recording and get audio blob
            const audioBlob = await this.audioRecorder.stop();
            console.log(`[VoiceInputController] Audio blob captured: ${audioBlob.size} bytes`);
            
            // Update state to processing
            this.stateMachine.transition('processing');
            this._notifyStateChange();
            
            // Transcribe audio
            console.log('[VoiceInputController] Transcribing audio...');
            const transcript = await this.transcriptionService.transcribe(
                audioBlob,
                this.config.language
            );
            
            // Update state to transcribed
            this.stateMachine.transition('transcribed');
            this._notifyStateChange();
            
            // Notify callback with transcript and mode
            if (this.config.onTranscript) {
                console.log(`[VoiceInputController] Notifying transcript callback (mode: ${this.config.mode})`);
                this.config.onTranscript(transcript, this.config.mode);
            }
            
            // Cleanup resources
            await this.cleanup();
            
            // Return to idle
            this.stateMachine.transition('idle');
            this._notifyStateChange();
            
            console.log('[VoiceInputController] ✅ Recording completed successfully');
            
        } catch (error) {
            console.error('[VoiceInputController] ❌ Failed to stop recording:', error);
            
            // CRITICAL FIX: Ensure cleanup happens even on error
            try {
                await this.cleanup();
            } catch (cleanupError) {
                console.error('[VoiceInputController] ❌ Cleanup failed:', cleanupError);
            }
            
            // Handle error (will auto-recover after 1 second)
            this._handleError(error);
            throw error;
        }
    }
    
    /**
     * Cancel recording without transcribing
     * @returns {Promise<void>}
     */
    async cancelRecording() {
        console.log('[VoiceInputController] Cancelling recording...');
        
        try {
            // Stop VAD if active
            if (this.vadDetector) {
                this.vadDetector.stop();
                this.vadDetector = null;
            }
            
            // Cancel audio recorder
            if (this.audioRecorder) {
                this.audioRecorder.cancel();
            }
            
            // Cleanup resources
            await this.cleanup();
            
            // Return to idle
            this.stateMachine.transition('idle');
            this._notifyStateChange();
            
            console.log('[VoiceInputController] ✅ Recording cancelled');
            
        } catch (error) {
            console.error('[VoiceInputController] ❌ Failed to cancel recording:', error);
            await this.cleanup();
            this._handleError(error);
        }
    }
    
    /**
     * Toggle between hold and auto modes
     * If currently recording, cancels the recording first
     * @returns {string} The new mode ('hold' or 'auto')
     */
    toggleMode() {
        const oldMode = this.config.mode;
        
        // If recording, cancel first
        if (this.stateMachine.getState() === 'recording') {
            console.log('[VoiceInputController] Cancelling recording before mode toggle...');
            this.cancelRecording();
        }
        
        // Toggle mode
        this.config.mode = this.config.mode === 'hold' ? 'auto' : 'hold';
        
        // Persist to localStorage
        this._saveMode();
        
        console.log(`[VoiceInputController] Mode toggled: ${oldMode} → ${this.config.mode}`);
        
        // Notify state change (mode changed)
        this._notifyStateChange();
        
        return this.config.mode;
    }
    
    /**
     * Clean up all resources
     * @returns {Promise<void>}
     */
    async cleanup() {
        console.log('[VoiceInputController] Cleaning up resources...');
        
        // Stop and cleanup VAD
        if (this.vadDetector) {
            this.vadDetector.stop();
            this.vadDetector = null;
        }
        
        // Stop and cleanup audio recorder
        if (this.audioRecorder) {
            this.audioRecorder.cleanup();
            this.audioRecorder = null;
        }
        
        // Release media stream
        await this.mediaStreamMgr.release();
        
        console.log('[VoiceInputController] ✅ Cleanup complete');
    }
    
    /**
     * Get current state
     * @returns {Object} Current state and mode
     */
    getState() {
        return {
            state: this.stateMachine.getState(),
            mode: this.config.mode
        };
    }
    
    /**
     * Get current mode
     * @returns {string} Current mode ('hold' or 'auto')
     */
    getMode() {
        return this.config.mode;
    }
    
    /**
     * Set mode programmatically
     * @param {string} mode - New mode ('hold' or 'auto')
     */
    setMode(mode) {
        if (mode !== 'hold' && mode !== 'auto') {
            throw new Error(`Invalid mode: ${mode}. Must be 'hold' or 'auto'`);
        }
        
        // If recording, cancel first
        if (this.stateMachine.getState() === 'recording') {
            this.cancelRecording();
        }
        
        this.config.mode = mode;
        this._saveMode();
        this._notifyStateChange();
        
        console.log(`[VoiceInputController] Mode set to: ${mode}`);
    }
    
    /**
     * Notify state change callback
     * @private
     */
    _notifyStateChange() {
        if (this.config.onStateChange) {
            const state = this.getState();
            console.log(`[VoiceInputController] 🔔 State changed:`, state);
            this.config.onStateChange(state);
        }
    }
    
    /**
     * Handle error and notify callback
     * @private
     */
    _handleError(error) {
        // Transition to error state
        try {
            this.stateMachine.transition('error');
            this._notifyStateChange();
        } catch (e) {
            // State transition might fail, that's ok
            console.warn('[VoiceInputController] Could not transition to error state:', e);
        }
        
        // Notify error callback
        if (this.config.onError) {
            this.config.onError(error);
        }
        
        // Log error
        console.error('[VoiceInputController] Error:', error);
        
        // CRITICAL FIX: Auto-recover from error state after a short delay
        // This prevents the "works once then stuck" bug
        setTimeout(() => {
            try {
                if (this.stateMachine.getState() === 'error') {
                    console.log('[VoiceInputController] 🔄 Auto-recovering from error state...');
                    this.stateMachine.transition('idle');
                    this._notifyStateChange();
                    console.log('[VoiceInputController] ✅ Recovered to idle state');
                }
            } catch (e) {
                console.error('[VoiceInputController] ❌ Failed to recover from error:', e);
                // Force reset as last resort
                this.stateMachine.reset();
                this._notifyStateChange();
            }
        }, 1000); // Wait 1 second before recovering
    }
    
    /**
     * Save mode to localStorage
     * @private
     */
    _saveMode() {
        try {
            localStorage.setItem('voiceInputMode', this.config.mode);
            console.log(`[VoiceInputController] Mode saved to localStorage: ${this.config.mode}`);
        } catch (e) {
            console.warn('[VoiceInputController] Failed to save mode to localStorage:', e);
        }
    }
    
    /**
     * Load mode from localStorage
     * @private
     * @returns {string|null} Saved mode or null
     */
    _loadMode() {
        try {
            const savedMode = localStorage.getItem('voiceInputMode');
            if (savedMode === 'hold' || savedMode === 'auto') {
                console.log(`[VoiceInputController] Loaded mode from localStorage: ${savedMode}`);
                return savedMode;
            }
        } catch (e) {
            console.warn('[VoiceInputController] Failed to load mode from localStorage:', e);
        }
        return null;
    }
}

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { 
        StateMachine, 
        MediaStreamManager, 
        AudioRecorder, 
        VADDetector, 
        TranscriptionService,
        VoiceInputController
    };
}
