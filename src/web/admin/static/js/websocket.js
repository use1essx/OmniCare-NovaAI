// Healthcare AI V2 Admin WebSocket Client
// Real-time communication for dashboard updates

class AdminWebSocketClient {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // Start with 1 second
        this.heartbeatInterval = null;
        this.messageHandlers = new Map();
        this.connectionHandlers = {
            onOpen: [],
            onClose: [],
            onError: [],
            onReconnect: []
        };
        
        // Bind methods
        this.connect = this.connect.bind(this);
        this.disconnect = this.disconnect.bind(this);
        this.send = this.send.bind(this);
        this.handleMessage = this.handleMessage.bind(this);
        this.handleOpen = this.handleOpen.bind(this);
        this.handleClose = this.handleClose.bind(this);
        this.handleError = this.handleError.bind(this);
    }
    
    // Connect to WebSocket
    connect() {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }
        
        try {
            console.log('Connecting to WebSocket:', this.url);
            this.socket = new WebSocket(this.url);
            
            this.socket.addEventListener('open', this.handleOpen);
            this.socket.addEventListener('message', this.handleMessage);
            this.socket.addEventListener('close', this.handleClose);
            this.socket.addEventListener('error', this.handleError);
        } catch (error) {
            console.error('Failed to create WebSocket connection:', error);
            this.scheduleReconnect();
        }
    }
    
    // Disconnect from WebSocket
    disconnect() {
        this.isConnected = false;
        this.stopHeartbeat();
        
        if (this.socket) {
            this.socket.removeEventListener('open', this.handleOpen);
            this.socket.removeEventListener('message', this.handleMessage);
            this.socket.removeEventListener('close', this.handleClose);
            this.socket.removeEventListener('error', this.handleError);
            
            if (this.socket.readyState === WebSocket.OPEN) {
                this.socket.close();
            }
            this.socket = null;
        }
    }
    
    // Send message to server
    send(message) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
            this.socket.send(messageStr);
            return true;
        } else {
            console.warn('WebSocket not connected, cannot send message:', message);
            return false;
        }
    }
    
    // Handle connection open
    handleOpen(event) {
        console.log('WebSocket connected successfully');
        this.isConnected = true;
        this.reconnectAttempts = 0;
        this.reconnectDelay = 1000;
        
        this.startHeartbeat();
        this.triggerConnectionHandlers('onOpen', event);
    }
    
    // Handle incoming messages
    handleMessage(event) {
        try {
            const message = JSON.parse(event.data);
            console.log('WebSocket message received:', message);
            
            // Handle built-in message types
            switch (message.type) {
                case 'ping':
                    this.send({ type: 'pong' });
                    break;
                case 'pong':
                    // Heartbeat response - connection is alive
                    break;
                default:
                    // Trigger registered message handlers
                    this.triggerMessageHandlers(message.type, message);
            }
        } catch (error) {
            console.error('Error parsing WebSocket message:', error);
        }
    }
    
    // Handle connection close
    handleClose(event) {
        console.log('WebSocket connection closed:', event.code, event.reason);
        this.isConnected = false;
        this.stopHeartbeat();
        
        this.triggerConnectionHandlers('onClose', event);
        
        // Schedule reconnection if it wasn't a clean close
        if (event.code !== 1000) {
            this.scheduleReconnect();
        }
    }
    
    // Handle connection error
    handleError(event) {
        console.error('WebSocket error:', event);
        this.triggerConnectionHandlers('onError', event);
    }
    
    // Schedule reconnection with exponential backoff
    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            return;
        }
        
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        
        console.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            console.log(`Reconnection attempt ${this.reconnectAttempts}`);
            this.triggerConnectionHandlers('onReconnect', { attempt: this.reconnectAttempts });
            this.connect();
        }, delay);
    }
    
    // Start heartbeat to keep connection alive
    startHeartbeat() {
        this.stopHeartbeat();
        this.heartbeatInterval = setInterval(() => {
            if (this.isConnected) {
                this.send({ type: 'ping' });
            }
        }, 30000); // Send ping every 30 seconds
    }
    
    // Stop heartbeat
    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
            this.heartbeatInterval = null;
        }
    }
    
    // Register message handler
    on(messageType, handler) {
        if (!this.messageHandlers.has(messageType)) {
            this.messageHandlers.set(messageType, []);
        }
        this.messageHandlers.get(messageType).push(handler);
    }
    
    // Unregister message handler
    off(messageType, handler) {
        if (this.messageHandlers.has(messageType)) {
            const handlers = this.messageHandlers.get(messageType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    // Register connection event handler
    onConnection(event, handler) {
        if (this.connectionHandlers[event]) {
            this.connectionHandlers[event].push(handler);
        }
    }
    
    // Trigger message handlers
    triggerMessageHandlers(messageType, message) {
        if (this.messageHandlers.has(messageType)) {
            this.messageHandlers.get(messageType).forEach(handler => {
                try {
                    handler(message);
                } catch (error) {
                    console.error('Error in message handler:', error);
                }
            });
        }
    }
    
    // Trigger connection handlers
    triggerConnectionHandlers(event, data) {
        if (this.connectionHandlers[event]) {
            this.connectionHandlers[event].forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error('Error in connection handler:', error);
                }
            });
        }
    }
    
    // Get connection status
    getStatus() {
        return {
            isConnected: this.isConnected,
            reconnectAttempts: this.reconnectAttempts,
            readyState: this.socket ? this.socket.readyState : WebSocket.CLOSED
        };
    }
}

// Admin Dashboard WebSocket Manager
class AdminDashboardWebSocket {
    constructor() {
        this.client = null;
        this.metrics = {};
        this.lastUpdate = null;
        this.isInitialized = false;
        
        // Event callbacks
        this.onMetricsUpdate = null;
        this.onUploadProgress = null;
        this.onAlert = null;
        this.onConnectionChange = null;
    }
    
    // Initialize WebSocket connection
    initialize(wsUrl) {
        if (this.isInitialized) {
            console.log('WebSocket already initialized');
            return;
        }
        
        this.client = new AdminWebSocketClient(wsUrl);
        
        // Register message handlers
        this.client.on('initial_metrics', (message) => {
            this.handleMetricsUpdate(message.data, true);
        });
        
        this.client.on('metrics_update', (message) => {
            this.handleMetricsUpdate(message.data, false);
        });
        
        this.client.on('upload_progress', (message) => {
            this.handleUploadProgress(message.data);
        });
        
        this.client.on('alert', (message) => {
            this.handleAlert(message);
        });
        
        // Register connection event handlers
        this.client.onConnection('onOpen', () => {
            console.log('Admin dashboard WebSocket connected');
            if (this.onConnectionChange) {
                this.onConnectionChange(true);
            }
        });
        
        this.client.onConnection('onClose', () => {
            console.log('Admin dashboard WebSocket disconnected');
            if (this.onConnectionChange) {
                this.onConnectionChange(false);
            }
        });
        
        this.client.onConnection('onError', (event) => {
            console.error('Admin dashboard WebSocket error:', event);
        });
        
        this.client.onConnection('onReconnect', (data) => {
            console.log(`Admin dashboard WebSocket reconnecting (attempt ${data.attempt})`);
        });
        
        // Connect
        this.client.connect();
        this.isInitialized = true;
    }
    
    // Handle metrics update
    handleMetricsUpdate(data, isInitial = false) {
        this.metrics = data;
        this.lastUpdate = new Date();
        
        console.log('Metrics updated:', data);
        
        if (this.onMetricsUpdate) {
            this.onMetricsUpdate(data, isInitial);
        }
        
        // Trigger chart updates if function exists
        if (typeof window.updateDashboardCharts === 'function') {
            window.updateDashboardCharts(data);
        }
    }
    
    // Handle upload progress
    handleUploadProgress(data) {
        console.log('Upload progress:', data);
        
        if (this.onUploadProgress) {
            this.onUploadProgress(data);
        }
        
        // Update UI elements
        const progressElement = document.getElementById(`upload-progress-${data.upload_id}`);
        if (progressElement) {
            const progressBar = progressElement.querySelector('.progress-bar');
            const statusText = progressElement.querySelector('.status-text');
            
            if (progressBar) {
                progressBar.style.width = `${data.progress}%`;
            }
            
            if (statusText) {
                statusText.textContent = data.message;
            }
        }
    }
    
    // Handle alerts
    handleAlert(data) {
        console.log('Alert received:', data);
        
        if (this.onAlert) {
            this.onAlert(data);
        }
        
        // Show notification if Alpine.js store is available
        if (window.Alpine && Alpine.store('admin')) {
            Alpine.store('admin').showNotification(
                data.title,
                data.message,
                data.level || 'info'
            );
        }
    }
    
    // Request fresh metrics
    requestMetrics() {
        if (this.client && this.client.isConnected) {
            this.client.send({ type: 'request_metrics' });
        }
    }
    
    // Send message to server
    send(message) {
        if (this.client) {
            return this.client.send(message);
        }
        return false;
    }
    
    // Get connection status
    getStatus() {
        if (this.client) {
            return this.client.getStatus();
        }
        return { isConnected: false, reconnectAttempts: 0, readyState: WebSocket.CLOSED };
    }
    
    // Get current metrics
    getMetrics() {
        return this.metrics;
    }
    
    // Get last update time
    getLastUpdate() {
        return this.lastUpdate;
    }
    
    // Disconnect
    disconnect() {
        if (this.client) {
            this.client.disconnect();
        }
        this.isInitialized = false;
    }
}

// Global WebSocket instance
window.adminWebSocket = new AdminDashboardWebSocket();

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Get WebSocket URL from page or default
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = window.websocketUrl || `${protocol}//${window.location.host}/admin/ws/dashboard`;
    
    // Initialize WebSocket
    window.adminWebSocket.initialize(wsUrl);
    
    // Set up callbacks if Alpine.js is available
    if (window.Alpine) {
        window.adminWebSocket.onConnectionChange = (isConnected) => {
            if (Alpine.store('admin')) {
                Alpine.store('admin').isConnected = isConnected;
            }
        };
        
        window.adminWebSocket.onMetricsUpdate = (data, isInitial) => {
            if (Alpine.store('admin')) {
                Alpine.store('admin').updateMetrics(data);
            }
        };
        
        window.adminWebSocket.onAlert = (data) => {
            if (Alpine.store('admin')) {
                Alpine.store('admin').showNotification(
                    data.title,
                    data.message,
                    data.level || 'info'
                );
            }
        };
    }
    
    console.log('Admin WebSocket client initialized');
});

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    if (window.adminWebSocket) {
        window.adminWebSocket.disconnect();
    }
});
