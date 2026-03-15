// Healthcare AI V2 Dashboard Charts
// Chart.js configuration and management

// Chart color palette
const CHART_COLORS = {
    primary: '#2563eb',
    success: '#059669',
    warning: '#d97706',
    danger: '#dc2626',
    info: '#0284c7',
    gray: '#6b7280',
    purple: '#7c3aed',
    pink: '#db2777'
};

// Chart configuration defaults
const CHART_DEFAULTS = {
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
            cornerRadius: 8,
            displayColors: true
        }
    },
    elements: {
        line: {
            tension: 0.4
        },
        point: {
            radius: 4,
            hoverRadius: 6
        }
    }
};

// Utility functions
function createGradient(ctx, color, height = 300) {
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, color + '40'); // 25% opacity
    gradient.addColorStop(1, color + '00'); // 0% opacity
    return gradient;
}

function formatTime(date) {
    return new Intl.DateTimeFormat('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    }).format(date);
}

function formatPercent(value) {
    return `${Math.round(value)}%`;
}

function formatNumber(value) {
    return new Intl.NumberFormat('en-US').format(value);
}

// Chart Manager Class
class DashboardChartManager {
    constructor() {
        this.charts = new Map();
        this.chartData = new Map();
        this.maxDataPoints = 20; // Maximum data points to keep in time series
        
        // Register default chart configurations
        this.registerChartConfigs();
    }
    
    // Register chart configurations
    registerChartConfigs() {
        // System Performance Chart
        this.registerChart('systemPerformance', {
            type: 'line',
            element: 'systemPerformanceChart',
            config: {
                ...CHART_DEFAULTS,
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'CPU Usage (%)',
                            data: [],
                            borderColor: CHART_COLORS.primary,
                            backgroundColor: (ctx) => createGradient(ctx.chart.ctx, CHART_COLORS.primary),
                            fill: true,
                            tension: 0.4
                        },
                        {
                            label: 'Memory Usage (%)',
                            data: [],
                            borderColor: CHART_COLORS.success,
                            backgroundColor: (ctx) => createGradient(ctx.chart.ctx, CHART_COLORS.success),
                            fill: true,
                            tension: 0.4
                        }
                    ]
                },
                options: {
                    ...CHART_DEFAULTS,
                    scales: {
                        y: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: function(value) {
                                    return formatPercent(value);
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
                    },
                    plugins: {
                        ...CHART_DEFAULTS.plugins,
                        title: {
                            display: false
                        }
                    }
                }
            }
        });
        
        // User Activity Chart (Doughnut)
        this.registerChart('userActivity', {
            type: 'doughnut',
            element: 'userActivityChart',
            config: {
                ...CHART_DEFAULTS,
                data: {
                    labels: ['Active Users', 'Inactive Users'],
                    datasets: [{
                        data: [0, 0],
                        backgroundColor: [
                            CHART_COLORS.primary,
                            '#e5e7eb'
                        ],
                        borderWidth: 2,
                        borderColor: '#ffffff',
                        hoverBorderWidth: 3
                    }]
                },
                options: {
                    ...CHART_DEFAULTS,
                    cutout: '60%',
                    plugins: {
                        ...CHART_DEFAULTS.plugins,
                        legend: {
                            position: 'bottom',
                            labels: {
                                padding: 20,
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            ...CHART_DEFAULTS.plugins.tooltip,
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
                    }
                }
            }
        });
        
        // API Response Time Chart
        this.registerChart('apiResponseTime', {
            type: 'bar',
            element: 'apiResponseTimeChart',
            config: {
                ...CHART_DEFAULTS,
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Response Time (ms)',
                        data: [],
                        backgroundColor: CHART_COLORS.info,
                        borderColor: CHART_COLORS.info,
                        borderWidth: 1,
                        borderRadius: 4,
                        borderSkipped: false
                    }]
                },
                options: {
                    ...CHART_DEFAULTS,
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
                    },
                    plugins: {
                        ...CHART_DEFAULTS.plugins,
                        tooltip: {
                            ...CHART_DEFAULTS.plugins.tooltip,
                            callbacks: {
                                label: function(context) {
                                    return `Response Time: ${context.parsed.y}ms`;
                                }
                            }
                        }
                    }
                }
            }
        });
        
        // Data Pipeline Status Chart
        this.registerChart('pipelineStatus', {
            type: 'horizontalBar',
            element: 'pipelineStatusChart',
            config: {
                ...CHART_DEFAULTS,
                data: {
                    labels: ['Hospital Authority', 'Dept of Health', 'Emergency Services', 'Environmental Data'],
                    datasets: [{
                        label: 'Status',
                        data: [100, 100, 85, 70], // Percentage of uptime
                        backgroundColor: [
                            CHART_COLORS.success,
                            CHART_COLORS.success,
                            CHART_COLORS.warning,
                            CHART_COLORS.danger
                        ],
                        borderWidth: 0,
                        borderRadius: 4
                    }]
                },
                options: {
                    ...CHART_DEFAULTS,
                    indexAxis: 'y',
                    scales: {
                        x: {
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                callback: function(value) {
                                    return formatPercent(value);
                                }
                            },
                            grid: {
                                color: '#f3f4f6'
                            }
                        },
                        y: {
                            grid: {
                                display: false
                            }
                        }
                    },
                    plugins: {
                        ...CHART_DEFAULTS.plugins,
                        legend: {
                            display: false
                        },
                        tooltip: {
                            ...CHART_DEFAULTS.plugins.tooltip,
                            callbacks: {
                                label: function(context) {
                                    return `Uptime: ${formatPercent(context.parsed.x)}`;
                                }
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Register a chart configuration
    registerChart(chartId, config) {
        this.chartData.set(chartId, config);
    }
    
    // Initialize all charts
    initializeCharts() {
        for (const [chartId, config] of this.chartData) {
            this.createChart(chartId, config);
        }
    }
    
    // Create a single chart
    createChart(chartId, config) {
        const element = document.getElementById(config.element);
        if (!element) {
            console.warn(`Chart element not found: ${config.element}`);
            return null;
        }
        
        // Destroy existing chart if it exists
        if (this.charts.has(chartId)) {
            this.charts.get(chartId).destroy();
        }
        
        try {
            const chart = new Chart(element, config.config);
            this.charts.set(chartId, chart);
            console.log(`Chart initialized: ${chartId}`);
            return chart;
        } catch (error) {
            console.error(`Error creating chart ${chartId}:`, error);
            return null;
        }
    }
    
    // Update chart with new data
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
                case 'pipelineStatus':
                    this.updatePipelineStatusChart(chart, data);
                    break;
                default:
                    console.warn(`No update handler for chart: ${chartId}`);
            }
        } catch (error) {
            console.error(`Error updating chart ${chartId}:`, error);
        }
    }
    
    // Update system performance chart
    updateSystemPerformanceChart(chart, data) {
        if (!data.system) return;
        
        const now = new Date();
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
        if (cpuData.length > this.maxDataPoints) {
            cpuData.shift();
            memoryData.shift();
        }
        
        chart.update('none');
    }
    
    // Update user activity chart
    updateUserActivityChart(chart, data) {
        if (!data.users) return;
        
        const activeUsers = data.users.active || 0;
        const totalUsers = data.users.total || 0;
        const inactiveUsers = Math.max(0, totalUsers - activeUsers);
        
        chart.data.datasets[0].data = [activeUsers, inactiveUsers];
        chart.update('none');
    }
    
    // Update API response time chart
    updateApiResponseTimeChart(chart, data) {
        if (!data.ai || !data.ai.avg_response_time_ms) return;
        
        const labels = chart.data.labels;
        const chartData = chart.data.datasets[0].data;
        
        const now = formatTime(new Date());
        const responseTime = data.ai.avg_response_time_ms;
        
        labels.push(now);
        chartData.push(responseTime);
        
        // Keep only last N points
        if (labels.length > this.maxDataPoints) {
            labels.shift();
            chartData.shift();
        }
        
        chart.update('none');
    }
    
    // Update pipeline status chart
    updatePipelineStatusChart(chart, data) {
        if (!data.pipeline) return;
        
        // Calculate uptime percentages based on status
        const statusMap = {
            'healthy': 100,
            'warning': 75,
            'error': 25,
            'unknown': 0
        };
        
        const status = data.pipeline.status || 'unknown';
        const uptime = statusMap[status] || 0;
        
        // Update all data sources with similar status for demo
        chart.data.datasets[0].data = [uptime, uptime, uptime * 0.9, uptime * 0.8];
        
        // Update colors based on status
        const colors = chart.data.datasets[0].data.map(value => {
            if (value >= 95) return CHART_COLORS.success;
            if (value >= 80) return CHART_COLORS.warning;
            return CHART_COLORS.danger;
        });
        chart.data.datasets[0].backgroundColor = colors;
        
        chart.update('none');
    }
    
    // Get chart instance
    getChart(chartId) {
        return this.charts.get(chartId);
    }
    
    // Destroy all charts
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
    
    // Resize all charts
    resizeAllCharts() {
        for (const [chartId, chart] of this.charts) {
            try {
                chart.resize();
            } catch (error) {
                console.error(`Error resizing chart ${chartId}:`, error);
            }
        }
    }
}

// Global chart manager instance
window.dashboardCharts = new DashboardChartManager();

// Global function to update all charts (called from WebSocket)
window.updateDashboardCharts = function(data) {
    if (!window.dashboardCharts) return;
    
    // Update all registered charts
    for (const chartId of window.dashboardCharts.charts.keys()) {
        window.dashboardCharts.updateChart(chartId, data);
    }
};

// Initialize charts when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Wait a bit for elements to be rendered
    setTimeout(() => {
        window.dashboardCharts.initializeCharts();
        console.log('Dashboard charts initialized');
    }, 100);
});

// Handle window resize
window.addEventListener('resize', function() {
    if (window.dashboardCharts) {
        window.dashboardCharts.resizeAllCharts();
    }
});

// Clean up charts on page unload
window.addEventListener('beforeunload', function() {
    if (window.dashboardCharts) {
        window.dashboardCharts.destroyAllCharts();
    }
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DashboardChartManager, CHART_COLORS, CHART_DEFAULTS };
}
