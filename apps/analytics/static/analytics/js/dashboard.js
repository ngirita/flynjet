// Analytics Dashboard JavaScript

class DateRangePicker {
    constructor(options = {}) {
        this.element = options.element;
        this.onChange = options.onChange || function() {};
        this.startDate = options.startDate || this.getDefaultStartDate();
        this.endDate = options.endDate || new Date();
        
        this.init();
    }
    
    init() {
        this.render();
        this.bindEvents();
    }
    
    render() {
        this.element.innerHTML = `
            <div class="date-range-picker" id="dateRangePicker">
                <i class="fas fa-calendar"></i>
                <span id="dateRangeText">${this.formatDateRange()}</span>
                <i class="fas fa-chevron-down"></i>
            </div>
            <div class="date-range-dropdown" id="dateRangeDropdown" style="display: none;">
                <div class="preset-ranges">
                    <button data-range="today">Today</button>
                    <button data-range="yesterday">Yesterday</button>
                    <button data-range="7d">Last 7 Days</button>
                    <button data-range="30d">Last 30 Days</button>
                    <button data-range="90d">Last 90 Days</button>
                    <button data-range="thisMonth">This Month</button>
                    <button data-range="lastMonth">Last Month</button>
                    <button data-range="custom">Custom Range</button>
                </div>
                <div class="custom-range" style="display: none;">
                    <input type="date" id="startDate" value="${this.formatDate(this.startDate)}">
                    <input type="date" id="endDate" value="${this.formatDate(this.endDate)}">
                    <button class="apply-range">Apply</button>
                </div>
            </div>
        `;
    }
    
    bindEvents() {
        const picker = this.element.querySelector('#dateRangePicker');
        const dropdown = this.element.querySelector('#dateRangeDropdown');
        
        picker.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
        });
        
        document.addEventListener('click', (e) => {
            if (!this.element.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
        
        // Preset ranges
        this.element.querySelectorAll('[data-range]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const range = e.target.dataset.range;
                this.setPresetRange(range);
                dropdown.style.display = 'none';
            });
        });
        
        // Custom range
        const customBtn = this.element.querySelector('[data-range="custom"]');
        const customRange = this.element.querySelector('.custom-range');
        
        customBtn.addEventListener('click', () => {
            customRange.style.display = 'block';
        });
        
        this.element.querySelector('.apply-range').addEventListener('click', () => {
            this.startDate = new Date(this.element.querySelector('#startDate').value);
            this.endDate = new Date(this.element.querySelector('#endDate').value);
            this.updateRange();
            dropdown.style.display = 'none';
        });
    }
    
    setPresetRange(range) {
        const now = new Date();
        
        switch(range) {
            case 'today':
                this.startDate = new Date(now.setHours(0,0,0,0));
                this.endDate = new Date();
                break;
            case 'yesterday':
                this.startDate = new Date(now.setDate(now.getDate() - 1));
                this.startDate.setHours(0,0,0,0);
                this.endDate = new Date(this.startDate);
                this.endDate.setHours(23,59,59,999);
                break;
            case '7d':
                this.endDate = new Date();
                this.startDate = new Date(now.setDate(now.getDate() - 7));
                break;
            case '30d':
                this.endDate = new Date();
                this.startDate = new Date(now.setDate(now.getDate() - 30));
                break;
            case '90d':
                this.endDate = new Date();
                this.startDate = new Date(now.setDate(now.getDate() - 90));
                break;
            case 'thisMonth':
                this.startDate = new Date(now.getFullYear(), now.getMonth(), 1);
                this.endDate = new Date();
                break;
            case 'lastMonth':
                this.startDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
                this.endDate = new Date(now.getFullYear(), now.getMonth(), 0);
                break;
        }
        
        this.updateRange();
    }
    
    updateRange() {
        const textElement = this.element.querySelector('#dateRangeText');
        textElement.textContent = this.formatDateRange();
        
        this.onChange({
            startDate: this.startDate,
            endDate: this.endDate
        });
    }
    
    formatDateRange() {
        if (this.isSameDay(this.startDate, this.endDate)) {
            return this.formatDate(this.startDate);
        } else {
            return `${this.formatDate(this.startDate)} - ${this.formatDate(this.endDate)}`;
        }
    }
    
    formatDate(date) {
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }
    
    isSameDay(d1, d2) {
        return d1.toDateString() === d2.toDateString();
    }
    
    getDefaultStartDate() {
        const date = new Date();
        date.setDate(date.getDate() - 30);
        return date;
    }
}

class ReportBuilder {
    constructor(options = {}) {
        this.container = options.container;
        this.reportType = options.reportType || 'revenue';
        this.fields = [];
        this.filters = [];
        
        this.init();
    }
    
    init() {
        this.render();
        this.bindEvents();
    }
    
    render() {
        this.container.innerHTML = `
            <div class="report-builder">
                <div class="builder-toolbar">
                    <select id="reportType">
                        <option value="revenue">Revenue Report</option>
                        <option value="bookings">Bookings Report</option>
                        <option value="customer">Customer Report</option>
                        <option value="fleet">Fleet Report</option>
                    </select>
                    
                    <button class="btn btn-primary" id="generateReport">
                        <i class="fas fa-play"></i> Generate
                    </button>
                    
                    <button class="btn btn-success" id="exportReport">
                        <i class="fas fa-download"></i> Export
                    </button>
                </div>
                
                <div class="builder-fields">
                    <h6>Select Fields</h6>
                    <div id="fieldsList"></div>
                </div>
                
                <div class="builder-filters">
                    <h6>Filters</h6>
                    <div id="filtersList"></div>
                    <button class="btn btn-sm btn-outline-primary" id="addFilter">
                        <i class="fas fa-plus"></i> Add Filter
                    </button>
                </div>
            </div>
        `;
        
        this.loadFields();
    }
    
    bindEvents() {
        document.getElementById('reportType').addEventListener('change', (e) => {
            this.reportType = e.target.value;
            this.loadFields();
        });
        
        document.getElementById('generateReport').addEventListener('click', () => {
            this.generate();
        });
        
        document.getElementById('exportReport').addEventListener('click', () => {
            this.export();
        });
        
        document.getElementById('addFilter').addEventListener('click', () => {
            this.addFilter();
        });
    }
    
    loadFields() {
        const fields = this.getFieldsForType(this.reportType);
        const container = document.getElementById('fieldsList');
        
        container.innerHTML = fields.map(field => `
            <label class="field-checkbox">
                <input type="checkbox" value="${field.value}" checked>
                ${field.label}
            </label>
        `).join('');
    }
    
    getFieldsForType(type) {
        const fieldSets = {
            'revenue': [
                { value: 'date', label: 'Date' },
                { value: 'revenue', label: 'Revenue' },
                { value: 'bookings', label: 'Bookings' },
                { value: 'avg_value', label: 'Average Value' }
            ],
            'bookings': [
                { value: 'reference', label: 'Reference' },
                { value: 'customer', label: 'Customer' },
                { value: 'route', label: 'Route' },
                { value: 'amount', label: 'Amount' },
                { value: 'status', label: 'Status' }
            ],
            'customer': [
                { value: 'name', label: 'Name' },
                { value: 'email', label: 'Email' },
                { value: 'bookings', label: 'Bookings' },
                { value: 'spent', label: 'Total Spent' },
                { value: 'last_booking', label: 'Last Booking' }
            ],
            'fleet': [
                { value: 'aircraft', label: 'Aircraft' },
                { value: 'flights', label: 'Flights' },
                { value: 'hours', label: 'Hours' },
                { value: 'utilization', label: 'Utilization' },
                { value: 'revenue', label: 'Revenue' }
            ]
        };
        
        return fieldSets[type] || [];
    }
    
    addFilter() {
        const container = document.getElementById('filtersList');
        const filterId = Date.now();
        
        const filterDiv = document.createElement('div');
        filterDiv.className = 'filter-row';
        filterDiv.innerHTML = `
            <select class="filter-field">
                ${this.getFieldsForType(this.reportType).map(f => 
                    `<option value="${f.value}">${f.label}</option>`
                ).join('')}
            </select>
            <select class="filter-operator">
                <option value="eq">Equals</option>
                <option value="gt">Greater Than</option>
                <option value="lt">Less Than</option>
                <option value="contains">Contains</option>
            </select>
            <input type="text" class="filter-value" placeholder="Value">
            <button class="btn btn-sm btn-danger remove-filter" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        container.appendChild(filterDiv);
    }
    
    generate() {
        const params = {
            type: this.reportType,
            fields: Array.from(document.querySelectorAll('#fieldsList input:checked')).map(cb => cb.value),
            filters: this.getFilters()
        };
        
        fetch('/api/v1/analytics/reports/generate/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify(params)
        })
        .then(response => response.json())
        .then(data => {
            this.displayResults(data);
        });
    }
    
    getFilters() {
        const filters = [];
        document.querySelectorAll('.filter-row').forEach(row => {
            filters.push({
                field: row.querySelector('.filter-field').value,
                operator: row.querySelector('.filter-operator').value,
                value: row.querySelector('.filter-value').value
            });
        });
        return filters;
    }
    
    displayResults(data) {
        // Create results modal or section
        const resultsDiv = document.createElement('div');
        resultsDiv.className = 'report-results';
        resultsDiv.innerHTML = `
            <h5>Report Results</h5>
            <pre>${JSON.stringify(data, null, 2)}</pre>
        `;
        
        this.container.appendChild(resultsDiv);
    }
    
    export() {
        const format = prompt('Export format (csv, excel, pdf):', 'csv');
        if (format) {
            window.location.href = `/api/v1/analytics/export/?format=${format}`;
        }
    }
    
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// Export utilities
window.DateRangePicker = DateRangePicker;
window.ReportBuilder = ReportBuilder;