/**
 * Healthcare AI V2 Admin Utilities
 * Shared utility functions for admin components
 */

window.adminUtils = {
    /**
     * Format file size
     */
    formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    },
    
    /**
     * Format number with commas
     */
    formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    },
    
    /**
     * Format percentage
     */
    formatPercent(num, decimals = 0) {
        return (num * 100).toFixed(decimals) + '%';
    },
    
    /**
     * Format currency
     */
    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    },
    
    /**
     * Format date
     */
    formatDate(date, options = {}) {
        const defaultOptions = {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        };
        return new Intl.DateTimeFormat('en-US', { ...defaultOptions, ...options }).format(new Date(date));
    },
    
    /**
     * Format date and time
     */
    formatDateTime(date) {
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        }).format(new Date(date));
    },
    
    /**
     * Get time ago string
     */
    timeAgo(date) {
        const now = new Date();
        const time = new Date(date);
        const diff = now - time;
        
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        const weeks = Math.floor(days / 7);
        const months = Math.floor(days / 30);
        const years = Math.floor(days / 365);
        
        if (years > 0) return `${years} year${years > 1 ? 's' : ''} ago`;
        if (months > 0) return `${months} month${months > 1 ? 's' : ''} ago`;
        if (weeks > 0) return `${weeks} week${weeks > 1 ? 's' : ''} ago`;
        if (days > 0) return `${days} day${days > 1 ? 's' : ''} ago`;
        if (hours > 0) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        if (minutes > 0) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        return 'Just now';
    },
    
    /**
     * Create gradient background for charts
     */
    createGradientBackground(ctx, color1, color2, height = 300) {
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, color1);
        gradient.addColorStop(1, color2);
        return gradient;
    },
    
    /**
     * Create chart gradient with opacity
     */
    createChartGradient(ctx, color, height = 300) {
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, color + '40'); // 25% opacity
        gradient.addColorStop(1, color + '00'); // 0% opacity
        return gradient;
    },
    
    /**
     * Debounce function
     */
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
    
    /**
     * Throttle function
     */
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
    },
    
    /**
     * Deep clone object
     */
    deepClone(obj) {
        if (obj === null || typeof obj !== 'object') return obj;
        if (obj instanceof Date) return new Date(obj.getTime());
        if (obj instanceof Array) return obj.map(item => this.deepClone(item));
        if (typeof obj === 'object') {
            const clonedObj = {};
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    clonedObj[key] = this.deepClone(obj[key]);
                }
            }
            return clonedObj;
        }
    },
    
    /**
     * Generate random ID
     */
    generateId(prefix = 'id') {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    },
    
    /**
     * Copy text to clipboard
     */
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            return true;
        } catch (err) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {
                document.execCommand('copy');
                document.body.removeChild(textArea);
                return true;
            } catch (err) {
                document.body.removeChild(textArea);
                return false;
            }
        }
    },
    
    /**
     * Download data as JSON file
     */
    downloadJSON(data, filename = 'data.json') {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },
    
    /**
     * Download data as CSV file
     */
    downloadCSV(data, filename = 'data.csv') {
        if (!Array.isArray(data) || data.length === 0) return;
        
        const headers = Object.keys(data[0]);
        const csvContent = [
            headers.join(','),
            ...data.map(row => headers.map(header => {
                const value = row[header];
                return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
            }).join(','))
        ].join('\n');
        
        const blob = new Blob([csvContent], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    },
    
    /**
     * Validate email address
     */
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },
    
    /**
     * Validate URL
     */
    isValidURL(url) {
        try {
            new URL(url);
            return true;
        } catch {
            return false;
        }
    },
    
    /**
     * Sanitize HTML
     */
    sanitizeHTML(html) {
        const temp = document.createElement('div');
        temp.textContent = html;
        return temp.innerHTML;
    },
    
    /**
     * Truncate text
     */
    truncateText(text, maxLength, suffix = '...') {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength - suffix.length) + suffix;
    },
    
    /**
     * Get status color class
     */
    getStatusColor(status) {
        const statusColors = {
            'healthy': 'text-green-600 bg-green-100',
            'warning': 'text-yellow-600 bg-yellow-100',
            'error': 'text-red-600 bg-red-100',
            'info': 'text-blue-600 bg-blue-100',
            'success': 'text-green-600 bg-green-100',
            'danger': 'text-red-600 bg-red-100',
            'active': 'text-green-600 bg-green-100',
            'inactive': 'text-gray-600 bg-gray-100',
            'pending': 'text-yellow-600 bg-yellow-100',
            'approved': 'text-green-600 bg-green-100',
            'rejected': 'text-red-600 bg-red-100'
        };
        return statusColors[status] || 'text-gray-600 bg-gray-100';
    },
    
    /**
     * Get status icon
     */
    getStatusIcon(status) {
        const statusIcons = {
            'healthy': 'fas fa-check-circle',
            'warning': 'fas fa-exclamation-triangle',
            'error': 'fas fa-times-circle',
            'info': 'fas fa-info-circle',
            'success': 'fas fa-check-circle',
            'danger': 'fas fa-times-circle',
            'active': 'fas fa-check-circle',
            'inactive': 'fas fa-times-circle',
            'pending': 'fas fa-clock',
            'approved': 'fas fa-check-circle',
            'rejected': 'fas fa-times-circle'
        };
        return statusIcons[status] || 'fas fa-question-circle';
    },
    
    /**
     * Get role badge class
     */
    getRoleBadgeClass(role) {
        const roleBadges = {
            'super_admin': 'badge-purple',
            'admin': 'badge-orange',
            'doctor': 'badge-blue',
            'nurse': 'badge-blue',
            'social_worker': 'badge-green',
            'counselor': 'badge-green',
            'user': 'badge-yellow',
            'patient': 'badge-yellow'
        };
        return roleBadges[role] || 'badge-gray';
    },
    
    /**
     * Get organization type badge class
     */
    getOrgTypeBadgeClass(type) {
        const typeBadges = {
            'hospital': 'badge-blue',
            'clinic': 'badge-green',
            'ngo': 'badge-purple',
            'platform': 'badge-yellow',
            'social_service': 'badge-orange'
        };
        return typeBadges[type] || 'badge-gray';
    },
    
    /**
     * Show loading spinner
     */
    showLoading(element, message = 'Loading...') {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        if (element) {
            element.innerHTML = `
                <div class="flex items-center justify-center p-4">
                    <div class="spinner mr-2"></div>
                    <span class="text-gray-600">${message}</span>
                </div>
            `;
        }
    },
    
    /**
     * Hide loading spinner
     */
    hideLoading(element) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        if (element) {
            element.innerHTML = '';
        }
    },
    
    /**
     * Show error message
     */
    showError(element, message) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        if (element) {
            element.innerHTML = `
                <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
                    <strong>Error:</strong> ${message}
                </div>
            `;
        }
    },
    
    /**
     * Show success message
     */
    showSuccess(element, message) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        if (element) {
            element.innerHTML = `
                <div class="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded">
                    <strong>Success:</strong> ${message}
                </div>
            `;
        }
    },
    
    /**
     * Animate element
     */
    animate(element, animation, duration = 300) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        if (element) {
            element.style.animationDuration = `${duration}ms`;
            element.classList.add(animation);
            setTimeout(() => {
                element.classList.remove(animation);
            }, duration);
        }
    },
    
    /**
     * Smooth scroll to element
     */
    scrollTo(element, offset = 0) {
        if (typeof element === 'string') {
            element = document.getElementById(element);
        }
        if (element) {
            const elementPosition = element.offsetTop - offset;
            window.scrollTo({
                top: elementPosition,
                behavior: 'smooth'
            });
        }
    },
    
    /**
     * Get query parameters
     */
    getQueryParams() {
        const params = new URLSearchParams(window.location.search);
        const result = {};
        for (const [key, value] of params) {
            result[key] = value;
        }
        return result;
    },
    
    /**
     * Set query parameter
     */
    setQueryParam(key, value) {
        const url = new URL(window.location);
        url.searchParams.set(key, value);
        window.history.pushState({}, '', url);
    },
    
    /**
     * Remove query parameter
     */
    removeQueryParam(key) {
        const url = new URL(window.location);
        url.searchParams.delete(key);
        window.history.pushState({}, '', url);
    }
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = window.adminUtils;
}
