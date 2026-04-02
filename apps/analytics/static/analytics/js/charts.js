// Analytics Charts JavaScript

class AnalyticsCharts {
    constructor(options = {}) {
        this.charts = {};
        this.colors = {
            primary: '#007bff',
            success: '#28a745',
            danger: '#dc3545',
            warning: '#ffc107',
            info: '#17a2b8',
            secondary: '#6c757d'
        };
    }
    
    createLineChart(elementId, data, options = {}) {
        const ctx = document.getElementById(elementId).getContext('2d');
        
        this.charts[elementId] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: data.datasets.map(dataset => ({
                    ...dataset,
                    borderColor: this.colors[dataset.color] || dataset.borderColor,
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    pointRadius: 3,
                    pointHoverRadius: 5
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: options.showLegend !== false,
                        position: 'top'
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: options.beginAtZero !== false,
                        grid: {
                            display: true,
                            color: '#e9ecef'
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
        
        return this.charts[elementId];
    }
    
    createBarChart(elementId, data, options = {}) {
        const ctx = document.getElementById(elementId).getContext('2d');
        
        this.charts[elementId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: data.datasets.map(dataset => ({
                    ...dataset,
                    backgroundColor: this.colors[dataset.color] || dataset.backgroundColor,
                    borderColor: 'transparent',
                    borderRadius: 4
                }))
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: options.showLegend !== false,
                        position: 'top'
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            display: true,
                            color: '#e9ecef'
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
        
        return this.charts[elementId];
    }
    
    createPieChart(elementId, data, options = {}) {
        const ctx = document.getElementById(elementId).getContext('2d');
        
        const backgroundColors = Object.values(this.colors);
        
        this.charts[elementId] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.values,
                    backgroundColor: backgroundColors.slice(0, data.values.length),
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                },
                cutout: '60%'
            }
        });
        
        return this.charts[elementId];
    }
    
    updateChart(elementId, newData) {
        if (this.charts[elementId]) {
            this.charts[elementId].data = newData;
            this.charts[elementId].update();
        }
    }
    
    destroyChart(elementId) {
        if (this.charts[elementId]) {
            this.charts[elementId].destroy();
            delete this.charts[elementId];
        }
    }
    
    createRevenueChart(elementId, data) {
        return this.createLineChart(elementId, {
            labels: data.labels,
            datasets: [{
                label: 'Revenue',
                data: data.revenue,
                color: 'success',
                borderWidth: 2
            }, {
                label: 'Forecast',
                data: data.forecast,
                color: 'primary',
                borderWidth: 2,
                borderDash: [5, 5]
            }]
        });
    }
    
    createBookingsChart(elementId, data) {
        return this.createBarChart(elementId, {
            labels: data.labels,
            datasets: [{
                label: 'Bookings',
                data: data.bookings,
                color: 'primary'
            }]
        });
    }
    
    createFleetUtilizationChart(elementId, data) {
        return this.createBarChart(elementId, {
            labels: data.labels,
            datasets: [{
                label: 'Utilization %',
                data: data.utilization,
                color: 'info'
            }]
        });
    }
    
    createPaymentMethodsChart(elementId, data) {
        return this.createPieChart(elementId, {
            labels: data.labels,
            values: data.values
        });
    }
}

class AnalyticsDashboard {
    constructor(options = {}) {
        this.charts = new AnalyticsCharts();
        this.dateRange = options.dateRange || '30d';
        this.refreshInterval = options.refreshInterval || 300000; // 5 minutes
        this.init();
    }
    
    init() {
        this.loadData();
        this.startAutoRefresh();
    }
    
    loadData() {
        fetch(`/api/v1/analytics/dashboard/?range=${this.dateRange}`)
            .then(response => response.json())
            .then(data => {
                this.updateKPIs(data.kpis);
                this.updateCharts(data.charts);
                this.updateTables(data.tables);
            });
    }
    
    updateKPIs(kpis) {
        Object.keys(kpis).forEach(key => {
            const element = document.getElementById(`kpi-${key}`);
            if (element) {
                element.textContent = this.formatValue(kpis[key].value, kpis[key].format);
                
                const changeElement = document.getElementById(`kpi-${key}-change`);
                if (changeElement) {
                    const change = kpis[key].change;
                    changeElement.className = `kpi-change ${change >= 0 ? 'positive' : 'negative'}`;
                    changeElement.innerHTML = `
                        <i class="fas fa-${change >= 0 ? 'arrow-up' : 'arrow-down'}"></i>
                        ${Math.abs(change).toFixed(1)}%
                    `;
                }
            }
        });
    }
    
    updateCharts(charts) {
        if (charts.revenue) {
            this.charts.createRevenueChart('revenueChart', charts.revenue);
        }
        
        if (charts.bookings) {
            this.charts.createBookingsChart('bookingsChart', charts.bookings);
        }
        
        if (charts.fleet) {
            this.charts.createFleetUtilizationChart('fleetChart', charts.fleet);
        }
        
        if (charts.payments) {
            this.charts.createPaymentMethodsChart('paymentsChart', charts.payments);
        }
    }
    
    updateTables(tables) {
        if (tables.recentBookings) {
            this.renderTable('recentBookingsTable', tables.recentBookings);
        }
        
        if (tables.topCustomers) {
            this.renderTable('topCustomersTable', tables.topCustomers);
        }
    }
    
    renderTable(elementId, data) {
        const tbody = document.querySelector(`#${elementId} tbody`);
        if (!tbody) return;
        
        tbody.innerHTML = data.rows.map(row => {
            return `<tr>
                ${row.map(cell => `<td>${cell}</td>`).join('')}
            </tr>`;
        }).join('');
    }
    
    formatValue(value, format) {
        if (format === 'currency') {
            return `$${value.toFixed(2)}`;
        } else if (format === 'percentage') {
            return `${value.toFixed(1)}%`;
        } else {
            return value.toString();
        }
    }
    
    startAutoRefresh() {
        setInterval(() => {
            this.loadData();
        }, this.refreshInterval);
    }
    
    exportData(format) {
        window.location.href = `/api/v1/analytics/export/?format=${format}&range=${this.dateRange}`;
    }
    
    setDateRange(range) {
        this.dateRange = range;
        this.loadData();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('analyticsDashboard')) {
        window.dashboard = new AnalyticsDashboard({
            dateRange: '30d'
        });
    }
});