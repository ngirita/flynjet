// Document Verification Utilities

class DocumentVerifier {
    constructor(options = {}) {
        this.documentId = options.documentId;
        this.verificationToken = options.verificationToken;
    }
    
    verify() {
        return fetch(`/api/v1/documents/${this.documentId}/verify/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                token: this.verificationToken
            })
        })
        .then(response => response.json())
        .then(data => {
            this.displayResult(data);
            return data;
        });
    }
    
    verifyByHash(documentHash) {
        return fetch(`/api/v1/documents/verify-hash/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                document_id: this.documentId,
                hash: documentHash
            })
        })
        .then(response => response.json());
    }
    
    displayResult(result) {
        const container = document.getElementById('verification-result');
        if (!container) return;
        
        if (result.valid) {
            container.innerHTML = `
                <div class="verification-badge valid">
                    <i class="fas fa-check-circle"></i>
                    <h3>Document Verified</h3>
                    <p>This document is authentic and has not been tampered with.</p>
                    <p class="small">Verified on: ${new Date().toLocaleString()}</p>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="verification-badge invalid">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Verification Failed</h3>
                    <p>This document could not be verified. It may have been altered.</p>
                </div>
            `;
        }
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
    
    scanQRCode(imageData) {
        // QR code scanning logic would go here
        // This would typically use a library like jsQR
        return new Promise((resolve, reject) => {
            // Placeholder implementation
            console.log('QR code scanning:', imageData);
            resolve({ data: 'sample-data' });
        });
    }
    
    generateQRCode(elementId, data) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        // Use QRCode library if available
        if (typeof QRCode !== 'undefined') {
            new QRCode(element, {
                text: data,
                width: 200,
                height: 200
            });
        } else {
            console.warn('QRCode library not available');
        }
    }
}

// Blockchain Verification (for future implementation)
class BlockchainVerifier {
    constructor() {
        this.web3 = null;
        this.contract = null;
    }
    
    async connect() {
        if (typeof window.ethereum !== 'undefined') {
            this.web3 = new Web3(window.ethereum);
            await window.ethereum.enable();
            return true;
        }
        return false;
    }
    
    async verifyOnChain(documentHash) {
        if (!this.web3) return false;
        
        // Contract interaction would go here
        // This is a placeholder
        return {
            verified: true,
            timestamp: Date.now(),
            blockNumber: 12345678
        };
    }
    
    async getVerificationHistory(documentHash) {
        // Retrieve verification history from blockchain
        return [];
    }
}

// Export
window.DocumentVerifier = DocumentVerifier;
window.BlockchainVerifier = BlockchainVerifier;