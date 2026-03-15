/**
 * Healthcare AI V2 Admin Base Component
 * Base class for reusable components
 */

class BaseComponent {
    constructor(config = {}) {
        this.loading = false;
        this.error = null;
        this.data = config.initialData || null;
        this.config = {
            autoRefresh: true,
            refreshInterval: 30000, // 30 seconds
            ...config
        };
        
        this.refreshTimer = null;
    }

    /**
     * Initialize the component
     */
    async init() {
        if (this.config.autoRefresh) {
            this.startAutoRefresh();
        }
        
        await this.loadData();
    }

    /**
     * Load data from API
     */
    async loadData() {
        if (!this.config.endpoint) {
            console.warn('No endpoint configured for component');
            return;
        }

        this.loading = true;
        this.error = null;
        
        try {
            this.data = await adminAPI.get(this.config.endpoint);
            this.onDataLoaded(this.data);
        } catch (error) {
            this.error = error.message;
            this.onError(error);
        } finally {
            this.loading = false;
        }
    }

    /**
     * Refresh data
     */
    async refresh() {
        await this.loadData();
    }

    /**
     * Start auto-refresh timer
     */
    startAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
        }
        
        this.refreshTimer = setInterval(() => {
            if (!this.loading) {
                this.loadData();
            }
        }, this.config.refreshInterval);
    }

    /**
     * Stop auto-refresh timer
     */
    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    }

    /**
     * Handle data loaded event
     */
    onDataLoaded(data) {
        // Override in subclasses
    }

    /**
     * Handle error event
     */
    onError(error) {
        this.showError(error.message);
    }

    /**
     * Show error notification
     */
    showError(message) {
        Alpine.store('admin').showNotification('Error', message, 'error');
    }

    /**
     * Show success notification
     */
    showSuccess(message) {
        Alpine.store('admin').showNotification('Success', message, 'success');
    }

    /**
     * Show info notification
     */
    showInfo(message) {
        Alpine.store('admin').showNotification('Info', message, 'info');
    }

    /**
     * Destroy component and cleanup
     */
    destroy() {
        this.stopAutoRefresh();
    }
}

/**
 * Data Table Component
 */
class DataTableComponent extends BaseComponent {
    constructor(config = {}) {
        super({
            pageSize: 10,
            sortField: 'created_at',
            sortOrder: 'desc',
            ...config
        });
        
        this.currentPage = 1;
        this.totalPages = 1;
        this.totalItems = 0;
        this.filteredData = [];
        this.searchTerm = '';
        this.filters = {};
    }

    /**
     * Load data with pagination and filtering
     */
    async loadData() {
        if (!this.config.endpoint) return;

        this.loading = true;
        this.error = null;
        
        try {
            const params = new URLSearchParams({
                page: this.currentPage,
                limit: this.config.pageSize,
                sort_by: this.config.sortField,
                sort_order: this.config.sortOrder,
                ...this.filters
            });
            
            if (this.searchTerm) {
                params.append('search', this.searchTerm);
            }
            
            const response = await adminAPI.get(`${this.config.endpoint}?${params}`);
            
            this.data = response.data || response;
            this.totalItems = response.total || this.data.length;
            this.totalPages = Math.ceil(this.totalItems / this.config.pageSize);
            this.filteredData = this.data;
            
            this.onDataLoaded(this.data);
        } catch (error) {
            this.error = error.message;
            this.onError(error);
        } finally {
            this.loading = false;
        }
    }

    /**
     * Set search term
     */
    setSearch(term) {
        this.searchTerm = term;
        this.currentPage = 1;
        this.loadData();
    }

    /**
     * Set filter
     */
    setFilter(key, value) {
        this.filters[key] = value;
        this.currentPage = 1;
        this.loadData();
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.filters = {};
        this.searchTerm = '';
        this.currentPage = 1;
        this.loadData();
    }

    /**
     * Sort data
     */
    sort(field) {
        if (this.config.sortField === field) {
            this.config.sortOrder = this.config.sortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            this.config.sortField = field;
            this.config.sortOrder = 'desc';
        }
        this.loadData();
    }

    /**
     * Go to specific page
     */
    goToPage(page) {
        if (page >= 1 && page <= this.totalPages) {
            this.currentPage = page;
            this.loadData();
        }
    }

    /**
     * Get pagination info
     */
    getPaginationInfo() {
        const start = (this.currentPage - 1) * this.config.pageSize + 1;
        const end = Math.min(this.currentPage * this.config.pageSize, this.totalItems);
        return { start, end, total: this.totalItems };
    }
}

/**
 * Chart Component
 */
class ChartComponent extends BaseComponent {
    constructor(config = {}) {
        super(config);
        this.chart = null;
        this.chartConfig = config.chartConfig || {};
    }

    /**
     * Initialize chart
     */
    async init() {
        await super.init();
        this.createChart();
    }

    /**
     * Create chart instance
     */
    createChart() {
        const canvas = document.getElementById(this.config.canvasId);
        if (!canvas) {
            console.error(`Chart canvas not found: ${this.config.canvasId}`);
            return;
        }

        if (this.chart) {
            this.chart.destroy();
        }

        this.chart = new Chart(canvas, {
            ...this.chartConfig,
            data: this.getChartData()
        });
    }

    /**
     * Get chart data (override in subclasses)
     */
    getChartData() {
        return {
            labels: [],
            datasets: []
        };
    }

    /**
     * Update chart with new data
     */
    updateChart() {
        if (this.chart) {
            this.chart.data = this.getChartData();
            this.chart.update();
        }
    }

    /**
     * Handle data loaded event
     */
    onDataLoaded(data) {
        super.onDataLoaded(data);
        this.updateChart();
    }

    /**
     * Destroy chart
     */
    destroy() {
        super.destroy();
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }
}

/**
 * Form Component
 */
class FormComponent extends BaseComponent {
    constructor(config = {}) {
        super(config);
        this.formData = {};
        this.validationErrors = {};
        this.isSubmitting = false;
    }

    /**
     * Set form data
     */
    setFormData(data) {
        this.formData = { ...this.formData, ...data };
    }

    /**
     * Get form data
     */
    getFormData() {
        return this.formData;
    }

    /**
     * Validate form data
     */
    validate() {
        this.validationErrors = {};
        // Override in subclasses for specific validation
        return Object.keys(this.validationErrors).length === 0;
    }

    /**
     * Submit form
     */
    async submit() {
        if (!this.validate()) {
            this.showError('Please fix validation errors');
            return false;
        }

        this.isSubmitting = true;
        
        try {
            const method = this.config.method || 'POST';
            const endpoint = this.config.endpoint;
            
            let response;
            if (method === 'POST') {
                response = await adminAPI.post(endpoint, this.formData);
            } else if (method === 'PUT') {
                response = await adminAPI.put(endpoint, this.formData);
            }
            
            this.onSubmitSuccess(response);
            return true;
        } catch (error) {
            this.onSubmitError(error);
            return false;
        } finally {
            this.isSubmitting = false;
        }
    }

    /**
     * Handle successful submission
     */
    onSubmitSuccess(response) {
        this.showSuccess('Form submitted successfully');
        this.formData = {};
        this.validationErrors = {};
    }

    /**
     * Handle submission error
     */
    onSubmitError(error) {
        this.showError(error.message);
    }

    /**
     * Reset form
     */
    reset() {
        this.formData = {};
        this.validationErrors = {};
        this.isSubmitting = false;
    }
}

// Export classes
window.BaseComponent = BaseComponent;
window.DataTableComponent = DataTableComponent;
window.ChartComponent = ChartComponent;
window.FormComponent = FormComponent;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        BaseComponent,
        DataTableComponent,
        ChartComponent,
        FormComponent
    };
}
