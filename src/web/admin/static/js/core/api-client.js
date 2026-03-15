/**
 * Healthcare AI V2 Admin API Client
 * Centralized API client for all admin operations
 */

class AdminAPIClient {
    constructor() {
        this.baseURL = '/api/v1/admin';
        this.timeout = 30000; // 30 seconds
    }

    /**
     * Make authenticated GET request
     */
    async get(endpoint, options = {}) {
        return this._request('GET', endpoint, null, options);
    }

    /**
     * Make authenticated POST request
     */
    async post(endpoint, data, options = {}) {
        return this._request('POST', endpoint, data, options);
    }

    /**
     * Make authenticated PUT request
     */
    async put(endpoint, data, options = {}) {
        return this._request('PUT', endpoint, data, options);
    }

    /**
     * Make authenticated DELETE request
     */
    async delete(endpoint, options = {}) {
        return this._request('DELETE', endpoint, null, options);
    }

    /**
     * Core request method with authentication and error handling
     */
    async _request(method, endpoint, data, options = {}) {
        const token = this._getAuthToken();
        
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const requestOptions = {
            method,
            headers,
            ...options
        };

        if (data && method !== 'GET') {
            requestOptions.body = JSON.stringify(data);
        }

        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.timeout);
            
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                ...requestOptions,
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            // Handle authentication errors
            if (response.status === 401) {
                this._handleAuthError();
                throw new Error('Authentication required');
            }

            // Handle authorization errors
            if (response.status === 403) {
                throw new Error('Insufficient permissions');
            }

            // Handle other HTTP errors
            if (!response.ok) {
                const errorText = await response.text();
                let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
                
                try {
                    const errorData = JSON.parse(errorText);
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch {
                    // Use default error message if JSON parsing fails
                }
                
                throw new Error(errorMessage);
            }

            // Parse response
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            
            return await response.text();

        } catch (error) {
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }
            
            console.error(`API Error [${method} ${endpoint}]:`, error);
            throw error;
        }
    }

    /**
     * Get authentication token from localStorage
     */
    _getAuthToken() {
        return localStorage.getItem('access_token');
    }

    /**
     * Handle authentication errors by redirecting to login
     */
    _handleAuthError() {
        const currentPath = window.location.pathname + window.location.search;
        const loginUrl = `/auth.html?next=${encodeURIComponent(currentPath)}`;
        
        // Clear invalid token
        localStorage.removeItem('access_token');
        
        // Redirect to login
        window.location.href = loginUrl;
    }

    /**
     * Upload file with progress tracking
     */
    async uploadFile(endpoint, file, data = {}, onProgress = null) {
        const token = this._getAuthToken();
        const formData = new FormData();
        
        formData.append('file', file);
        
        // Add additional data
        Object.entries(data).forEach(([key, value]) => {
            formData.append(key, value);
        });

        const headers = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            // Track upload progress
            if (onProgress) {
                xhr.upload.addEventListener('progress', (event) => {
                    if (event.lengthComputable) {
                        const percentComplete = (event.loaded / event.total) * 100;
                        onProgress(percentComplete);
                    }
                });
            }

            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } catch {
                        resolve(xhr.responseText);
                    }
                } else {
                    reject(new Error(`Upload failed: ${xhr.status} ${xhr.statusText}`));
                }
            });

            xhr.addEventListener('error', () => {
                reject(new Error('Upload failed: Network error'));
            });

            xhr.addEventListener('timeout', () => {
                reject(new Error('Upload failed: Timeout'));
            });

            xhr.timeout = this.timeout;
            xhr.open('POST', `${this.baseURL}${endpoint}`);
            
            // Set headers
            Object.entries(headers).forEach(([key, value]) => {
                xhr.setRequestHeader(key, value);
            });

            xhr.send(formData);
        });
    }

    /**
     * Test API connectivity
     */
    async testConnection() {
        try {
            await this.get('/health');
            return { connected: true, error: null };
        } catch (error) {
            return { connected: false, error: error.message };
        }
    }
}

// Create global instance
window.adminAPI = new AdminAPIClient();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AdminAPIClient;
}
