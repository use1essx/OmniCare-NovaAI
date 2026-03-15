/**
 * Healthcare AI V2 Admin Data Table Component
 * Reusable data table with sorting, filtering, and pagination
 */

// Register component function
let dataTableComponentRegistered = false;
function registerDataTableComponent() {
    if (typeof Alpine === 'undefined') {
        return false;
    }
    
    if (dataTableComponentRegistered) {
        return true; // Already registered
    }
    
    dataTableComponentRegistered = true;
    Alpine.data('dataTable', (config = {}) => ({
    // Data
    data: [],
    filteredData: [],
    loading: false,
    error: null,
    
    // Pagination
    currentPage: 1,
    itemsPerPage: config.pageSize || 10,
    totalPages: 1,
    totalItems: 0,
    
    // Filtering and sorting
    searchTerm: '',
    sortField: config.sortField || '',
    sortDirection: config.sortOrder || 'asc',
    filters: {},
    
    // Selection
    selectedItems: new Set(),
    selectAll: false,
    
    // Configuration
    config: {
        endpoint: null,
        autoLoad: true,
        refreshInterval: 30000,
        ...config
    },
    
    // Initialize component
    async init() {
        if (this.config.autoLoad && this.config.endpoint) {
            await this.loadData();
        }
        
        if (this.config.refreshInterval > 0) {
            this.startAutoRefresh();
        }
        
        // Listen for global refresh events
        window.addEventListener('admin:refresh-data', () => {
            this.loadData();
        });
    },
    
    // Load data from API
    async loadData() {
        if (!this.config.endpoint) {
            console.warn('No endpoint configured for data table');
            return;
        }
        
        this.loading = true;
        this.error = null;
        
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                limit: this.itemsPerPage,
                sort_by: this.sortField,
                sort_order: this.sortDirection
            });
            
            // Add search term
            if (this.searchTerm) {
                params.append('search', this.searchTerm);
            }
            
            // Add filters
            Object.entries(this.filters).forEach(([key, value]) => {
                if (value !== null && value !== undefined && value !== '') {
                    params.append(key, value);
                }
            });
            
            const response = await adminAPI.get(`${this.config.endpoint}?${params}`);
            
            // Handle different response formats
            if (response.data) {
                this.data = response.data;
                this.totalItems = response.total || response.data.length;
            } else if (Array.isArray(response)) {
                this.data = response;
                this.totalItems = response.length;
            } else {
                this.data = [];
                this.totalItems = 0;
            }
            
            this.totalPages = Math.ceil(this.totalItems / this.itemsPerPage);
            this.filteredData = this.data;
            
            // Reset selection
            this.selectedItems.clear();
            this.selectAll = false;
            
        } catch (error) {
            this.error = error.message;
            console.error('Error loading data:', error);
        } finally {
            this.loading = false;
        }
    },
    
    // Refresh data
    async refresh() {
        await this.loadData();
    },
    
    // Start auto-refresh
    startAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        this.refreshTimer = setInterval(() => {
            if (!this.loading) {
                this.loadData();
            }
        }, this.config.refreshInterval);
    },
    
    // Stop auto-refresh
    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    },
    
    // Set search term
    setSearch(term) {
        this.searchTerm = term;
        this.currentPage = 1;
        this.loadData();
    },
    
    // Set filter
    setFilter(key, value) {
        this.filters[key] = value;
        this.currentPage = 1;
        this.loadData();
    },
    
    // Clear all filters
    clearFilters() {
        this.filters = {};
        this.searchTerm = '';
        this.currentPage = 1;
        this.loadData();
    },
    
    // Sort by field
    sort(field) {
        if (this.sortField === field) {
            this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
            this.sortField = field;
            this.sortDirection = 'desc';
        }
        this.loadData();
    },
    
    // Go to specific page
    goToPage(page) {
        if (page >= 1 && page <= this.totalPages) {
            this.currentPage = page;
            this.loadData();
        }
    },
    
    // Go to next page
    nextPage() {
        if (this.currentPage < this.totalPages) {
            this.goToPage(this.currentPage + 1);
        }
    },
    
    // Go to previous page
    prevPage() {
        if (this.currentPage > 1) {
            this.goToPage(this.currentPage - 1);
        }
    },
    
    // Toggle item selection
    toggleSelection(itemId) {
        if (this.selectedItems.has(itemId)) {
            this.selectedItems.delete(itemId);
        } else {
            this.selectedItems.add(itemId);
        }
        this.updateSelectAllState();
    },
    
    // Toggle select all
    toggleSelectAll() {
        if (this.selectAll) {
            this.selectedItems.clear();
        } else {
            this.data.forEach(item => {
                this.selectedItems.add(item.id);
            });
        }
        this.selectAll = !this.selectAll;
    },
    
    // Update select all state
    updateSelectAllState() {
        this.selectAll = this.data.length > 0 && this.selectedItems.size === this.data.length;
    },
    
    // Get selected items
    getSelectedItems() {
        return this.data.filter(item => this.selectedItems.has(item.id));
    },
    
    // Clear selection
    clearSelection() {
        this.selectedItems.clear();
        this.selectAll = false;
    },
    
    // Get pagination info
    getPaginationInfo() {
        const start = Math.min((this.currentPage - 1) * this.itemsPerPage + 1, this.totalItems);
        const end = Math.min(this.currentPage * this.itemsPerPage, this.totalItems);
        return { start, end, total: this.totalItems };
    },
    
    // Format data for display
    formatCellValue(value, type = 'text') {
        switch (type) {
            case 'date':
                return adminUtils.formatDate(value);
            case 'datetime':
                return adminUtils.formatDateTime(value);
            case 'number':
                return adminUtils.formatNumber(value);
            case 'currency':
                return adminUtils.formatCurrency(value);
            case 'percent':
                return adminUtils.formatPercent(value);
            case 'status':
                return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${adminUtils.getStatusColor(value)}">
                    <i class="fas ${adminUtils.getStatusIcon(value)} mr-1"></i>
                    ${value}
                </span>`;
            case 'badge':
                return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                    ${value}
                </span>`;
            default:
                return value;
        }
    },
    
    // Export data
    exportData(format = 'json') {
        const data = this.getSelectedItems().length > 0 ? this.getSelectedItems() : this.data;
        
        switch (format) {
            case 'json':
                adminUtils.downloadJSON(data, `data_${Date.now()}.json`);
                break;
            case 'csv':
                adminUtils.downloadCSV(data, `data_${Date.now()}.csv`);
                break;
        }
    },
    
    // Bulk action
    async bulkAction(action, data = {}) {
        if (this.selectedItems.size === 0) {
            Alpine.store('admin').showNotification('No items selected', 'Please select items to perform bulk action', 'warning');
            return;
        }
        
        const selectedIds = Array.from(this.selectedItems);
        
        try {
            const response = await adminAPI.post(`/bulk-actions/${action}`, {
                item_ids: selectedIds,
                ...data
            });
            
            Alpine.store('admin').showNotification('Bulk action completed', `${selectedIds.length} items processed`, 'success');
            this.clearSelection();
            await this.loadData();
            
        } catch (error) {
            Alpine.store('admin').showNotification('Bulk action failed', error.message, 'error');
        }
    },
    
    // Destroy component
    destroy() {
        this.stopAutoRefresh();
        window.removeEventListener('admin:refresh-data', this.loadData);
    }
}));
    
    return true;
}

// Try to register immediately, or wait for Alpine
if (typeof Alpine !== 'undefined') {
    registerDataTableComponent();
} else {
    // Wait for Alpine to be ready
    document.addEventListener('alpine:init', () => {
        registerDataTableComponent();
    });
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { dataTable };
}
