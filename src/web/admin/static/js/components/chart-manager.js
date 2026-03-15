/**
 * Healthcare AI V2 Admin Chart Manager
 * Centralized chart management and configuration
 */

class ChartManager {
    constructor() {
        this.charts = new Map();
        this.chartConfigs = new Map();
        this.defaultColors = {
            primary: '#2563eb',
            success: '#059669',
            warning: '#d97706',
            danger: '#dc2626',
            info: '#0284c7',
            gray: '#6b7280',
            purple: '#7c3aed',
            pink: '#db2777'
        };
        
        this.registerDefaultConfigs();
    }
    
    /**
     * Register default chart configurations
     */
    registerDefaultConfigs() {
        // System Performance Chart
        this.registerChart('systemPerformance', {
            type: 'line',
            canvasId: 'systemPerformanceChart',
            config: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 20
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: '#ffffff',
                        bodyColor: '#ffffff',
                        borderColor: '#e5e7eb',
                        borderWidth: 1,
                        cornerRadius: 8
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        },
                        grid: {
                            color: '#f3f4f6'
                        }
                    },
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                minute: 'HH:mm',
                                hour: 'HH:mm'
                            }
                        },
                        grid: {
                            color: '#f3f4f6'
                        }
                    }
                }
            }
        });
        
        // User Activity Chart
        this.registerChart('userActivity', {
            type: 'doughnut',
            canvasId: 'userActivityChart',
            config: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? Math.round((value / total) * 100) : 0;
                                return `${label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                },
                cutout: '60%'
            }
        });
        
        // API Response Time Chart
        this.registerChart('apiResponseTime', {
            type: 'bar',
            canvasId: 'apiResponseTimeChart',
            config: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `Response Time: ${context.parsed.y}ms`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value + 'ms';
                            }
                        },
                        grid: {
                            color: '#f3f4f6'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }
    
    /**
     * Register a chart configuration
     */
    registerChart(chartId, config) {
        this.chartConfigs.set(chartId, config);
    }
    
    /**
     * Initialize all charts (only those that exist on current page)
     */
    initializeCharts() {
        let initializedCount = 0;
        for (const [chartId, config] of this.chartConfigs) {
            if (this.createChart(chartId, config)) {
                initializedCount++;
            }
        }
        if (initializedCount > 0) {
            console.log(`Initialized ${initializedCount} chart(s)`);
        }
    }
    
    /**
     * Create a single chart
     */
    createChart(chartId, config) {
        const canvas = document.getElementById(config.canvasId);
        if (!canvas) {
            // Silent - not all charts exist on every page
            return false;
        }
        
        // Destroy existing chart if it exists
        if (this.charts.has(chartId)) {
            this.charts.get(chartId).destroy();
        }
        
        try {
            const chartConfig = {
                ...config.config,
                data: this.getDefaultData(config.type)
            };
            
            const chart = new Chart(canvas.getContext('2d'), {
                type: config.type,
                data: chartConfig.data,
                options: chartConfig
            });
            this.charts.set(chartId, chart);
            return true;
        } catch (error) {
            console.error(`Error creating chart ${chartId}:`, error);
            return false;
        }
    }
    
    /**
     * Get default data for chart type
     */
    getDefaultData(type) {
        switch (type) {
            case 'line':
                return {
                    labels: [],
                    datasets: []
                };
            case 'doughnut':
                return {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: [],
                        borderWidth: 2,
                        borderColor: '#ffffff'
                    }]
                };
            case 'bar':
                return {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: this.defaultColors.primary,
                        borderColor: this.defaultColors.primary,
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                };
            default:
                return { labels: [], datasets: [] };
        }
    }
    
    /**
     * Update chart with new data
     */
    updateChart(chartId, data) {
        const chart = this.charts.get(chartId);
        if (!chart) {
            console.warn(`Chart not found: ${chartId}`);
            return;
        }
        
        try {
            switch (chartId) {
                case 'systemPerformance':
                    this.updateSystemPerformanceChart(chart, data);
                    break;
                case 'userActivity':
                    this.updateUserActivityChart(chart, data);
                    break;
                case 'apiResponseTime':
                    this.updateApiResponseTimeChart(chart, data);
                    break;
                default:
                    console.warn(`No update handler for chart: ${chartId}`);
            }
        } catch (error) {
            console.error(`Error updating chart ${chartId}:`, error);
        }
    }
    
    /**
     * Update system performance chart
     */
    updateSystemPerformanceChart(chart, data) {
        if (!data.system) return;
        
        const now = new Date();
        const maxDataPoints = 20;
        
        // Initialize datasets if they don't exist
        if (chart.data.datasets.length === 0) {
            chart.data.datasets = [
                {
                    label: 'CPU Usage (%)',
                    data: [],
                    borderColor: this.defaultColors.primary,
                    backgroundColor: (ctx) => adminUtils.createChartGradient(ctx.chart.ctx, this.defaultColors.primary),
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Memory Usage (%)',
                    data: [],
                    borderColor: this.defaultColors.success,
                    backgroundColor: (ctx) => adminUtils.createChartGradient(ctx.chart.ctx, this.defaultColors.success),
                    fill: true,
                    tension: 0.4
                }
            ];
        }
        
        const cpuData = chart.data.datasets[0].data;
        const memoryData = chart.data.datasets[1].data;
        
        // Add new data point
        cpuData.push({
            x: now,
            y: data.system.cpu_percent || 0
        });
        memoryData.push({
            x: now,
            y: data.system.memory_percent || 0
        });
        
        // Keep only last N points
        if (cpuData.length > maxDataPoints) {
            cpuData.shift();
            memoryData.shift();
        }
        
        chart.update('none');
    }
    
    /**
     * Update user activity chart
     */
    updateUserActivityChart(chart, data) {
        if (!data.users) return;
        
        const activeUsers = data.users.active || 0;
        const totalUsers = data.users.total || 0;
        const inactiveUsers = Math.max(0, totalUsers - activeUsers);
        
        chart.data.labels = ['Active Users', 'Inactive Users'];
        chart.data.datasets[0].data = [activeUsers, inactiveUsers];
        chart.data.datasets[0].backgroundColor = [
            this.defaultColors.primary,
            '#e5e7eb'
        ];
        
        chart.update('none');
    }
    
    /**
     * Update API response time chart
     */
    updateApiResponseTimeChart(chart, data) {
        if (!data.ai || !data.ai.avg_response_time_ms) return;
        
        const labels = chart.data.labels;
        const chartData = chart.data.datasets[0].data;
        const maxDataPoints = 15;
        
        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        const responseTime = data.ai.avg_response_time_ms;
        
        labels.push(now);
        chartData.push(responseTime);
        
        // Keep only last N points
        if (labels.length > maxDataPoints) {
            labels.shift();
            chartData.shift();
        }
        
        chart.update('none');
    }
    
    /**
     * Get chart instance
     */
    getChart(chartId) {
        return this.charts.get(chartId);
    }
    
    /**
     * Destroy all charts
     */
    destroyAllCharts() {
        for (const [chartId, chart] of this.charts) {
            try {
                chart.destroy();
            } catch (error) {
                console.error(`Error destroying chart ${chartId}:`, error);
            }
        }
        this.charts.clear();
    }
    
    /**
     * Resize all charts
     */
    resizeAllCharts() {
        for (const [chartId, chart] of this.charts) {
            try {
                chart.resize();
            } catch (error) {
                console.error(`Error resizing chart ${chartId}:`, error);
            }
        }
    }
    
    /**
     * Create custom chart
     */
    createCustomChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`Canvas not found: ${canvasId}`);
            return null;
        }
        
        try {
            const chart = new Chart(canvas, config);
            return chart;
        } catch (error) {
            console.error(`Error creating custom chart:`, error);
            return null;
        }
    }
}

// Global chart manager instance
window.chartManager = new ChartManager();

// Global function to update all charts
window.updateDashboardCharts = function(data) {
    if (!window.chartManager) return;

    for (const chartId of window.chartManager.chartConfigs.keys()) {
        if (window.chartManager.charts.has(chartId)) {
            window.chartManager.updateChart(chartId, data);
        }
    }
};

// Don't auto-initialize charts on every page
// Pages that need charts should call window.chartManager.initializeCharts() manually
// This prevents warnings about missing chart canvases on pages that don't use them

// Handle window resize
window.addEventListener('resize', function() {
    if (window.chartManager) {
        window.chartManager.resizeAllCharts();
    }
});

// Clean up charts on page unload
window.addEventListener('beforeunload', function() {
    if (window.chartManager) {
        window.chartManager.destroyAllCharts();
    }
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ChartManager };
}
