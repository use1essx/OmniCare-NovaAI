/**
 * Healthcare AI V2 Admin State Manager
 * Centralized Alpine.js stores and state management
 */

document.addEventListener('alpine:init', () => {
    // Global admin state store
    Alpine.store('admin', {
        // UI state
        loading: false,
        loadingMessage: 'Loading...',
        sidebarOpen: false,
        
        // Metrics cache
        metrics: {
            users: {
                total: 0,
                active: 0,
                admin: 0,
                new_today: 0
            },
            system: {
                status: 'unknown',
                cpu_percent: 0,
                memory_percent: 0,
                disk_percent: 0,
                uptime_hours: 0
            },
            pipeline: {
                status: 'unknown',
                sources_online: 0,
                total_sources: 0,
                data_freshness_minutes: 0
            },
            security: {
                status: 'unknown',
                failed_logins_hour: 0,
                alerts_today: 0
            }
        },
        
        // Cache management
        cache: new Map(),
        cacheTimeout: 30000, // 30 seconds
        
        // Notification system
        notifications: [],
        notificationId: 0,
        
        // WebSocket connection
        websocket: null,
        isConnected: false,
        reconnectAttempts: 0,
        maxReconnectAttempts: 5,
        
        // Initialize the store
        init() {
            // Disable WebSocket for now - not implemented yet
            // this.initWebSocket();
            this.setupPeriodicRefresh();
            this.refreshMetrics(); // Load initial data
        },
        
        // WebSocket connection management
        initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/admin/ws/dashboard`;
            
            try {
                this.websocket = new WebSocket(wsUrl);
                
                this.websocket.onopen = () => {
                    console.log('Admin WebSocket connected');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    // Don't show notification for connection success
                };
                
                this.websocket.onmessage = (event) => {
                    this.handleWebSocketMessage(JSON.parse(event.data));
                };
                
                this.websocket.onclose = () => {
                    console.log('Admin WebSocket disconnected');
                    this.isConnected = false;
                    this.scheduleReconnect();
                };
                
                this.websocket.onerror = (error) => {
                    console.warn('Admin WebSocket error:', error);
                    // Don't show error notification - WebSocket is optional
                };
            } catch (error) {
                console.warn('Failed to initialize WebSocket:', error);
                // Don't show error notification - WebSocket is optional
            }
        },
        
        // Handle WebSocket messages
        handleWebSocketMessage(message) {
            switch (message.type) {
                case 'initial_metrics':
                case 'metrics_update':
                    this.updateMetrics(message.data);
                    break;
                case 'upload_progress':
                    this.handleUploadProgress(message.data);
                    break;
                case 'alert':
                    this.showNotification(message.title, message.message, message.level);
                    break;
                case 'pong':
                    // Handle ping/pong for connection health
                    break;
                default:
                    console.log('Unknown WebSocket message type:', message.type);
            }
        },
        
        // Schedule WebSocket reconnection
        scheduleReconnect() {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                const delay = Math.pow(2, this.reconnectAttempts) * 1000; // Exponential backoff
                this.reconnectAttempts++;
                
                setTimeout(() => {
                    console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                    this.initWebSocket();
                }, delay);
            } else {
                console.warn('Max WebSocket reconnection attempts reached');
                // Don't show error notification - WebSocket is optional
            }
        },
        
        // Setup periodic refresh for when WebSocket is not available
        setupPeriodicRefresh() {
            setInterval(() => {
                if (!this.isConnected && !this.loading) {
                    this.refreshMetrics();
                }
                
                // Send ping to keep WebSocket alive
                if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                    this.websocket.send(JSON.stringify({ type: 'ping' }));
                }
            }, 10000); // Every 10 seconds for more responsive updates
        },
        
        // Refresh all metrics
        async refreshMetrics() {
            if (this.loading) return;
            
            this.loading = true;
            this.loadingMessage = 'Loading dashboard data...';
            
            try {
                // Call the actual dashboard stats API
                const response = await fetch('/admin/api/dashboard/stats');
                
                if (response.ok) {
                    const data = await response.json();
                    
                    // Update metrics with the new data structure
                    this.updateMetrics({
                        users: data.users || { total: 0, active: 0 },
                        system: data.system || { status: 'unknown', cpu_percent: 0, memory_percent: 0 },
                        pipeline: data.pipeline || { error_rate: 0 },
                        security: data.security || { alerts_today: 0 },
                        ai: data.ai || { active_agents: 0 }
                    });
                    
                    // Update organizations and models (add to metrics root)
                    this.metrics.organizations = data.organizations || 0;
                    this.metrics.models = data.models || 0;
                    
                    // Update last update timestamp
                    this.lastUpdate = new Date().toISOString();
                    
                    // Set connected status to true since API responded
                    this.isConnected = true;
                    
                    console.log('✅ Dashboard metrics updated successfully');
                } else {
                    console.warn(`Dashboard API returned ${response.status}`);
                    // Set disconnected if API fails
                    this.isConnected = false;
                }
                
            } catch (error) {
                console.warn('Error refreshing metrics (dashboard will show zeros):', error);
                // Set disconnected on error
                this.isConnected = false;
                
                // Use fallback data
                this.updateMetrics({
                    users: { total: 0, active: 0 },
                    system: { status: 'unknown', cpu_percent: 0, memory_percent: 0 },
                    pipeline: { error_rate: 0 },
                    security: { alerts_today: 0 },
                    ai: { active_agents: 0 }
                });
            } finally {
                this.loading = false;
            }
        },
        
        // Update metrics data
        updateMetrics(newMetrics) {
            this.metrics = { ...this.metrics, ...newMetrics };
            
            // Trigger chart updates if available
            if (typeof window.updateDashboardCharts === 'function') {
                window.updateDashboardCharts(this.metrics);
            }
            
            // Dispatch custom event for components to listen to
            window.dispatchEvent(new CustomEvent('admin:metrics-updated', {
                detail: this.metrics
            }));
        },
        
        // Handle upload progress updates
        handleUploadProgress(data) {
            window.dispatchEvent(new CustomEvent('admin:upload-progress', {
                detail: data
            }));
        },
        
        // Cache management
        async getCachedData(key, fetcher) {
            const cached = this.cache.get(key);
            const now = Date.now();
            
            if (cached && (now - cached.timestamp) < this.cacheTimeout) {
                return cached.data;
            }
            
            try {
                const data = await fetcher();
                this.cache.set(key, {
                    data,
                    timestamp: now
                });
                
                return data;
            } catch (error) {
                // Return cached data if available, even if expired
                if (cached) {
                    console.warn(`Using stale cache for ${key} due to fetch error:`, error.message);
                    return cached.data;
                }
                // Re-throw if no cache available
                throw error;
            }
        },
        
        // Clear cache
        clearCache() {
            this.cache.clear();
        },
        
        // Notification system
        showNotification(title, message, type = 'info', duration = 5000) {
            const notification = {
                id: ++this.notificationId,
                title,
                message,
                type,
                timestamp: new Date()
            };
            
            this.notifications.push(notification);
            
            // Auto-remove after duration
            if (duration > 0) {
                setTimeout(() => {
                    this.removeNotification(notification.id);
                }, duration);
            }
            
            // Dispatch custom event
            window.dispatchEvent(new CustomEvent('admin:notification', {
                detail: notification
            }));
        },
        
        removeNotification(id) {
            this.notifications = this.notifications.filter(n => n.id !== id);
        },
        
        // Toggle sidebar
        toggleSidebar() {
            this.sidebarOpen = !this.sidebarOpen;
        },
        
        // Set loading state
        setLoading(loading, message = 'Loading...') {
            this.loading = loading;
            this.loadingMessage = message;
        }
    });
    
    // Utility magic methods
    Alpine.magic('formatNumber', () => {
        return (num) => {
            if (num >= 1000000) {
                return (num / 1000000).toFixed(1) + 'M';
            }
            if (num >= 1000) {
                return (num / 1000).toFixed(1) + 'K';
            }
            return num.toString();
        };
    });
    
    Alpine.magic('formatPercent', () => {
        return (num) => Math.round(num) + '%';
    });
    
    Alpine.magic('formatDuration', () => {
        return (seconds) => {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
        };
    });
    
    Alpine.magic('timeAgo', () => {
        return (timestamp) => {
            const now = new Date();
            const time = new Date(timestamp);
            const diff = now - time;
            
            const minutes = Math.floor(diff / 60000);
            const hours = Math.floor(diff / 3600000);
            const days = Math.floor(diff / 86400000);
            
            if (days > 0) return `${days}d ago`;
            if (hours > 0) return `${hours}h ago`;
            if (minutes > 0) return `${minutes}m ago`;
            return 'Just now';
        };
    });
    
    Alpine.magic('getStatusClass', () => {
        return (status) => {
            switch (status) {
                case 'healthy': case 'secure': case 'online': return 'text-green-600 bg-green-100';
                case 'warning': case 'degraded': return 'text-yellow-600 bg-yellow-100';
                case 'error': case 'critical': case 'offline': return 'text-red-600 bg-red-100';
                default: return 'text-gray-600 bg-gray-100';
            }
        };
    });
    
    Alpine.magic('getStatusIcon', () => {
        return (status) => {
            switch (status) {
                case 'healthy': case 'secure': case 'online': return 'fas fa-check-circle';
                case 'warning': case 'degraded': return 'fas fa-exclamation-triangle';
                case 'error': case 'critical': case 'offline': return 'fas fa-times-circle';
                default: return 'fas fa-question-circle';
            }
        };
    });
});

// Global utility functions
window.adminUtils = {
    // Format file size
    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },
    
    // Create gradient background for charts
    createGradientBackground(ctx, color1, color2) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, color1);
        gradient.addColorStop(1, color2);
        return gradient;
    },
    
    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // Throttle function
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};
