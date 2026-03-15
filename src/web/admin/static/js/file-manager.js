/**
 * Document Management System
 * Handles document listing, search, filtering, and bulk operations
 */

class DocumentManager {
    constructor(config = {}) {
        this.config = {
            documentsEndpoint: '/api/v1/uploads/documents',
            bulkOperationsEndpoint: '/api/v1/uploads/bulk-operations',
            categoriesEndpoint: '/api/v1/uploads/categories',
            wsEndpoint: '/api/v1/uploads/ws/progress',
            pageSize: 20,
            ...config
        };
        
        this.documents = [];
        this.filteredDocuments = [];
        this.selectedDocuments = new Set();
        this.currentPage = 1;
        this.totalPages = 1;
        this.totalDocuments = 0;
        this.filters = {
            search: '',
            category: '',
            status: '',
            uploaded_by: '',
            date_from: '',
            date_to: '',
            sort_by: 'created_at',
            sort_order: 'desc'
        };
        
        this.categories = [];
        this.isLoading = false;
        
        this.init();
    }
    
    async init() {
        await this.loadCategories();
        this.setupEventListeners();
        this.setupSearch();
        this.setupFilters();
        this.setupPagination();
        this.setupBulkActions();
        await this.loadDocuments();
        this.startAutoRefresh();
    }
    
    async loadCategories() {
        try {
            const response = await fetch(this.config.categoriesEndpoint, {
                headers: { 'Authorization': `Bearer ${this.getAuthToken()}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.categories = data.categories || [];
                this.populateCategoryFilter();
            }
        } catch (error) {
            console.error('Error loading categories:', error);
        }
    }
    
    populateCategoryFilter() {
        const categorySelect = document.getElementById('category-filter');
        if (!categorySelect || this.categories.length === 0) return;
        
        // Clear existing options except the first one
        while (categorySelect.children.length > 1) {
            categorySelect.removeChild(categorySelect.lastChild);
        }
        
        this.categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category.value || category;
            option.textContent = category.label || category;
            categorySelect.appendChild(option);
        });
    }
    
    setupEventListeners() {
        // Refresh button
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadDocuments());
        }
        
        // Select all checkbox
        const selectAllBtn = document.getElementById('select-all');
        if (selectAllBtn) {
            selectAllBtn.addEventListener('change', (e) => this.toggleSelectAll(e.target.checked));
        }
        
        // Document table clicks
        const documentTable = document.getElementById('documents-table');
        if (documentTable) {
            documentTable.addEventListener('click', (e) => this.handleTableClick(e));
        }
        
        // Sort headers
        document.querySelectorAll('.sortable-header').forEach(header => {
            header.addEventListener('click', () => {
                const sortBy = header.dataset.sort;
                this.toggleSort(sortBy);
            });
        });
    }
    
    setupSearch() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;
        
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                this.filters.search = e.target.value;
                this.currentPage = 1;
                this.loadDocuments();
            }, 300);
        });
        
        // Search suggestions
        searchInput.addEventListener('focus', () => this.showSearchSuggestions());
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#search-container')) {
                this.hideSearchSuggestions();
            }
        });
    }
    
    setupFilters() {
        // Category filter
        const categoryFilter = document.getElementById('category-filter');
        if (categoryFilter) {
            categoryFilter.addEventListener('change', (e) => {
                this.filters.category = e.target.value;
                this.currentPage = 1;
                this.loadDocuments();
            });
        }
        
        // Status filter
        const statusFilter = document.getElementById('status-filter');
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.filters.status = e.target.value;
                this.currentPage = 1;
                this.loadDocuments();
            });
        }
        
        // Date filters
        const dateFromFilter = document.getElementById('date-from-filter');
        const dateToFilter = document.getElementById('date-to-filter');
        
        if (dateFromFilter) {
            dateFromFilter.addEventListener('change', (e) => {
                this.filters.date_from = e.target.value;
                this.currentPage = 1;
                this.loadDocuments();
            });
        }
        
        if (dateToFilter) {
            dateToFilter.addEventListener('change', (e) => {
                this.filters.date_to = e.target.value;
                this.currentPage = 1;
                this.loadDocuments();
            });
        }
        
        // Clear filters button
        const clearFiltersBtn = document.getElementById('clear-filters-btn');
        if (clearFiltersBtn) {
            clearFiltersBtn.addEventListener('click', () => this.clearFilters());
        }
    }
    
    setupPagination() {
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.goToPage(this.currentPage - 1));
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.goToPage(this.currentPage + 1));
        }
    }
    
    setupBulkActions() {
        // Bulk action select
        const bulkActionSelect = document.getElementById('bulk-action-select');
        if (bulkActionSelect) {
            bulkActionSelect.addEventListener('change', (e) => {
                const applyBtn = document.getElementById('apply-bulk-action');
                if (applyBtn) {
                    applyBtn.disabled = !e.target.value || this.selectedDocuments.size === 0;
                }
            });
        }
        
        // Apply bulk action button
        const applyBtn = document.getElementById('apply-bulk-action');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => this.applyBulkAction());
        }
    }
    
    async loadDocuments() {
        if (this.isLoading) return;
        
        this.isLoading = true;
        this.showLoading(true);
        
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                limit: this.config.pageSize,
                sort_by: this.filters.sort_by,
                sort_order: this.filters.sort_order
            });
            
            // Add filters
            Object.entries(this.filters).forEach(([key, value]) => {
                if (value && key !== 'sort_by' && key !== 'sort_order') {
                    params.append(key, value);
                }
            });
            
            const response = await fetch(`${this.config.documentsEndpoint}?${params}`, {
                headers: { 'Authorization': `Bearer ${this.getAuthToken()}` }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            this.documents = data.documents || [];
            this.totalDocuments = data.pagination?.total || 0;
            this.totalPages = data.pagination?.pages || 1;
            this.currentPage = data.pagination?.page || 1;
            
            this.renderDocuments();
            this.updatePagination();
            this.updateStats();
            
        } catch (error) {
            console.error('Error loading documents:', error);
            this.showError('Failed to load documents: ' + error.message);
        } finally {
            this.isLoading = false;
            this.showLoading(false);
        }
    }
    
    renderDocuments() {
        const tbody = document.getElementById('documents-tbody');
        if (!tbody) return;
        
        if (this.documents.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center py-8 text-gray-500">
                        <div class="flex flex-col items-center">
                            <svg class="w-12 h-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                            </svg>
                            <p class="text-lg font-medium">No documents found</p>
                            <p class="text-sm">Try adjusting your search or filters</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = this.documents.map(doc => this.renderDocumentRow(doc)).join('');
    }
    
    renderDocumentRow(doc) {
        const isSelected = this.selectedDocuments.has(doc.id);
        const statusColors = {
            'pending_approval': 'bg-yellow-100 text-yellow-800',
            'approved': 'bg-green-100 text-green-800',
            'rejected': 'bg-red-100 text-red-800',
            'processing': 'bg-blue-100 text-blue-800',
            'processing_error': 'bg-red-100 text-red-800'
        };
        
        const qualityScore = doc.quality_score ? Math.round(doc.quality_score * 100) : 'N/A';
        const qualityColor = doc.quality_score >= 0.8 ? 'text-green-600' : 
                           doc.quality_score >= 0.6 ? 'text-yellow-600' : 'text-red-600';
        
        return `
            <tr class="hover:bg-gray-50 ${isSelected ? 'bg-blue-50' : ''}" data-document-id="${doc.id}">
                <td class="px-6 py-4 whitespace-nowrap">
                    <input type="checkbox" class="document-checkbox" ${isSelected ? 'checked' : ''} 
                           data-document-id="${doc.id}">
                </td>
                <td class="px-6 py-4">
                    <div class="flex items-center">
                        <div class="flex-shrink-0 h-10 w-10">
                            <div class="h-10 w-10 rounded-lg bg-gray-100 flex items-center justify-center">
                                <span class="text-xs font-medium text-gray-600">
                                    ${doc.file_type.toUpperCase()}
                                </span>
                            </div>
                        </div>
                        <div class="ml-4">
                            <div class="text-sm font-medium text-gray-900 cursor-pointer hover:text-blue-600" 
                                 onclick="documentManager.viewDocument(${doc.id})">
                                ${this.truncateText(doc.title || doc.original_filename, 40)}
                            </div>
                            <div class="text-sm text-gray-500">
                                ${this.formatFileSize(doc.file_size)}
                            </div>
                        </div>
                    </div>
                </td>
                <td class="px-6 py-4 whitespace-nowrap">
                    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[doc.status] || 'bg-gray-100 text-gray-800'}">
                        ${this.formatStatus(doc.status)}
                    </span>
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${doc.category || 'Uncategorized'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm ${qualityColor}">
                    ${qualityScore}${doc.quality_score ? '%' : ''}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${doc.uploaded_by?.full_name || doc.uploaded_by?.username || 'Unknown'}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    ${this.formatDate(doc.created_at)}
                </td>
                <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <div class="flex items-center justify-end space-x-2">
                        ${this.renderDocumentActions(doc)}
                    </div>
                </td>
            </tr>
        `;
    }
    
    renderDocumentActions(doc) {
        const actions = [];
        
        // View action
        actions.push(`
            <button onclick="documentManager.viewDocument(${doc.id})" 
                    class="text-blue-600 hover:text-blue-900" title="View">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                </svg>
            </button>
        `);
        
        // Download action
        actions.push(`
            <button onclick="documentManager.downloadDocument(${doc.id})" 
                    class="text-green-600 hover:text-green-900" title="Download">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
            </button>
        `);
        
        // Status-specific actions
        if (doc.status === 'pending_approval') {
            actions.push(`
                <button onclick="documentManager.approveDocument(${doc.id})" 
                        class="text-green-600 hover:text-green-900" title="Approve">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                </button>
            `);
            
            actions.push(`
                <button onclick="documentManager.rejectDocument(${doc.id})" 
                        class="text-red-600 hover:text-red-900" title="Reject">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </button>
            `);
        }
        
        // Edit action
        actions.push(`
            <button onclick="documentManager.editDocument(${doc.id})" 
                    class="text-gray-600 hover:text-gray-900" title="Edit">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                </svg>
            </button>
        `);
        
        // Delete action
        actions.push(`
            <button onclick="documentManager.deleteDocument(${doc.id})" 
                    class="text-red-600 hover:text-red-900" title="Delete">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                </svg>
            </button>
        `);
        
        return actions.join('');
    }
    
    handleTableClick(e) {
        if (e.target.classList.contains('document-checkbox')) {
            const docId = parseInt(e.target.dataset.documentId);
            this.toggleDocumentSelection(docId, e.target.checked);
        }
    }
    
    toggleDocumentSelection(docId, selected) {
        if (selected) {
            this.selectedDocuments.add(docId);
        } else {
            this.selectedDocuments.delete(docId);
        }
        
        this.updateSelectionUI();
    }
    
    toggleSelectAll(selectAll) {
        this.selectedDocuments.clear();
        
        if (selectAll) {
            this.documents.forEach(doc => {
                this.selectedDocuments.add(doc.id);
            });
        }
        
        // Update checkboxes
        document.querySelectorAll('.document-checkbox').forEach(checkbox => {
            checkbox.checked = selectAll;
        });
        
        this.updateSelectionUI();
        this.renderDocuments(); // Re-render to update row highlighting
    }
    
    updateSelectionUI() {
        const selectedCount = this.selectedDocuments.size;
        const totalCount = this.documents.length;
        
        // Update select all checkbox
        const selectAllCheckbox = document.getElementById('select-all');
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = selectedCount === totalCount && totalCount > 0;
            selectAllCheckbox.indeterminate = selectedCount > 0 && selectedCount < totalCount;
        }
        
        // Update bulk actions
        const bulkActionSelect = document.getElementById('bulk-action-select');
        const applyBtn = document.getElementById('apply-bulk-action');
        
        if (bulkActionSelect && applyBtn) {
            applyBtn.disabled = selectedCount === 0 || !bulkActionSelect.value;
        }
        
        // Update selection counter
        const selectionCounter = document.getElementById('selection-counter');
        if (selectionCounter) {
            selectionCounter.textContent = selectedCount > 0 ? 
                `${selectedCount} document(s) selected` : '';
        }
    }
    
    updatePagination() {
        const prevBtn = document.getElementById('prev-page');
        const nextBtn = document.getElementById('next-page');
        const pageInfo = document.getElementById('page-info');
        
        if (prevBtn) {
            prevBtn.disabled = this.currentPage <= 1;
        }
        
        if (nextBtn) {
            nextBtn.disabled = this.currentPage >= this.totalPages;
        }
        
        if (pageInfo) {
            const start = Math.min((this.currentPage - 1) * this.config.pageSize + 1, this.totalDocuments);
            const end = Math.min(this.currentPage * this.config.pageSize, this.totalDocuments);
            pageInfo.textContent = `Showing ${start}-${end} of ${this.totalDocuments}`;
        }
    }
    
    updateStats() {
        const totalElement = document.getElementById('total-documents');
        if (totalElement) {
            totalElement.textContent = this.totalDocuments;
        }
        
        // Update status counts
        const statusCounts = {};
        this.documents.forEach(doc => {
            statusCounts[doc.status] = (statusCounts[doc.status] || 0) + 1;
        });
        
        Object.entries(statusCounts).forEach(([status, count]) => {
            const element = document.getElementById(`${status.replace('_', '-')}-count`);
            if (element) {
                element.textContent = count;
            }
        });
    }
    
    goToPage(page) {
        if (page < 1 || page > this.totalPages || page === this.currentPage) {
            return;
        }
        
        this.currentPage = page;
        this.loadDocuments();
    }
    
    toggleSort(sortBy) {
        if (this.filters.sort_by === sortBy) {
            this.filters.sort_order = this.filters.sort_order === 'asc' ? 'desc' : 'asc';
        } else {
            this.filters.sort_by = sortBy;
            this.filters.sort_order = 'desc';
        }
        
        this.currentPage = 1;
        this.loadDocuments();
    }
    
    clearFilters() {
        this.filters = {
            search: '',
            category: '',
            status: '',
            uploaded_by: '',
            date_from: '',
            date_to: '',
            sort_by: 'created_at',
            sort_order: 'desc'
        };
        
        // Clear form inputs
        const form = document.getElementById('filters-form');
        if (form) {
            form.reset();
        }
        
        this.currentPage = 1;
        this.loadDocuments();
    }
    
    async applyBulkAction() {
        const actionSelect = document.getElementById('bulk-action-select');
        if (!actionSelect || !actionSelect.value || this.selectedDocuments.size === 0) {
            return;
        }
        
        const action = actionSelect.value;
        const documentIds = Array.from(this.selectedDocuments);
        
        let reason = null;
        if (action === 'reject') {
            reason = prompt('Please provide a reason for rejection:');
            if (!reason) return;
        }
        
        if (!confirm(`Are you sure you want to ${action} ${documentIds.length} document(s)?`)) {
            return;
        }
        
        try {
            const response = await fetch(this.config.bulkOperationsEndpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${this.getAuthToken()}`
                },
                body: JSON.stringify({
                    document_ids: documentIds,
                    operation: action,
                    reason: reason
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const result = await response.json();
            
            this.showSuccess(`${result.successful_operations}/${result.total_documents} documents ${action}d successfully`);
            
            // Clear selection and reload
            this.selectedDocuments.clear();
            actionSelect.value = '';
            this.updateSelectionUI();
            await this.loadDocuments();
            
        } catch (error) {
            console.error('Bulk operation error:', error);
            this.showError('Failed to perform bulk operation: ' + error.message);
        }
    }
    
    async viewDocument(docId) {
        // Open document preview modal
        this.openDocumentModal(docId, 'view');
    }
    
    async editDocument(docId) {
        // Open document edit modal
        this.openDocumentModal(docId, 'edit');
    }
    
    async approveDocument(docId) {
        if (!confirm('Are you sure you want to approve this document?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/v1/uploads/documents/${docId}/approve`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${this.getAuthToken()}` }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.showSuccess('Document approved successfully');
            await this.loadDocuments();
            
        } catch (error) {
            console.error('Approval error:', error);
            this.showError('Failed to approve document: ' + error.message);
        }
    }
    
    async rejectDocument(docId) {
        const reason = prompt('Please provide a reason for rejection:');
        if (!reason) return;
        
        try {
            const formData = new FormData();
            formData.append('reason', reason);
            
            const response = await fetch(`/api/v1/uploads/documents/${docId}/reject`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${this.getAuthToken()}` },
                body: formData
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.showSuccess('Document rejected successfully');
            await this.loadDocuments();
            
        } catch (error) {
            console.error('Rejection error:', error);
            this.showError('Failed to reject document: ' + error.message);
        }
    }
    
    async deleteDocument(docId) {
        if (!confirm('Are you sure you want to delete this document? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/v1/uploads/documents/${docId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${this.getAuthToken()}` }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            this.showSuccess('Document deleted successfully');
            this.selectedDocuments.delete(docId);
            this.updateSelectionUI();
            await this.loadDocuments();
            
        } catch (error) {
            console.error('Deletion error:', error);
            this.showError('Failed to delete document: ' + error.message);
        }
    }
    
    downloadDocument(docId) {
        const downloadUrl = `/api/v1/uploads/download/${docId}`;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = '';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    
    openDocumentModal(docId, mode = 'view') {
        // This would open a modal with document details/preview
        // Implementation depends on your modal system
        console.log(`Opening document ${docId} in ${mode} mode`);
    }
    
    showSearchSuggestions() {
        // Implementation for search suggestions
        // Could show recent searches, popular terms, etc.
    }
    
    hideSearchSuggestions() {
        // Hide search suggestions dropdown
    }
    
    startAutoRefresh() {
        // Auto-refresh every 30 seconds to check for status updates
        setInterval(() => {
            if (!this.isLoading) {
                this.loadDocuments();
            }
        }, 30000);
    }
    
    showLoading(show) {
        const loadingIndicator = document.getElementById('loading-indicator');
        if (loadingIndicator) {
            loadingIndicator.style.display = show ? 'block' : 'none';
        }
        
        const refreshBtn = document.getElementById('refresh-btn');
        if (refreshBtn) {
            refreshBtn.disabled = show;
            if (show) {
                refreshBtn.classList.add('animate-spin');
            } else {
                refreshBtn.classList.remove('animate-spin');
            }
        }
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    formatDate(dateString) {
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        } catch {
            return 'Invalid Date';
        }
    }
    
    formatStatus(status) {
        const statusMap = {
            'pending_approval': 'Pending',
            'approved': 'Approved',
            'rejected': 'Rejected',
            'processing': 'Processing',
            'processing_error': 'Error'
        };
        return statusMap[status] || status;
    }
    
    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    getAuthToken() {
        return localStorage.getItem('auth_token') || '';
    }
    
    showError(message) {
        this.showNotification(message, 'error');
    }
    
    showSuccess(message) {
        this.showNotification(message, 'success');
    }
    
    showNotification(message, type = 'info') {
        // Use the same notification system as upload.js
        const event = new CustomEvent('showNotification', {
            detail: { message, type }
        });
        document.dispatchEvent(event);
    }
}

// Global document manager instance
let documentManager;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    documentManager = new DocumentManager();
});

// Listen for notifications from other components
document.addEventListener('showNotification', (e) => {
    const { message, type } = e.detail;
    
    // Create notification element (same as upload.js)
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
});
