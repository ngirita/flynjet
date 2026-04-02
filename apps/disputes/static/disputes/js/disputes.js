// Disputes Management JavaScript

class DisputeManager {
    constructor(options = {}) {
        this.disputeId = options.disputeId;
        this.csrfToken = options.csrfToken;
        this.wsUrl = options.wsUrl;
        
        this.init();
    }
    
    init() {
        this.initWebSocket();
        this.bindEvents();
    }
    
    initWebSocket() {
        if (!this.wsUrl) return;
        
        this.ws = new WebSocket(this.wsUrl);
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
    }
    
    bindEvents() {
        // Message form
        const messageForm = document.getElementById('messageForm');
        if (messageForm) {
            messageForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }
        
        // Evidence upload
        const evidenceForm = document.getElementById('evidenceForm');
        if (evidenceForm) {
            evidenceForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.uploadEvidence();
            });
        }
        
        // Resolution actions
        const acceptBtn = document.getElementById('acceptResolution');
        if (acceptBtn) {
            acceptBtn.addEventListener('click', () => this.acceptResolution());
        }
        
        const rejectBtn = document.getElementById('rejectResolution');
        if (rejectBtn) {
            rejectBtn.addEventListener('click', () => this.rejectResolution());
        }
        
        // Escalate button
        const escalateBtn = document.getElementById('escalateBtn');
        if (escalateBtn) {
            escalateBtn.addEventListener('click', () => this.escalateDispute());
        }
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'new_message':
                this.displayMessage(data.message);
                break;
            case 'status_update':
                this.updateStatus(data.status);
                break;
            case 'resolution_proposed':
                this.displayResolution(data.resolution);
                break;
        }
    }
    
    sendMessage() {
        const input = document.getElementById('messageInput');
        const message = input.value.trim();
        
        if (!message) return;
        
        fetch(`/api/v1/disputes/${this.disputeId}/add_message/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                this.displayMessage(data.message);
                input.value = '';
            }
        });
    }
    
    uploadEvidence() {
        const formData = new FormData(document.getElementById('evidenceForm'));
        
        fetch(`/api/v1/disputes/${this.disputeId}/upload_evidence/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.csrfToken
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                this.displayEvidence(data.evidence);
                document.getElementById('evidenceForm').reset();
            }
        });
    }
    
    acceptResolution() {
        if (!confirm('Are you sure you want to accept this resolution?')) return;
        
        fetch(`/api/v1/disputes/${this.disputeId}/accept_resolution/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                location.reload();
            }
        });
    }
    
    rejectResolution() {
        const reason = prompt('Please provide a reason for rejection:');
        if (!reason) return;
        
        fetch(`/api/v1/disputes/${this.disputeId}/reject_resolution/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ reason: reason })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                location.reload();
            }
        });
    }
    
    escalateDispute() {
        const reason = prompt('Reason for escalation:');
        if (!reason) return;
        
        fetch(`/api/v1/disputes/${this.disputeId}/escalate/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ reason: reason })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Dispute escalated');
                location.reload();
            }
        });
    }
    
    displayMessage(message) {
        const container = document.getElementById('messageThread');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.is_staff ? 'staff' : 'customer'}`;
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                ${message.sender_name ? message.sender_name.charAt(0) : 'U'}
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-sender">${message.sender_name || 'User'}</span>
                    <span class="message-time">${new Date(message.timestamp).toLocaleString()}</span>
                </div>
                <div class="message-body">${this.escapeHtml(message.message)}</div>
                ${message.attachment ? `
                    <div class="message-attachment">
                        <i class="fas fa-paperclip"></i>
                        <a href="${message.attachment}" target="_blank">View Attachment</a>
                    </div>
                ` : ''}
            </div>
        `;
        
        container.appendChild(messageDiv);
        container.scrollTop = container.scrollHeight;
    }
    
    displayEvidence(evidence) {
        const container = document.getElementById('evidenceGrid');
        const evidenceDiv = document.createElement('div');
        evidenceDiv.className = 'evidence-item';
        
        evidenceDiv.innerHTML = `
            <div class="evidence-icon">
                <i class="fas fa-${this.getFileIcon(evidence.type)}"></i>
            </div>
            <div class="evidence-name">${evidence.name}</div>
            <div class="evidence-meta">${evidence.size} • ${evidence.type}</div>
            <div class="evidence-actions">
                <a href="${evidence.url}" class="btn btn-sm btn-primary" target="_blank">
                    <i class="fas fa-eye"></i>
                </a>
                <a href="${evidence.url}" class="btn btn-sm btn-success" download>
                    <i class="fas fa-download"></i>
                </a>
            </div>
        `;
        
        container.appendChild(evidenceDiv);
    }
    
    displayResolution(resolution) {
        const container = document.getElementById('resolutionSection');
        const resolutionDiv = document.createElement('div');
        resolutionDiv.className = 'resolution-proposal';
        
        resolutionDiv.innerHTML = `
            <h5>Resolution Proposed</h5>
            <p><strong>Type:</strong> ${resolution.type}</p>
            <p><strong>Description:</strong> ${resolution.description}</p>
            ${resolution.refund_amount ? `<p><strong>Refund Amount:</strong> $${resolution.refund_amount}</p>` : ''}
            <div class="resolution-actions">
                <button class="btn btn-success" onclick="disputeManager.acceptResolution()">Accept</button>
                <button class="btn btn-danger" onclick="disputeManager.rejectResolution()">Reject</button>
            </div>
        `;
        
        container.appendChild(resolutionDiv);
    }
    
    updateStatus(status) {
        const badge = document.getElementById('statusBadge');
        if (badge) {
            badge.className = `status-badge status-${status}`;
            badge.textContent = status.replace('_', ' ').toUpperCase();
        }
    }
    
    getFileIcon(type) {
        const icons = {
            'document': 'file-alt',
            'image': 'image',
            'video': 'video',
            'audio': 'music',
            'receipt': 'receipt',
            'contract': 'file-contract'
        };
        return icons[type] || 'file';
    }
    
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

// Admin Dispute Management
class AdminDisputeManager extends DisputeManager {
    constructor(options = {}) {
        super(options);
    }
    
    assignToAgent(agentId) {
        fetch(`/api/v1/disputes/${this.disputeId}/assign/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ agent_id: agentId })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'assigned') {
                alert(`Dispute assigned to ${data.agent}`);
                location.reload();
            }
        });
    }
    
    proposeResolution(data) {
        fetch(`/api/v1/disputes/${this.disputeId}/resolve/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Resolution proposed');
                location.reload();
            }
        });
    }
}

// Dispute Statistics
class DisputeStats {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.init();
    }
    
    init() {
        this.loadStats();
    }
    
    loadStats() {
        fetch('/api/v1/disputes/stats/')
            .then(response => response.json())
            .then(data => {
                this.renderStats(data);
            });
    }
    
    renderStats(data) {
        this.container.innerHTML = `
            <div class="stat-card">
                <div class="stat-value">${data.total}</div>
                <div class="stat-label">Total Disputes</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-value">${data.pending}</div>
                <div class="stat-label">Pending</div>
            </div>
            <div class="stat-card success">
                <div class="stat-value">${data.resolved}</div>
                <div class="stat-label">Resolved</div>
            </div>
            <div class="stat-card danger">
                <div class="stat-value">$${data.total_amount}</div>
                <div class="stat-label">Total Amount</div>
            </div>
        `;
    }
}

// Export
window.DisputeManager = DisputeManager;
window.AdminDisputeManager = AdminDisputeManager;
window.DisputeStats = DisputeStats;