// Healthcare AI V2 Admin Dashboard JavaScript
// Alpine.js components and utilities

// Global Alpine.js store for admin state
document.addEventListener('alpine:init', () => {
    // Global admin app state
    Alpine.store('admin', {
        // UI state
        sidebarOpen: false,
        loading: false,
        loadingMessage: 'Loading...',
        
        // Notifications
        notifications: [],
        notificationId: 0,
        
        // WebSocket connection
        websocket: null,
        isConnected: false,
        reconnectAttempts: 0,
        maxReconnectAttempts: 5,
        
        // Metrics data
        metrics: {},
        lastUpdate: null,
        
        // Charts
        charts: {},
        
        // Initialize the app
        init() {
            this.initWebSocket();
            this.loadInitialData();
            this.setupPeriodicUpdates();
        },
        
        // WebSocket connection management
        initWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const defaultUrl = `${protocol}//${window.location.host}/admin/ws/dashboard`;
            const wsUrl = window.websocketUrl || defaultUrl;
            
            try {
                this.websocket = new WebSocket(wsUrl);
                
                this.websocket.onopen = () => {
                    console.log('WebSocket connected');
                    this.isConnected = true;
                    this.reconnectAttempts = 0;
                    this.showNotification('Connected', 'Real-time updates active', 'success');
                };
                
                this.websocket.onmessage = (event) => {
                    this.handleWebSocketMessage(JSON.parse(event.data));
                };
                
                this.websocket.onclose = () => {
                    console.log('WebSocket disconnected');
                    this.isConnected = false;
                    this.scheduleReconnect();
                };
                
                this.websocket.onerror = (error) => {
                    console.error('WebSocket error:', error);
                    this.showNotification('Connection Error', 'Real-time updates unavailable', 'error');
                };
            } catch (error) {
                console.error('Failed to initialize WebSocket:', error);
                this.showNotification('Connection Failed', 'Unable to connect for real-time updates', 'error');
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
                    console.log('Unknown message type:', message.type);
            }
        },
        
        // Update metrics data
        updateMetrics(newMetrics) {
            this.metrics = newMetrics;
            this.lastUpdate = new Date();
            
            // Trigger chart updates
            if (typeof window.updateDashboardCharts === 'function') {
                window.updateDashboardCharts(this.metrics);
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
                this.showNotification('Connection Lost', 'Unable to restore real-time updates', 'error');
            }
        },
        
        // Load initial data
        async loadInitialData() {
            try {
                this.loading = true;
                this.loadingMessage = 'Loading dashboard data...';
                
                await this.refreshMetrics();
                
            } catch (error) {
                console.error('Error loading initial data:', error);
                this.showNotification('Load Error', 'Failed to load dashboard data', 'error');
            } finally {
                this.loading = false;
            }
        },
        
        // Refresh metrics manually
        async refreshMetrics() {
            try {
                const response = await fetch('/api/v1/admin/metrics');
                if (response.ok) {
                    const metrics = await response.json();
                    this.updateMetrics(metrics);
                }
            } catch (error) {
                console.error('Error refreshing metrics:', error);
            }
        },
        
        // Setup periodic updates
        setupPeriodicUpdates() {
            setInterval(() => {
                if (!this.isConnected) {
                    this.refreshMetrics();
                }
                
                // Send ping to keep WebSocket alive
                if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                    this.websocket.send(JSON.stringify({ type: 'ping' }));
                }
            }, 30000); // Every 30 seconds
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
        },
        
        removeNotification(id) {
            this.notifications = this.notifications.filter(n => n.id !== id);
        }
    });
    
    // Utility functions for Alpine.js
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
                case 'healthy': case 'secure': case 'online': return 'status-healthy';
                case 'warning': case 'degraded': return 'status-warning';
                case 'error': case 'critical': case 'offline': return 'status-error';
                default: return 'status-unknown';
            }
        };
    });
});

// Main admin app component
function adminApp() {
    return {
        // Access the global store
        get sidebarOpen() { return this.$store.admin.sidebarOpen; },
        set sidebarOpen(value) { this.$store.admin.sidebarOpen = value; },
        
        get loading() { return this.$store.admin.loading; },
        get loadingMessage() { return this.$store.admin.loadingMessage; },
        get notifications() { return this.$store.admin.notifications; },
        get isConnected() { return this.$store.admin.isConnected; },
        get metrics() { return this.$store.admin.metrics; },
        get lastUpdate() { return this.$store.admin.lastUpdate; },
        
        // Initialize the app
        initApp() {
            this.$store.admin.init();
            
            // Parse initial metrics if provided
            if (window.initialMetrics) {
                try {
                    this.$store.admin.updateMetrics(window.initialMetrics);
                } catch (e) {
                    console.error('Error parsing initial metrics:', e);
                }
            }
        },
        
        // Delegate methods to store
        refreshMetrics() {
            return this.$store.admin.refreshMetrics();
        },
        
        showNotification(title, message, type, duration) {
            return this.$store.admin.showNotification(title, message, type, duration);
        },
        
        removeNotification(id) {
            return this.$store.admin.removeNotification(id);
        },
        
        // Utility methods
        formatNumber(num) {
            return this.$formatNumber(num);
        },
        
        formatPercent(num) {
            return this.$formatPercent(num);
        },
        
        formatDuration(seconds) {
            return this.$formatDuration(seconds);
        },
        
        timeAgo(timestamp) {
            return this.$timeAgo(timestamp);
        },
        
        getStatusClass(status) {
            return this.$getStatusClass(status);
        }
    };
}

// File upload component
Alpine.data('fileUpload', () => ({
    uploading: false,
    progress: 0,
    error: null,
    success: false,
    
    async uploadFile(file, category, description) {
        this.uploading = true;
        this.progress = 0;
        this.error = null;
        this.success = false;
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('category', category);
            formData.append('description', description);
            
            const response = await fetch('/api/v1/admin/upload', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                this.success = true;
                this.progress = 100;
                Alpine.store('admin').showNotification(
                    'Upload Successful',
                    `File "${file.name}" uploaded successfully`,
                    'success'
                );
            } else {
                throw new Error(`Upload failed: ${response.statusText}`);
            }
        } catch (error) {
            this.error = error.message;
            Alpine.store('admin').showNotification(
                'Upload Failed',
                error.message,
                'error'
            );
        } finally {
            this.uploading = false;
        }
    }
}));

// Data table component
Alpine.data('dataTable', (initialData = []) => ({
    data: initialData,
    filteredData: [],
    searchTerm: '',
    sortField: '',
    sortDirection: 'asc',
    currentPage: 1,
    itemsPerPage: 10,
    
    init() {
        this.filteredData = this.data;
        this.$watch('searchTerm', () => this.filterData());
    },
    
    filterData() {
        if (!this.searchTerm) {
            this.filteredData = this.data;
        } else {
            this.filteredData = this.data.filter(item => 
                Object.values(item).some(value => 
                    String(value).toLowerCase().includes(this.searchTerm.toLowerCase())
                )
            );
        }
        this.currentPage = 1;
    },
    
    sortBy(field) {
        if (this.sortField === field) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortField = field;
            this.sortDirection = 'asc';
        }
        
        this.filteredData.sort((a, b) => {
            const aVal = a[field];
            const bVal = b[field];
            const modifier = this.sortDirection === 'asc' ? 1 : -1;
            
            if (aVal < bVal) return -1 * modifier;
            if (aVal > bVal) return 1 * modifier;
            return 0;
        });
    },
    
    get paginatedData() {
        const start = (this.currentPage - 1) * this.itemsPerPage;
        const end = start + this.itemsPerPage;
        return this.filteredData.slice(start, end);
    },
    
    get totalPages() {
        return Math.ceil(this.filteredData.length / this.itemsPerPage);
    },
    
    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.currentPage++;
        }
    },
    
    prevPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
        }
    }
}));

// Global utility functions
window.formatBytes = function(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
};

window.createGradientBackground = function(ctx, color1, color2) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 400);
    gradient.addColorStop(0, color1);
    gradient.addColorStop(1, color2);
    return gradient;
};

// Chart theme configuration
window.chartTheme = {
    colors: {
        primary: '#2563eb',
        success: '#059669',
        warning: '#d97706',
        danger: '#dc2626',
        info: '#0284c7',
        gray: '#6b7280'
    },
    
    getGradient(ctx, color) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, color + '40'); // 25% opacity
        gradient.addColorStop(1, color + '00'); // 0% opacity
        return gradient;
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Set global initial metrics if provided
    if (typeof initialMetrics !== 'undefined') {
        window.initialMetrics = initialMetrics;
    }
    
    console.log('Healthcare AI V2 Admin Dashboard loaded');
});
