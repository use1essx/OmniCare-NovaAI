/**
 * Simple STT - Minimal, Fast, Reliable
 * 
 * Uses browser Web Speech API (fast and accurate)
 * Smart silence detection - knows when you start and finish speaking
 * 
 * @version 2.0.0
 */

class SimpleSTT {
    constructor(config = {}) {
        this.config = {
            language: config.language || 'yue-Hant-HK',  // Default to Cantonese
            continuous: config.continuous !== false,
            interimResults: config.interimResults !== false,
            autoStop: config.autoStop !== false,  // Auto-stop after silence
            silenceTimeout: config.silenceTimeout || 2000  // 2 seconds of silence
        };

        // Callbacks
        this.onStart = config.onStart || (() => {});
        this.onResult = config.onResult || (() => {});
        this.onEnd = config.onEnd || (() => {});
        this.onError = config.onError || (() => {});
        this.onSpeechStart = config.onSpeechStart || (() => {});  // When user starts speaking
        this.onSpeechEnd = config.onSpeechEnd || (() => {});      // When user stops speaking
        this.onAutoStop = config.onAutoStop || (() => {});        // When auto-stopped after silence

        // State
        this.isListening = false;
        this.recognition = null;
        this.finalTranscript = '';
        this.interimTranscript = '';
        this.lastSpeechTime = null;
        this.silenceTimer = null;
        this.hasSpeech = false;
        this.isMixedMode = false;  // Track if using mixed language mode

        // Check if Web Speech API is available
        this.isAvailable = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;

        console.log('[SimpleSTT] Initialized', { 
            available: this.isAvailable, 
            language: this.config.language,
            autoStop: this.config.autoStop,
            silenceTimeout: this.config.silenceTimeout
        });
    }

    /**
     * Start listening
     */
    start() {
        if (!this.isAvailable) {
            this.onError({ code: 'not-supported', message: 'Web Speech API not supported' });
            return;
        }

        if (this.isListening) {
            console.log('[SimpleSTT] Already listening');
            return;
        }

        try {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();

            // Handle mixed language mode
            let recognitionLang = this.config.language;
            this.isMixedMode = false;
            
            if (this.config.language === 'mixed') {
                // For mixed mode, use Cantonese as primary but allow alternatives
                recognitionLang = 'yue-Hant-HK';
                this.isMixedMode = true;
                console.log('[SimpleSTT] Mixed mode enabled - will accept English and Cantonese');
            }

            // Configure
            this.recognition.lang = recognitionLang;
            this.recognition.continuous = this.config.continuous;
            this.recognition.interimResults = this.config.interimResults;
            this.recognition.maxAlternatives = this.isMixedMode ? 3 : 1;  // More alternatives for mixed mode

            // Reset state
            this.finalTranscript = '';
            this.interimTranscript = '';
            this.lastSpeechTime = null;
            this.hasSpeech = false;
            this._clearSilenceTimer();

            // Event handlers
            this.recognition.onstart = () => {
                this.isListening = true;
                console.log('[SimpleSTT] Started');
                this.onStart();
            };

            this.recognition.onspeechstart = () => {
                console.log('[SimpleSTT] Speech detected');
                this.hasSpeech = true;
                this.lastSpeechTime = Date.now();
                this.onSpeechStart();
                this._clearSilenceTimer();
            };

            this.recognition.onspeechend = () => {
                console.log('[SimpleSTT] Speech ended');
                this.onSpeechEnd();
                
                // Start silence timer if auto-stop is enabled
                if (this.config.autoStop && this.hasSpeech) {
                    this._startSilenceTimer();
                }
            };

            this.recognition.onresult = (event) => {
                let interim = '';
                let final = '';

                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        final += transcript;
                    } else {
                        interim += transcript;
                    }
                }

                if (final) {
                    this.finalTranscript += final;
                    this.lastSpeechTime = Date.now();
                }
                this.interimTranscript = interim;

                this.onResult({
                    final: this.finalTranscript,
                    interim: this.interimTranscript,
                    isFinal: final.length > 0
                });

                // Reset silence timer on new speech
                if (this.config.autoStop && (final || interim)) {
                    this._clearSilenceTimer();
                    this._startSilenceTimer();
                }
            };

            this.recognition.onerror = (event) => {
                console.error('[SimpleSTT] Error:', event.error);
                this.isListening = false;
                this._clearSilenceTimer();

                const errorMap = {
                    'no-speech': 'No speech detected',
                    'audio-capture': 'Microphone not accessible',
                    'not-allowed': 'Microphone permission denied',
                    'network': 'Network error',
                    'aborted': 'Recognition aborted'
                };

                this.onError({
                    code: event.error,
                    message: errorMap[event.error] || event.error
                });
            };

            this.recognition.onend = () => {
                this.isListening = false;
                this._clearSilenceTimer();
                console.log('[SimpleSTT] Ended');
                this.onEnd();
            };

            // Start recognition
            this.recognition.start();

        } catch (error) {
            console.error('[SimpleSTT] Failed to start:', error);
            this.onError({ code: 'start-error', message: error.message });
        }
    }

    /**
     * Start silence detection timer
     * @private
     */
    _startSilenceTimer() {
        this._clearSilenceTimer();
        
        this.silenceTimer = setTimeout(() => {
            if (this.isListening && this.hasSpeech) {
                console.log('[SimpleSTT] Silence detected, auto-stopping');
                const transcript = this.getTranscript();
                this.onAutoStop(transcript);
                this.stop();
            }
        }, this.config.silenceTimeout);
    }

    /**
     * Clear silence detection timer
     * @private
     */
    _clearSilenceTimer() {
        if (this.silenceTimer) {
            clearTimeout(this.silenceTimer);
            this.silenceTimer = null;
        }
    }

    /**
     * Stop listening
     */
    stop() {
        if (this.recognition && this.isListening) {
            this.recognition.stop();
        }
    }

    /**
     * Get current transcript
     */
    getTranscript() {
        return {
            final: this.finalTranscript,
            interim: this.interimTranscript,
            full: this.finalTranscript + this.interimTranscript
        };
    }

    /**
     * Change language
     */
    setLanguage(language) {
        this.config.language = language;
        console.log('[SimpleSTT] Language changed to:', language);
    }
}

// Export
window.SimpleSTT = SimpleSTT;
