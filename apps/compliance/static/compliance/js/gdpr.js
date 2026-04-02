// GDPR Compliance Utilities

class GDPRManager {
    constructor(options = {}) {
        this.apiEndpoint = options.apiEndpoint || '/api/v1/compliance/';
        this.csrfToken = options.csrfToken || this.getCsrfToken();
    }
    
    async requestDataExport() {
        try {
            const response = await fetch(`${this.apiEndpoint}dsr/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    request_type: 'access',
                    description: 'Request for data export'
                })
            });
            
            const data = await response.json();
            if (response.ok) {
                this.showNotification('Data export request submitted successfully', 'success');
                return data;
            } else {
                throw new Error(data.error || 'Failed to submit request');
            }
        } catch (error) {
            this.showNotification(error.message, 'error');
            throw error;
        }
    }
    
    async requestAccountDeletion() {
        if (!confirm('Are you sure you want to delete your account? This action cannot be undone.')) {
            return;
        }
        
        try {
            const response = await fetch(`${this.apiEndpoint}dsr/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    request_type: 'erasure',
                    description: 'Request for account deletion'
                })
            });
            
            const data = await response.json();
            if (response.ok) {
                this.showNotification('Account deletion request submitted successfully', 'success');
                return data;
            } else {
                throw new Error(data.error || 'Failed to submit request');
            }
        } catch (error) {
            this.showNotification(error.message, 'error');
            throw error;
        }
    }
    
    async getConsentStatus() {
        try {
            const response = await fetch(`${this.apiEndpoint}consent/current/`);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error fetching consent status:', error);
            return {};
        }
    }
    
    async updateConsent(consentType, granted) {
        try {
            const response = await fetch(`${this.apiEndpoint}consent/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    consent_type: consentType,
                    granted: granted,
                    version: '1.0' // Should get current version from server
                })
            });
            
            const data = await response.json();
            if (response.ok) {
                this.showNotification('Consent updated successfully', 'success');
                return data;
            } else {
                throw new Error(data.error || 'Failed to update consent');
            }
        } catch (error) {
            this.showNotification(error.message, 'error');
            throw error;
        }
    }
    
    async withdrawConsent(consentType) {
        return this.updateConsent(consentType, false);
    }
    
    async getDSRStatus(requestNumber) {
        try {
            const response = await fetch(`${this.apiEndpoint}dsr/${requestNumber}/`);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error fetching DSR status:', error);
            return null;
        }
    }
    
    async downloadData(requestNumber) {
        window.location.href = `${this.apiEndpoint}dsr/${requestNumber}/download/`;
    }
    
    redactPII(text) {
        // Redact email addresses
        text = text.replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g, '[EMAIL REDACTED]');
        
        // Redact phone numbers
        text = text.replace(/\b\+?[\d\s-]{10,}\b/g, '[PHONE REDACTED]');
        
        // Redact credit card numbers
        text = text.replace(/\b(?:\d{4}[-\s]?){3}\d{4}\b/g, '[CARD REDACTED]');
        
        return text;
    }
    
    maskEmail(email) {
        if (!email || !email.includes('@')) return email;
        
        const [local, domain] = email.split('@');
        if (local.length <= 2) {
            return local[0] + '*'.repeat(local.length - 1) + '@' + domain;
        }
        return local[0] + '*'.repeat(local.length - 2) + local.slice(-1) + '@' + domain;
    }
    
    maskPhone(phone) {
        if (!phone) return phone;
        const cleaned = phone.replace(/\D/g, '');
        if (cleaned.length >= 4) {
            return '*'.repeat(cleaned.length - 4) + cleaned.slice(-4);
        }
        return '*'.repeat(cleaned.length);
    }
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
                <span>${message}</span>
            </div>
            <button class="notification-close">&times;</button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.remove();
        }, 5000);
        
        // Close button
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.remove();
        });
    }
    
    getCsrfToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return '';
    }
}

// Data Subject Request Form Handler
class DSRFormHandler {
    constructor(formId) {
        this.form = document.getElementById(formId);
        this.gdpr = new GDPRManager();
        
        if (this.form) {
            this.init();
        }
    }
    
    init() {
        this.form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submit();
        });
        
        // Identity verification
        this.setupVerification();
    }
    
    setupVerification() {
        const verifyBtn = this.form.querySelector('[data-verify]');
        if (verifyBtn) {
            verifyBtn.addEventListener('click', () => {
                this.verifyIdentity();
            });
        }
    }
    
    async verifyIdentity() {
        // Show verification modal
        const modal = document.getElementById('verificationModal');
        if (modal) {
            modal.style.display = 'block';
        }
    }
    
    async submit() {
        const formData = new FormData(this.form);
        const data = Object.fromEntries(formData.entries());
        
        try {
            const response = await fetch('/api/v1/compliance/dsr/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.gdpr.csrfToken
                },
                body: JSON.stringify(data)
            });
            
            const result = await response.json();
            
            if (response.ok) {
                this.gdpr.showNotification('Request submitted successfully', 'success');
                setTimeout(() => {
                    window.location.href = `/compliance/dsr/${result.id}/`;
                }, 2000);
            } else {
                throw new Error(result.error || 'Submission failed');
            }
        } catch (error) {
            this.gdpr.showNotification(error.message, 'error');
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    window.gdpr = new GDPRManager();
    
    // Initialize DSR form if present
    if (document.getElementById('dsrForm')) {
        new DSRFormHandler('dsrForm');
    }
    
    // Data export buttons
    document.querySelectorAll('[data-export-data]').forEach(btn => {
        btn.addEventListener('click', () => gdpr.requestDataExport());
    });
    
    // Account deletion buttons
    document.querySelectorAll('[data-delete-account]').forEach(btn => {
        btn.addEventListener('click', () => gdpr.requestAccountDeletion());
    });
});