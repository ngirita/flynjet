// Cookie Consent Manager

class CookieConsentManager {
    constructor(options = {}) {
        this.options = {
            bannerId: options.bannerId || 'cookieConsent',
            settingsPanelId: options.settingsPanelId || 'cookieSettings',
            cookieName: options.cookieName || 'cookie_consent',
            expiryDays: options.expiryDays || 365,
            onAccept: options.onAccept || null,
            onReject: options.onReject || null,
            onSave: options.onSave || null,
            ...options
        };
        
        this.categories = {
            essential: true, // Always enabled
            functional: false,
            analytics: false,
            marketing: false
        };
        
        this.init();
    }
    
    init() {
        this.loadConsent();
        this.bindEvents();
        this.showBannerIfNeeded();
    }
    
    loadConsent() {
        const saved = this.getCookie(this.options.cookieName);
        if (saved) {
            try {
                const settings = JSON.parse(saved);
                this.categories = { ...this.categories, ...settings };
            } catch (e) {
                console.error('Error parsing cookie consent:', e);
            }
        }
    }
    
    saveConsent() {
        const consentData = JSON.stringify(this.categories);
        this.setCookie(this.options.cookieName, consentData, this.options.expiryDays);
        
        // Update scripts based on consent
        this.updateScripts();
        
        // Hide banner
        const banner = document.getElementById(this.options.bannerId);
        if (banner) {
            banner.classList.remove('show');
        }
        
        // Callback
        if (this.options.onSave) {
            this.options.onSave(this.categories);
        }
    }
    
    acceptAll() {
        this.categories = {
            essential: true,
            functional: true,
            analytics: true,
            marketing: true
        };
        this.saveConsent();
        
        if (this.options.onAccept) {
            this.options.onAccept(this.categories);
        }
    }
    
    rejectAll() {
        this.categories = {
            essential: true,
            functional: false,
            analytics: false,
            marketing: false
        };
        this.saveConsent();
        
        if (this.options.onReject) {
            this.options.onReject(this.categories);
        }
    }
    
    updateCategory(category, enabled) {
        if (category !== 'essential') { // Can't disable essential
            this.categories[category] = enabled;
        }
    }
    
    showSettings() {
        const panel = document.getElementById(this.options.settingsPanelId);
        if (panel) {
            panel.style.display = 'block';
            this.updateSettingsUI();
        }
    }
    
    hideSettings() {
        const panel = document.getElementById(this.options.settingsPanelId);
        if (panel) {
            panel.style.display = 'none';
        }
    }
    
    updateSettingsUI() {
        // Update toggle states
        for (const [category, enabled] of Object.entries(this.categories)) {
            const toggle = document.querySelector(`[data-cookie-category="${category}"]`);
            if (toggle) {
                toggle.checked = enabled;
                if (category === 'essential') {
                    toggle.disabled = true;
                }
            }
        }
    }
    
    updateScripts() {
        // Load/unload scripts based on consent
        if (this.categories.analytics) {
            this.loadScript('analytics');
        } else {
            this.unloadScript('analytics');
        }
        
        if (this.categories.marketing) {
            this.loadScript('marketing');
        } else {
            this.unloadScript('marketing');
        }
    }
    
    loadScript(type) {
        // Load third-party scripts based on type
        const scripts = {
            analytics: [
                'https://www.googletagmanager.com/gtag/js?id=UA-XXXXX-Y'
            ],
            marketing: [
                'https://connect.facebook.net/en_US/fbevents.js'
            ]
        };
        
        if (scripts[type]) {
            scripts[type].forEach(src => {
                if (!document.querySelector(`script[src="${src}"]`)) {
                    const script = document.createElement('script');
                    script.src = src;
                    script.async = true;
                    document.head.appendChild(script);
                }
            });
        }
    }
    
    unloadScript(type) {
        // Remove scripts (Note: scripts can't truly be unloaded, but we can disable them)
        // This is a simplified version
    }
    
    showBannerIfNeeded() {
        const hasConsent = this.getCookie(this.options.cookieName);
        const banner = document.getElementById(this.options.bannerId);
        
        if (!hasConsent && banner) {
            banner.classList.add('show');
        }
    }
    
    setCookie(name, value, days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        const expires = `expires=${date.toUTCString()}`;
        document.cookie = `${name}=${value};${expires};path=/;SameSite=Lax`;
    }
    
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return null;
    }
    
    bindEvents() {
        // Accept all button
        const acceptBtn = document.getElementById('acceptCookies');
        if (acceptBtn) {
            acceptBtn.addEventListener('click', () => this.acceptAll());
        }
        
        // Reject all button
        const rejectBtn = document.getElementById('rejectCookies');
        if (rejectBtn) {
            rejectBtn.addEventListener('click', () => this.rejectAll());
        }
        
        // Settings button
        const settingsBtn = document.getElementById('cookieSettings');
        if (settingsBtn) {
            settingsBtn.addEventListener('click', () => this.showSettings());
        }
        
        // Save settings button
        const saveBtn = document.getElementById('saveCookieSettings');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                // Update categories from UI
                document.querySelectorAll('[data-cookie-category]').forEach(toggle => {
                    const category = toggle.dataset.cookieCategory;
                    this.updateCategory(category, toggle.checked);
                });
                this.saveConsent();
                this.hideSettings();
            });
        }
        
        // Category toggles
        document.querySelectorAll('[data-cookie-category]').forEach(toggle => {
            toggle.addEventListener('change', (e) => {
                const category = e.target.dataset.cookieCategory;
                this.updateCategory(category, e.target.checked);
            });
        });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    window.cookieManager = new CookieConsentManager({
        bannerId: 'cookieConsent',
        settingsPanelId: 'cookieSettings'
    });
});