// Marketing Campaigns JavaScript

class CampaignManager {
    constructor(options = {}) {
        this.campaignId = options.campaignId;
        this.csrfToken = options.csrfToken;
    }
    
    launchCampaign() {
        if (!confirm('Launch this campaign?')) return;
        
        fetch(`/api/v1/marketing/campaigns/${this.campaignId}/launch/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Campaign launched successfully');
                location.reload();
            }
        });
    }
    
    pauseCampaign() {
        if (!confirm('Pause this campaign?')) return;
        
        fetch(`/api/v1/marketing/campaigns/${this.campaignId}/pause/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Campaign paused');
                location.reload();
            }
        });
    }
    
    duplicateCampaign() {
        fetch(`/api/v1/marketing/campaigns/${this.campaignId}/duplicate/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Campaign duplicated');
                window.location.href = `/marketing/campaigns/${data.campaign_id}/edit/`;
            }
        });
    }
    
    getMetrics() {
        fetch(`/api/v1/marketing/campaigns/${this.campaignId}/metrics/`)
            .then(response => response.json())
            .then(data => {
                this.renderMetrics(data);
            });
    }
    
    renderMetrics(data) {
        const container = document.getElementById('campaignMetrics');
        if (!container) return;
        
        container.innerHTML = `
            <div class="row">
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${data.opens}</div>
                        <div class="metric-label">Opens</div>
                        <div class="metric-rate">${data.open_rate.toFixed(1)}%</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${data.clicks}</div>
                        <div class="metric-label">Clicks</div>
                        <div class="metric-rate">${data.click_rate.toFixed(1)}%</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">${data.conversions}</div>
                        <div class="metric-label">Conversions</div>
                        <div class="metric-rate">${data.conversion_rate.toFixed(1)}%</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="metric-card">
                        <div class="metric-value">$${data.revenue}</div>
                        <div class="metric-label">Revenue</div>
                        <div class="metric-rate">ROI: ${data.roi.toFixed(1)}%</div>
                    </div>
                </div>
            </div>
        `;
    }
}

class LoyaltyManager {
    constructor(options = {}) {
        this.userId = options.userId;
        this.csrfToken = options.csrfToken;
    }
    
    loadPointsHistory() {
        fetch(`/api/v1/marketing/loyalty/transactions/`)
            .then(response => response.json())
            .then(data => {
                this.renderHistory(data);
            });
    }
    
    renderHistory(transactions) {
        const container = document.getElementById('pointsHistory');
        if (!container) return;
        
        let html = '<table class="table"><thead><tr><th>Date</th><th>Type</th><th>Points</th><th>Source</th></tr></thead><tbody>';
        
        transactions.forEach(t => {
            html += `
                <tr>
                    <td>${new Date(t.created_at).toLocaleDateString()}</td>
                    <td><span class="badge bg-${t.transaction_type === 'earn' ? 'success' : 'warning'}">${t.transaction_type}</span></td>
                    <td class="${t.transaction_type === 'earn' ? 'text-success' : 'text-danger'}">${t.transaction_type === 'earn' ? '+' : '-'}${t.points}</td>
                    <td>${t.source}</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }
}

class ReferralManager {
    constructor(options = {}) {
        this.csrfToken = options.csrfToken;
    }
    
    shareViaEmail() {
        const email = prompt('Enter friend\'s email:');
        if (!email) return;
        
        fetch('/api/v1/marketing/referrals/share/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify({ email: email })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'sent') {
                alert(`Invitation sent to ${email}`);
            }
        });
    }
    
    copyReferralLink() {
        const link = document.getElementById('referralLink').textContent;
        navigator.clipboard.writeText(link).then(() => {
            alert('Referral link copied to clipboard!');
        });
    }
    
    loadReferrals() {
        fetch('/api/v1/marketing/referrals/')
            .then(response => response.json())
            .then(data => {
                this.renderReferrals(data);
            });
    }
    
    renderReferrals(referrals) {
        const container = document.getElementById('referralsList');
        if (!container) return;
        
        let html = '<table class="table"><thead><tr><th>Email</th><th>Status</th><th>Date</th><th>Reward</th></tr></thead><tbody>';
        
        referrals.forEach(r => {
            html += `
                <tr>
                    <td>${r.referred_email}</td>
                    <td><span class="badge bg-${r.status === 'completed' ? 'success' : 'warning'}">${r.status}</span></td>
                    <td>${new Date(r.created_at).toLocaleDateString()}</td>
                    <td>${r.referrer_reward} points</td>
                </tr>
            `;
        });
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }
}

// Export
window.CampaignManager = CampaignManager;
window.LoyaltyManager = LoyaltyManager;
window.ReferralManager = ReferralManager;