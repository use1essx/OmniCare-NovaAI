(function(global) {
    const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

    const DEFAULT_COPY = {
        railTitle: {
            'en-US': 'Conversation',
            'zh-HK': '對話',
        },
        railSubtitle: {
            'en-US': 'Voice linked • Live2D active',
            'zh-HK': '語音已連線 • Live2D 已啟動',
        },
        loadOlder: {
            'en-US': 'Load previous messages',
            'zh-HK': '載入較早訊息',
        },
        composerPlaceholder: {
            'en-US': 'Type a message…',
            'zh-HK': '請輸入訊息…',
        },
        emptyTitle: {
            'en-US': 'Start a health check-in',
            'zh-HK': '開始健康諮詢',
        },
        emptySubtitle: {
            'en-US': 'Speak or type to begin — your Live2D nurse is ready.',
            'zh-HK': '可以開口或輸入文字開始，Live2D 護理員隨時待命。',
        },
        adminLabel: {
            'en-US': '⚙️ Admin',
            'zh-HK': '⚙️ 管理'
        },
        sendLabel: {
            'en-US': 'Send',
            'zh-HK': '傳送',
        },
        sendTitle: {
            'en-US': 'Send message',
            'zh-HK': '傳送訊息',
        },
        micTitle: {
            'en-US': 'Voice input',
            'zh-HK': '語音輸入',
        },
        ttsTitle: {
            'en-US': 'Text-to-Speech ON (click to disable)',
            'zh-HK': '語音播放開啟（點擊關閉）',
        },
        clearTitle: {
            'en-US': 'Start new conversation',
            'zh-HK': '開始新對話',
        },
    };

    const copyFor = (dictionary, locale) => {
        return dictionary[locale] || dictionary['en-US'] || '';
    };

    class Live2DChatStage {
        constructor(root, config = {}, locale = 'en-US') {
            if (!root) {
                throw new Error('Live2DChatStage root element is required.');
            }
            this.root = root;
            this.locale = locale;
            this.config = {
                RAIL_MAX_VH: 38,
                RAIL_WIDTH_MAX: 880,
                RAIL_CHROMELESS: true,
                VISIBILITY_MODE: 'auto',
                IDLE_DIM_SECONDS: 2,
                FADE_MS: 180,
                FACE_GUARD_PCT: 0.25,
                HISTORY_LIMIT: 50,
                RECENT_VISIBLE: 8,
                BLUR_ENABLED: true,
                ...config,
            };

            this.elements = {};
            this._viewportListeners = [];
            this._globalListeners = [];
            this.state = {
                visibility: 'hidden',
                peekTimer: null,
                hideTimer: null,
            };
            this._railResizeObserver = null;
            this._faceGuardRaf = null;
            this._boundHandleInteraction = this._handleInteraction.bind(this);
            this._boundIdleCountdown = this._startIdleCountdown.bind(this);
            this._boundFaceGuard = () => this._applyFaceGuard();
        }

        init() {
            this._applyConfig();
            this._buildDOM();
            this._attachViewportListeners();
            console.log('🎛️ Live2DChatStage mounted');
            return this.elements;
        }

        destroy() {
            this._viewportListeners.forEach(({ type, listener }) => {
                window.visualViewport?.removeEventListener(type, listener);
            });
            this._viewportListeners = [];

            this._globalListeners.forEach(({ target, type, listener, options }) => {
                target.removeEventListener(type, listener, options);
            });
            this._globalListeners = [];

            this._clearVisibilityTimers();

            if (this._railResizeObserver) {
                this._railResizeObserver.disconnect();
                this._railResizeObserver = null;
            }

            if (this._faceGuardRaf) {
                cancelAnimationFrame(this._faceGuardRaf);
                this._faceGuardRaf = null;
            }

            if (this.root) {
                this.root.innerHTML = '';
            }
        }

        _applyConfig() {
            this.root.classList.add('live2d-chat-stage');

            const maxVh = clamp(this.config.RAIL_MAX_VH, 30, 50);
            this.root.style.setProperty('--live2d-rail-max-height', `${maxVh}vh`);

            const widthMax = this.config.RAIL_WIDTH_MAX || 880;
            this.root.style.setProperty('--live2d-rail-width', `min(${widthMax}px, 96vw)`);

            const fadeMs = this.config.FADE_MS || 180;
            this.root.style.setProperty('--live2d-rail-transition', `${fadeMs}ms`);

            if (this.config.RAIL_CHROMELESS) {
                this.root.dataset.railChromeless = 'true';
            } else {
                delete this.root.dataset.railChromeless;
            }

            const blurSupported = typeof CSS !== 'undefined'
                && CSS.supports
                && (CSS.supports('backdrop-filter: blur(10px)') || CSS.supports('-webkit-backdrop-filter: blur(10px)'));

            if (this.config.BLUR_ENABLED && blurSupported) {
                this.root.dataset.blur = 'true';
            } else {
                this.root.dataset.blur = 'false';
            }
        }

        _buildDOM() {
            this.root.innerHTML = '';

            const canvasLayer = document.createElement('div');
            canvasLayer.className = 'live2d-chat-stage__canvas';

            const canvasFrame = document.createElement('div');
            canvasFrame.id = 'live2dContainer';
            canvasFrame.className = 'live2d-chat-stage__canvas-frame';

            const sttOverlay = document.createElement('div');
            sttOverlay.id = 'sttOverlay';
            sttOverlay.className = 'live2d-chat-stage__stt';
            sttOverlay.setAttribute('role', 'status');

            const overlayRail = document.createElement('section');
            overlayRail.className = 'live2d-chat-stage__rail';
            overlayRail.setAttribute('aria-live', 'polite');
            overlayRail.setAttribute('aria-label', copyFor(DEFAULT_COPY.railTitle, this.locale));
            if (this.config.RAIL_CHROMELESS) {
                overlayRail.dataset.chromeless = 'true';
            }

            const loadOlderBtn = document.createElement('button');
            loadOlderBtn.type = 'button';
            loadOlderBtn.id = 'loadOlderBtn';
            loadOlderBtn.className = 'live2d-chat-stage__load-older';
            loadOlderBtn.textContent = copyFor(DEFAULT_COPY.loadOlder, this.locale);
            loadOlderBtn.setAttribute('aria-label', copyFor(DEFAULT_COPY.loadOlder, this.locale));

            const loadBar = document.createElement('div');
            loadBar.className = 'live2d-chat-stage__load-bar';
            loadBar.appendChild(loadOlderBtn);

            const messagesScroll = document.createElement('div');
            messagesScroll.id = 'chatMessages';
            messagesScroll.className = 'live2d-chat-stage__rail-scroll';
            messagesScroll.setAttribute('role', 'log');
            messagesScroll.setAttribute('aria-live', 'polite');
            messagesScroll.setAttribute('aria-relevant', 'additions');
            messagesScroll.setAttribute('tabindex', '0');

            const emptyState = document.createElement('div');
            emptyState.id = 'emptyState';
            emptyState.className = 'live2d-chat-stage__empty';
            emptyState.setAttribute('data-role', 'empty-state');

            const emptyEmoji = document.createElement('span');
            emptyEmoji.className = 'live2d-chat-stage__empty-emoji';
            emptyEmoji.textContent = '🤝';

            const emptyTitle = document.createElement('h3');
            emptyTitle.textContent = copyFor(DEFAULT_COPY.emptyTitle, this.locale);

            const emptyCopy = document.createElement('p');
            emptyCopy.textContent = copyFor(DEFAULT_COPY.emptySubtitle, this.locale);

            emptyState.appendChild(emptyEmoji);
            emptyState.appendChild(emptyTitle);
            emptyState.appendChild(emptyCopy);

            messagesScroll.appendChild(loadBar);
            messagesScroll.appendChild(emptyState);

            const scrollIndicator = document.createElement('button');
            scrollIndicator.type = 'button';
            scrollIndicator.id = 'scrollToBottomBtn';
            scrollIndicator.className = 'live2d-chat-stage__scroll-indicator';
            scrollIndicator.textContent = '⬇️';

            const composer = document.createElement('form');
            composer.id = 'inputArea';
            composer.className = 'live2d-chat-stage__composer';
            composer.autocomplete = 'off';

            composer.addEventListener('submit', (event) => {
                event.preventDefault();
                if (typeof global.sendMessage === 'function') {
                    global.sendMessage();
                }
            });

            const micButton = this._createIconButton(
                'micButton',
                '🎤',
                'voice-btn',
                copyFor(DEFAULT_COPY.micTitle, this.locale),
            );
            const ttsButton = this._createIconButton(
                'ttsButton',
                '🔊',
                'voice-btn',
                copyFor(DEFAULT_COPY.ttsTitle, this.locale),
            );

            const clearButton = this._createIconButton(
                'clearSessionButton',
                '🗑️',
                'clear-session-btn',
                copyFor(DEFAULT_COPY.clearTitle, this.locale),
            );

            const textareaContainer = document.createElement('div');
            textareaContainer.className = 'textarea-container';
            textareaContainer.style.position = 'relative';
            textareaContainer.style.display = 'flex';
            textareaContainer.style.flexDirection = 'column';
            textareaContainer.style.gap = '6px';

            const textarea = document.createElement('textarea');
            textarea.id = 'textInput';
            textarea.className = 'live2d-chat-stage__input';
            textarea.rows = 1;
            textarea.maxLength = 2000;
            textarea.spellcheck = true;
            textarea.placeholder = copyFor(DEFAULT_COPY.composerPlaceholder, this.locale);

            const charCounter = document.createElement('div');
            charCounter.id = 'charCounter';
            charCounter.className = 'live2d-chat-stage__char-counter';
            charCounter.textContent = '0/2000';
            charCounter.style.display = 'none';

            textareaContainer.appendChild(textarea);
            textareaContainer.appendChild(charCounter);

            const sendButton = document.createElement('button');
            sendButton.type = 'button';
            sendButton.className = 'send-btn live2d-chat-stage__send';
            sendButton.title = copyFor(DEFAULT_COPY.sendTitle, this.locale);
            sendButton.innerHTML = `<span>${copyFor(DEFAULT_COPY.sendLabel, this.locale)}</span>`;
            sendButton.disabled = true;
            sendButton.addEventListener('click', () => {
                if (typeof global.sendMessage === 'function') {
                    global.sendMessage();
                }
            });

            composer.appendChild(micButton);
            composer.appendChild(ttsButton);
            composer.appendChild(clearButton);
            composer.appendChild(textareaContainer);
            composer.appendChild(sendButton);

            canvasLayer.appendChild(canvasFrame);

            this.root.appendChild(canvasLayer);
            this.root.appendChild(sttOverlay);
            this.root.appendChild(overlayRail);
            overlayRail.appendChild(messagesScroll);
            this.root.appendChild(scrollIndicator);
            this.root.appendChild(composer);

            this.elements = {
                root: this.root,
                canvasLayer,
                canvasHost: canvasFrame,
                sttOverlay,
                rail: overlayRail,
                messagesScroll,
                loadOlderBtn,
                loadBar,
                scrollIndicator,
                composer,
                textarea,
                charCounter,
                micButton,
                ttsButton,
                clearButton,
                sendButton,
                emptyState,
            };
            this.elements.flashRail = (mode) => this.flashRail(mode);
            this.elements.applyFaceGuard = () => this.applyFaceGuard();

            this._initializeVisibilitySystem();
            this._bindFaceGuardObservers();
        }

        _createIconButton(id, glyph, className, title) {
            const button = document.createElement('button');
            button.type = 'button';
            button.id = id;
            button.className = className;
            button.textContent = glyph;
            if (title) {
                button.title = title;
            }
            return button;
        }

        _addListener(target, type, listener, options) {
            if (!target || !listener) {
                return;
            }
            target.addEventListener(type, listener, options);
            this._globalListeners.push({ target, type, listener, options });
        }

        _initializeVisibilitySystem() {
            if (!this.elements.rail) {
                return;
            }

            this._setRailVisibility('hidden', { force: true, immediate: true });

            if (this.config.VISIBILITY_MODE !== 'auto') {
                this._setRailVisibility('show', { force: true, immediate: true });
                return;
            }

            const interactiveTargets = [
                this.elements.rail,
                this.elements.messagesScroll,
                this.elements.composer,
                this.elements.textarea,
                this.elements.micButton,
                this.elements.ttsButton,
                this.elements.clearButton,
                this.elements.sendButton,
                this.elements.canvasHost,
            ].filter(Boolean);

            interactiveTargets.forEach((node) => {
                this._addListener(node, 'pointerdown', this._boundHandleInteraction, { passive: true });
                this._addListener(node, 'pointerenter', this._boundHandleInteraction, { passive: true });
                this._addListener(node, 'touchstart', this._boundHandleInteraction, { passive: true });
            });

            if (this.elements.messagesScroll) {
                this._addListener(this.elements.messagesScroll, 'wheel', this._boundHandleInteraction, { passive: true });
                this._addListener(this.elements.messagesScroll, 'scroll', this._boundHandleInteraction, { passive: true });
            }

            if (this.elements.composer) {
                this._addListener(this.elements.composer, 'focusin', this._boundHandleInteraction);
                this._addListener(this.elements.composer, 'focusout', this._boundIdleCountdown);
                this._addListener(this.elements.composer, 'pointerleave', this._boundIdleCountdown, { passive: true });
            }

            if (this.elements.rail) {
                this._addListener(this.elements.rail, 'focusin', this._boundHandleInteraction);
                this._addListener(this.elements.rail, 'pointerleave', this._boundIdleCountdown, { passive: true });
            }

            if (this.elements.textarea) {
                this._addListener(this.elements.textarea, 'focus', this._boundHandleInteraction);
                this._addListener(this.elements.textarea, 'blur', this._boundIdleCountdown);
            }

            if (this.elements.canvasHost) {
                this._addListener(this.elements.canvasHost, 'pointerdown', this._boundHandleInteraction, { passive: true });
                this._addListener(this.elements.canvasHost, 'pointerenter', this._boundHandleInteraction, { passive: true });
                this._addListener(this.elements.canvasHost, 'pointerleave', this._boundIdleCountdown, { passive: true });
            }

            this._addListener(this.root, 'pointerleave', this._boundIdleCountdown, { passive: true });
        }

        _setRailVisibility(mode, options = {}) {
            const validModes = ['hidden', 'peek', 'show'];
            const targetMode = validModes.includes(mode) ? mode : 'show';
            if (this.state.visibility === targetMode && !options.force) {
                return;
            }

            this.state.visibility = targetMode;
            this.root.dataset.railVisibility = targetMode;

            if (targetMode === 'hidden') {
                this._clearVisibilityTimers();
            } else if (options.resetTimers) {
                this._scheduleVisibilityTimers();
            }

            if (!options.immediate) {
                this._applyFaceGuard();
            }
        }

        _clearVisibilityTimers() {
            if (this.state.peekTimer) {
                clearTimeout(this.state.peekTimer);
                this.state.peekTimer = null;
            }
            if (this.state.hideTimer) {
                clearTimeout(this.state.hideTimer);
                this.state.hideTimer = null;
            }
        }

        _scheduleVisibilityTimers() {
            if (this.config.VISIBILITY_MODE !== 'auto') {
                return;
            }
            this._clearVisibilityTimers();
            const idleMs = Math.max(1, this.config.IDLE_DIM_SECONDS || 2) * 1000;
            this.state.peekTimer = window.setTimeout(() => {
                if (this.state.visibility === 'show') {
                    this._setRailVisibility('peek', { force: true, immediate: true });
                }
            }, idleMs);
            this.state.hideTimer = window.setTimeout(() => {
                if (this.state.visibility !== 'hidden') {
                    this._setRailVisibility('hidden', { force: true, immediate: true });
                }
            }, idleMs * 2);
        }

        _handleInteraction() {
            this._setRailVisibility('show', { force: true, immediate: true });
            this._scheduleVisibilityTimers();
        }

        _startIdleCountdown() {
            if (this.config.VISIBILITY_MODE !== 'auto') {
                return;
            }
            if (this.state.visibility === 'hidden') {
                return;
            }
            this._scheduleVisibilityTimers();
        }

        flashRail(mode = 'show') {
            if (mode === 'hidden') {
                this._setRailVisibility('hidden', { force: true });
                return;
            }
            if (mode === 'peek') {
                this._setRailVisibility('peek', { force: true });
                return;
            }
            this._handleInteraction();
        }

        applyFaceGuard() {
            this._applyFaceGuard();
        }

        _bindFaceGuardObservers() {
            this._applyFaceGuard();
            this._faceGuardRaf = requestAnimationFrame(() => this._applyFaceGuard());

            if (typeof ResizeObserver !== 'undefined' && this.elements.rail) {
                this._railResizeObserver = new ResizeObserver(() => this._applyFaceGuard());
                this._railResizeObserver.observe(this.elements.rail);
            }

            this._addListener(window, 'resize', this._boundFaceGuard);
            this._addListener(window, 'orientationchange', this._boundFaceGuard);
        }

        _applyFaceGuard() {
            if (!this.elements.rail || !this.elements.canvasHost) {
                return;
            }

            const stageRect = this.root.getBoundingClientRect();
            const canvasRect = this.elements.canvasHost.getBoundingClientRect();
            const safeTop = parseFloat(getComputedStyle(this.root).getPropertyValue('--live2d-safe-top')) || 0;
            const fallbackTop = safeTop + 12;
            const faceGuard = typeof this.config.FACE_GUARD_PCT === 'number' ? this.config.FACE_GUARD_PCT : 0.25;
            const fallbackGuard = 0.30;
            const railHeight = this.elements.rail.offsetHeight || 0;

            let topRelative = fallbackTop;

            if (canvasRect.height && stageRect.height) {
                const canvasTopRelative = canvasRect.top - stageRect.top;
                const permittedBottom = canvasTopRelative + (canvasRect.height * faceGuard);
                const fallbackBottom = canvasTopRelative + (canvasRect.height * fallbackGuard);

                if (Number.isFinite(permittedBottom)) {
                    const maxTop = permittedBottom - railHeight;
                    if (Number.isFinite(maxTop)) {
                        topRelative = Math.min(topRelative, maxTop);
                    }
                }

                if (Number.isFinite(fallbackBottom)) {
                    const fallbackMaxTop = fallbackBottom - railHeight;
                    if (Number.isFinite(fallbackMaxTop)) {
                        topRelative = Math.min(topRelative, fallbackMaxTop);
                    }
                }
            }

            if (!Number.isFinite(topRelative)) {
                topRelative = fallbackTop;
            }

            topRelative = Math.max(topRelative, fallbackTop);
            if (topRelative < 0) {
                topRelative = 0;
            }

            this.elements.rail.style.top = `${topRelative}px`;
        }

        _attachViewportListeners() {
            if (!window.visualViewport) {
                return;
            }

            const updateKeyboardOffset = () => {
                const vv = window.visualViewport;
                if (!vv) return;

                const visualBottom = vv.height + vv.offsetTop;
                const keyboardOffset = Math.max(0, window.innerHeight - visualBottom);
                this.root.style.setProperty('--live2d-keyboard-offset', `${keyboardOffset}px`);
                if (keyboardOffset > 20) {
                    this.root.dataset.keyboard = 'raised';
                } else {
                    this.root.dataset.keyboard = '';
                }
            };

            const listeners = [
                { type: 'resize', listener: updateKeyboardOffset },
                { type: 'scroll', listener: updateKeyboardOffset },
            ];

            listeners.forEach(({ type, listener }) => {
                window.visualViewport.addEventListener(type, listener);
                this._viewportListeners.push({ type, listener });
            });

            updateKeyboardOffset();
        }
    }

    global.Live2DChatStage = Live2DChatStage;
})(window);
