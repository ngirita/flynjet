// Reports Management JavaScript

class ReportsManager {
    constructor(options = {}) {
        this.reportsList = document.getElementById('reportsList');
        this.loadReports();
    }
    
    loadReports() {
        fetch('/api/v1/analytics/reports/')
            .then(response => response.json())
            .then(data => {
                this.renderReports(data);
            });
    }
    
    renderReports(reports) {
        if (!this.reportsList) return;
        
        this.reportsList.innerHTML = reports.map(report => `
            <div class="report-card">
                <div class="report-icon">
                    <i class="fas fa-${this.getReportIcon(report.report_type)}"></i>
                </div>
                <div class="report-name">${report.name}</div>
                <div class="report-meta">
                    ${report.report_type} • ${report.format} • 
                    ${report.frequency !== 'one_time' ? report.frequency : 'One-time'}
                </div>
                <div class="report-actions">
                    <button class="btn btn-sm btn-primary" onclick="viewReport('${report.id}')">
                        <i class="fas fa-eye"></i> View
                    </button>
                    <button class="btn btn-sm btn-success" onclick="downloadReport('${report.id}')">
                        <i class="fas fa-download"></i> Download
                    </button>
                    <button class="btn btn-sm btn-info" onclick="scheduleReport('${report.id}')">
                        <i class="fas fa-clock"></i> Schedule
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    getReportIcon(type) {
        const icons = {
            'revenue': 'chart-line',
            'bookings': 'calendar-check',
            'customer': 'users',
            'fleet': 'plane',
            'payment': 'credit-card',
            'support': 'headset'
        };
        return icons[type] || 'file-alt';
    }
    
    createReport() {
        // Show modal with report builder
        const modal = new bootstrap.Modal(document.getElementById('reportBuilderModal'));
        modal.show();
    }
    
    deleteReport(reportId) {
        if (confirm('Are you sure you want to delete this report?')) {
            fetch(`/api/v1/analytics/reports/${reportId}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            }).then(() => {
                this.loadReports();
            });
        }
    }
    
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// Schedule Report Modal
class ReportScheduler {
    constructor(reportId) {
        this.reportId = reportId;
        this.showModal();
    }
    
    showModal() {
        const modalHtml = `
            <div class="modal fade" id="scheduleModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Schedule Report</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <form id="scheduleForm">
                                <div class="mb-3">
                                    <label class="form-label">Frequency</label>
                                    <select class="form-control" id="frequency">
                                        <option value="daily">Daily</option>
                                        <option value="weekly">Weekly</option>
                                        <option value="monthly">Monthly</option>
                                        <option value="quarterly">Quarterly</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Recipients</label>
                                    <input type="text" class="form-control" id="recipients" 
                                           placeholder="Enter email addresses (comma-separated)">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Format</label>
                                    <select class="form-control" id="format">
                                        <option value="pdf">PDF</option>
                                        <option value="excel">Excel</option>
                                        <option value="csv">CSV</option>
                                    </select>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" onclick="saveSchedule()">Save Schedule</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById('scheduleModal'));
        modal.show();
        
        document.getElementById('scheduleModal').addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
    }
    
    saveSchedule() {
        const data = {
            frequency: document.getElementById('frequency').value,
            recipients: document.getElementById('recipients').value.split(',').map(e => e.trim()),
            format: document.getElementById('format').value
        };
        
        fetch(`/api/v1/analytics/reports/${this.reportId}/schedule/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            bootstrap.Modal.getInstance(document.getElementById('scheduleModal')).hide();
            alert('Report scheduled successfully');
        });
    }
    
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// Export functions
window.viewReport = function(reportId) {
    window.location.href = `/analytics/reports/${reportId}/`;
};

window.downloadReport = function(reportId) {
    window.location.href = `/analytics/reports/${reportId}/download/`;
};

window.scheduleReport = function(reportId) {
    new ReportScheduler(reportId);
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('reportsList')) {
        window.reportsManager = new ReportsManager();
    }
});