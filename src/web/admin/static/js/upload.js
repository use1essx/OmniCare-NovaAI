/**
 * Advanced File Upload Manager
 * Handles drag-and-drop, progress tracking, and batch operations
 */

class UploadManager {
    constructor(config = {}) {
        this.config = {
            maxFileSize: 50 * 1024 * 1024, // 50MB
            maxFiles: 10,
            allowedTypes: ['.pdf', '.jpg', '.jpeg', '.png', '.txt', '.doc', '.docx'],
            uploadEndpoint: '/api/v1/uploads/upload-with-progress',
            wsEndpoint: '/api/v1/uploads/ws/progress',
            chunkSize: 1024 * 1024, // 1MB chunks
            ...config
        };
        
        this.files = new Map();
        this.wsConnections = new Map();
        this.uploadQueue = [];
        this.isUploading = false;
        
        this.init();
    }
    
    init() {
        this.setupDropZone();
        this.setupFileInput();
        this.setupEventListeners();
        this.bindFormHandlers();
    }
    
    setupDropZone() {
        const dropZone = document.getElementById('upload-zone');
        if (!dropZone) return;
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });
        
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => this.highlight(dropZone), false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => this.unhighlight(dropZone), false);
        });
        
        dropZone.addEventListener('drop', (e) => this.handleDrop(e), false);
        dropZone.addEventListener('click', () => this.triggerFileInput());
    }
    
    setupFileInput() {
        const fileInput = document.getElementById('file-input');
        if (!fileInput) return;
        
        fileInput.addEventListener('change', (e) => {
            this.handleFiles(Array.from(e.target.files));
        });
        
        // Set accepted file types
        fileInput.accept = this.config.allowedTypes.join(',');
    }
    
    setupEventListeners() {
        // Upload button
        const uploadBtn = document.getElementById('upload-btn');
        if (uploadBtn) {
            uploadBtn.addEventListener('click', () => this.startUpload());
        }
        
        // Clear all button
        const clearBtn = document.getElementById('clear-all-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearAllFiles());
        }
        
        // Category quick select
        document.querySelectorAll('.category-pill').forEach(pill => {
            pill.addEventListener('click', (e) => this.selectCategory(e.target));
        });
    }
    
    bindFormHandlers() {
        // Auto-save form data
        const form = document.getElementById('upload-form');
        if (form) {
            const inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                input.addEventListener('change', () => this.saveFormData());
            });
        }
    }
    
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    highlight(element) {
        element.classList.add('drag-over');
    }
    
    unhighlight(element) {
        element.classList.remove('drag-over');
    }
    
    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = Array.from(dt.files);
        this.handleFiles(files);
    }
    
    triggerFileInput() {
        const fileInput = document.getElementById('file-input');
        if (fileInput) {
            fileInput.click();
        }
    }
    
    handleFiles(files) {
        if (files.length === 0) return;
        
        // Check total file limit
        if (this.files.size + files.length > this.config.maxFiles) {
            this.showError(`Maximum ${this.config.maxFiles} files allowed`);
            return;
        }
        
        files.forEach(file => this.addFile(file));
        this.updateUI();
    }
    
    addFile(file) {
        // Validate file
        const validation = this.validateFile(file);
        if (!validation.valid) {
            this.showError(validation.error);
            return;
        }
        
        const fileId = this.generateFileId();
        const fileData = {
            id: fileId,
            file: file,
            name: file.name,
            size: file.size,
            type: this.getFileType(file.name),
            status: 'pending',
            progress: 0,
            message: 'Ready to upload',
            uploadId: null,
            error: null
        };
        
        this.files.set(fileId, fileData);
        this.renderFileItem(fileData);
    }
    
    validateFile(file) {
        // Check file size
        if (file.size > this.config.maxFileSize) {
            return {
                valid: false,
                error: `File size (${this.formatFileSize(file.size)}) exceeds limit (${this.formatFileSize(this.config.maxFileSize)})`
            };
        }
        
        // Check file type
        const extension = '.' + file.name.split('.').pop().toLowerCase();
        if (!this.config.allowedTypes.includes(extension)) {
            return {
                valid: false,
                error: `File type ${extension} not allowed. Allowed types: ${this.config.allowedTypes.join(', ')}`
            };
        }
        
        return { valid: true };
    }
    
    generateFileId() {
        return 'file_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    getFileType(filename) {
        const extension = filename.split('.').pop().toLowerCase();
        const typeMap = {
            'pdf': 'pdf',
            'jpg': 'img', 'jpeg': 'img', 'png': 'img', 'gif': 'img',
            'doc': 'doc', 'docx': 'doc',
            'txt': 'txt'
        };
        return typeMap[extension] || 'file';
    }
    
    renderFileItem(fileData) {
        const fileList = document.getElementById('file-list');
        if (!fileList) return;
        
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.id = `file-${fileData.id}`;
        
        fileItem.innerHTML = `
            <div class="file-icon ${fileData.type}">
                ${fileData.type.toUpperCase()}
            </div>
            <div class="file-info">
                <div class="file-name" title="${fileData.name}">${fileData.name}</div>
                <div class="file-meta">
                    <span class="file-size">${this.formatFileSize(fileData.size)}</span>
                    <span class="file-status status-${fileData.status}">
                        <span class="status-icon">⏳</span>
                        <span class="status-text">${fileData.message}</span>
                    </span>
                </div>
                <div class="progress-container" style="display: none;">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 0%"></div>
                    </div>
                    <div class="progress-text">0%</div>
                </div>
            </div>
            <div class="file-actions">
                <button class="action-button action-retry" onclick="uploadManager.retryFile('${fileData.id}')" style="display: none;" title="Retry">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M4 12a8 8 0 018-8V2.5L14.5 5 12 7.5V6a6 6 0 100 12 6 6 0 006-6h2a8 8 0 01-16 0z"/>
                    </svg>
                </button>
                <button class="action-button action-remove" onclick="uploadManager.removeFile('${fileData.id}')" title="Remove">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                    </svg>
                </button>
            </div>
        `;
        
        fileList.appendChild(fileItem);
        this.updateFileCount();
    }
    
    updateFileItem(fileId, updates) {
        const fileData = this.files.get(fileId);
        if (!fileData) return;
        
        Object.assign(fileData, updates);
        
        const fileElement = document.getElementById(`file-${fileId}`);
        if (!fileElement) return;
        
        // Update status
        if (updates.status) {
            fileElement.className = `file-item ${updates.status}`;
            const statusElement = fileElement.querySelector('.file-status');
            if (statusElement) {
                statusElement.className = `file-status status-${updates.status}`;
                const statusIcon = statusElement.querySelector('.status-icon');
                const statusText = statusElement.querySelector('.status-text');
                
                if (updates.status === 'uploading') {
                    statusIcon.textContent = '⏳';
                } else if (updates.status === 'success') {
                    statusIcon.textContent = '✅';
                } else if (updates.status === 'error') {
                    statusIcon.textContent = '❌';
                }
                
                if (updates.message) {
                    statusText.textContent = updates.message;
                }
            }
        }
        
        // Update progress
        if (typeof updates.progress === 'number') {
            const progressContainer = fileElement.querySelector('.progress-container');
            const progressFill = fileElement.querySelector('.progress-fill');
            const progressText = fileElement.querySelector('.progress-text');
            
            if (progressContainer && progressFill && progressText) {
                progressContainer.style.display = 'block';
                progressFill.style.width = `${updates.progress}%`;
                progressText.textContent = `${Math.round(updates.progress)}%`;
                
                if (updates.status === 'success') {
                    progressFill.classList.add('success');
                } else if (updates.status === 'error') {
                    progressFill.classList.add('error');
                }
            }
        }
        
        // Show/hide action buttons
        const retryBtn = fileElement.querySelector('.action-retry');
        const removeBtn = fileElement.querySelector('.action-remove');
        
        if (retryBtn) {
            retryBtn.style.display = updates.status === 'error' ? 'flex' : 'none';
        }
    }
    
    setupWebSocket(uploadId) {
        if (this.wsConnections.has(uploadId)) {
            return this.wsConnections.get(uploadId);
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}${this.config.wsEndpoint}/${uploadId}`;
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log(`WebSocket connected for upload ${uploadId}`);
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleProgressUpdate(uploadId, data);
            } catch (e) {
                console.error('Error parsing WebSocket message:', e);
            }
        };
        
        ws.onclose = () => {
            console.log(`WebSocket closed for upload ${uploadId}`);
            this.wsConnections.delete(uploadId);
        };
        
        ws.onerror = (error) => {
            console.error(`WebSocket error for upload ${uploadId}:`, error);
        };
        
        this.wsConnections.set(uploadId, ws);
        return ws;
    }
    
    handleProgressUpdate(uploadId, data) {
        // Find file by uploadId
        let fileId = null;
        for (const [id, fileData] of this.files.entries()) {
            if (fileData.uploadId === uploadId) {
                fileId = id;
                break;
            }
        }
        
        if (!fileId) return;
        
        const updates = {
            progress: data.progress || 0,
            message: data.message || '',
        };
        
        if (data.stage === 'error') {
            updates.status = 'error';
            updates.error = data.message;
        } else if (data.stage === 'complete' || data.stage === 'processing_complete') {
            updates.status = 'success';
            updates.progress = 100;
        } else if (data.stage !== 'complete') {
            updates.status = 'uploading';
        }
        
        this.updateFileItem(fileId, updates);
    }
    
    async startUpload() {
        if (this.isUploading) return;
        if (this.files.size === 0) {
            this.showError('No files selected');
            return;
        }
        
        // Validate form
        const formData = this.getFormData();
        if (!formData.category) {
            this.showError('Please select a category');
            return;
        }
        
        this.isUploading = true;
        this.updateUploadButton(true);
        
        // Upload files one by one
        for (const [fileId, fileData] of this.files.entries()) {
            if (fileData.status === 'pending' || fileData.status === 'error') {
                await this.uploadFile(fileId);
            }
        }
        
        this.isUploading = false;
        this.updateUploadButton(false);
        this.showSuccess('Upload completed!');
    }
    
    async uploadFile(fileId) {
        const fileData = this.files.get(fileId);
        if (!fileData) return;
        
        const uploadId = this.generateUploadId();
        fileData.uploadId = uploadId;
        
        // Setup WebSocket for progress tracking
        this.setupWebSocket(uploadId);
        
        // Update file status
        this.updateFileItem(fileId, {
            status: 'uploading',
            progress: 0,
            message: 'Starting upload...'
        });
        
        try {
            const formData = new FormData();
            const form = this.getFormData();
            
            formData.append('file', fileData.file);
            formData.append('upload_id', uploadId);
            formData.append('category', form.category);
            formData.append('title', form.title || '');
            formData.append('description', form.description || '');
            formData.append('tags', form.tags || '');
            formData.append('language', form.language || 'en');
            formData.append('is_sensitive', form.is_sensitive || false);
            
            const response = await fetch(this.config.uploadEndpoint, {
                method: 'POST',
                body: formData,
                headers: {
                    'Authorization': `Bearer ${this.getAuthToken()}`
                }
            });
            
            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            // File upload successful, now wait for processing
            this.updateFileItem(fileId, {
                message: 'Upload successful, processing...',
                documentId: result.document_id
            });
            
        } catch (error) {
            console.error('Upload error:', error);
            this.updateFileItem(fileId, {
                status: 'error',
                message: error.message,
                error: error.message
            });
        }
    }
    
    generateUploadId() {
        return 'upload_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    getFormData() {
        const form = document.getElementById('upload-form');
        if (!form) return {};
        
        const formData = new FormData(form);
        const data = {};
        
        for (const [key, value] of formData.entries()) {
            data[key] = value;
        }
        
        return data;
    }
    
    saveFormData() {
        const formData = this.getFormData();
        localStorage.setItem('uploadFormData', JSON.stringify(formData));
    }
    
    loadFormData() {
        try {
            const saved = localStorage.getItem('uploadFormData');
            if (saved) {
                const data = JSON.parse(saved);
                this.populateForm(data);
            }
        } catch (e) {
            console.error('Error loading form data:', e);
        }
    }
    
    populateForm(data) {
        const form = document.getElementById('upload-form');
        if (!form) return;
        
        Object.entries(data).forEach(([key, value]) => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) {
                if (input.type === 'checkbox') {
                    input.checked = value === 'true' || value === true;
                } else {
                    input.value = value;
                }
            }
        });
    }
    
    selectCategory(pill) {
        // Remove selection from all pills
        document.querySelectorAll('.category-pill').forEach(p => {
            p.classList.remove('selected');
        });
        
        // Select clicked pill
        pill.classList.add('selected');
        
        // Update form
        const categoryInput = document.querySelector('[name="category"]');
        if (categoryInput) {
            categoryInput.value = pill.dataset.value;
            this.saveFormData();
        }
    }
    
    removeFile(fileId) {
        const fileData = this.files.get(fileId);
        if (!fileData) return;
        
        // Close WebSocket if exists
        if (fileData.uploadId && this.wsConnections.has(fileData.uploadId)) {
            this.wsConnections.get(fileData.uploadId).close();
            this.wsConnections.delete(fileData.uploadId);
        }
        
        // Remove from files map
        this.files.delete(fileId);
        
        // Remove from DOM
        const fileElement = document.getElementById(`file-${fileId}`);
        if (fileElement) {
            fileElement.remove();
        }
        
        this.updateFileCount();
        this.updateUI();
    }
    
    retryFile(fileId) {
        const fileData = this.files.get(fileId);
        if (!fileData) return;
        
        // Reset file status
        this.updateFileItem(fileId, {
            status: 'pending',
            progress: 0,
            message: 'Ready to retry',
            error: null
        });
        
        // Upload the file
        this.uploadFile(fileId);
    }
    
    clearAllFiles() {
        // Close all WebSocket connections
        this.wsConnections.forEach(ws => ws.close());
        this.wsConnections.clear();
        
        // Clear files
        this.files.clear();
        
        // Clear DOM
        const fileList = document.getElementById('file-list');
        if (fileList) {
            fileList.innerHTML = '';
        }
        
        this.updateFileCount();
        this.updateUI();
    }
    
    updateFileCount() {
        const fileCount = document.getElementById('file-count');
        if (fileCount) {
            fileCount.textContent = `${this.files.size} file(s) selected`;
        }
    }
    
    updateUI() {
        const hasFiles = this.files.size > 0;
        
        // Show/hide file list
        const fileListContainer = document.getElementById('file-list-container');
        if (fileListContainer) {
            fileListContainer.style.display = hasFiles ? 'block' : 'none';
        }
        
        // Enable/disable upload button
        const uploadBtn = document.getElementById('upload-btn');
        if (uploadBtn) {
            uploadBtn.disabled = !hasFiles || this.isUploading;
        }
        
        // Enable/disable clear button
        const clearBtn = document.getElementById('clear-all-btn');
        if (clearBtn) {
            clearBtn.disabled = !hasFiles || this.isUploading;
        }
    }
    
    updateUploadButton(isUploading) {
        const uploadBtn = document.getElementById('upload-btn');
        if (!uploadBtn) return;
        
        if (isUploading) {
            uploadBtn.textContent = 'Uploading...';
            uploadBtn.disabled = true;
            uploadBtn.classList.add('uploading');
        } else {
            uploadBtn.textContent = 'Start Upload';
            uploadBtn.disabled = this.files.size === 0;
            uploadBtn.classList.remove('uploading');
        }
    }
    
    getAuthToken() {
        // Get JWT token from localStorage or wherever it's stored
        return localStorage.getItem('auth_token') || '';
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <span class="notification-icon">
                    ${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}
                </span>
                <span class="notification-message">${message}</span>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
        `;
        
        // Add to page
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 1000;
                max-width: 400px;
            `;
            document.body.appendChild(container);
        }
        
        container.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentElement) {
                notification.remove();
            }
        }, 5000);
    }
}

// Global upload manager instance
let uploadManager;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    uploadManager = new UploadManager();
    uploadManager.loadFormData();
});

// Add notification styles
const notificationStyles = `
<style>
.notification {
    background: white;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    margin-bottom: 10px;
    animation: slideInRight 0.3s ease;
}

.notification-success {
    border-left: 4px solid #10b981;
}

.notification-error {
    border-left: 4px solid #ef4444;
}

.notification-info {
    border-left: 4px solid #3b82f6;
}

.notification-content {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
}

.notification-icon {
    font-size: 18px;
}

.notification-message {
    flex: 1;
    font-weight: 500;
    color: #374151;
}

.notification-close {
    background: none;
    border: none;
    font-size: 20px;
    color: #6b7280;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.notification-close:hover {
    color: #374151;
}

@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}
</style>
`;

document.head.insertAdjacentHTML('beforeend', notificationStyles);
