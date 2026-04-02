// FlynJet Notifications System

class NotificationManager {
    constructor(options = {}) {
        this.options = {
            position: options.position || 'top-right',
            duration: options.duration || 5000,
            maxNotifications: options.maxNotifications || 5,
            animation: options.animation !== false,
            sound: options.sound || false,
            ...options
        };
        
        this.container = this.createContainer();
        this.notifications = [];
        this.ws = null;
        
        this.initWebSocket();
    }
    
    createContainer() {
        let container = document.querySelector(`.notification-container.${this.options.position}`);
        
        if (!container) {
            container = document.createElement('div');
            container.className = `notification-container ${this.options.position}`;
            document.body.appendChild(container);
        }
        
        return container;
    }
    
    initWebSocket() {
        if (window.wsManager) {
            this.ws = window.wsManager;
            
            // Listen for notifications
            this.ws.on('notification', (data) => {
                this.show(data.title, data.message, data.type);
            });
        }
    }
    
    show(title, message, type = 'info', options = {}) {
        const notification = {
            id: this.generateId(),
            title: title,
            message: message,
            type: type,
            options: {
                duration: options.duration || this.options.duration,
                dismissible: options.dismissible !== false,
                icon: options.icon !== false,
                ...options
            },
            createdAt: Date.now()
        };
        
        // Remove oldest notification if at limit
        if (this.notifications.length >= this.options.maxNotifications) {
            const oldest = this.notifications.shift();
            this.remove(oldest.id);
        }
        
        this.notifications.push(notification);
        this.render(notification);
        
        // Auto dismiss
        if (notification.options.duration > 0) {
            setTimeout(() => {
                this.dismiss(notification.id);
            }, notification.options.duration);
        }
        
        // Play sound
        if (this.options.sound) {
            this.playSound(type);
        }
        
        return notification.id;
    }
    
    success(title, message, options = {}) {
        return this.show(title, message, 'success', options);
    }
    
    error(title, message, options = {}) {
        return this.show(title, message, 'error', options);
    }
    
    warning(title, message, options = {}) {
        return this.show(title, message, 'warning', options);
    }
    
    info(title, message, options = {}) {
        return this.show(title, message, 'info', options);
    }
    
    render(notification) {
        const el = document.createElement('div');
        el.className = `notification notification-${notification.type}`;
        el.dataset.id = notification.id;
        el.setAttribute('role', 'alert');
        
        let iconHtml = '';
        if (notification.options.icon) {
            const icons = {
                success: '<i class="fas fa-check-circle"></i>',
                error: '<i class="fas fa-exclamation-circle"></i>',
                warning: '<i class="fas fa-exclamation-triangle"></i>',
                info: '<i class="fas fa-info-circle"></i>'
            };
            iconHtml = icons[notification.type] || icons.info;
        }
        
        let dismissHtml = '';
        if (notification.options.dismissible) {
            dismissHtml = '<button class="notification-dismiss">&times;</button>';
        }
        
        el.innerHTML = `
            <div class="notification-icon">${iconHtml}</div>
            <div class="notification-content">
                <div class="notification-title">${notification.title}</div>
                <div class="notification-message">${notification.message}</div>
            </div>
            ${dismissHtml}
            <div class="notification-progress"></div>
        `;
        
        // Add to container
        this.container.appendChild(el);
        
        // Add animation class
        if (this.options.animation) {
            setTimeout(() => el.classList.add('show'), 10);
        } else {
            el.classList.add('show');
        }
        
        // Bind dismiss button
        const dismissBtn = el.querySelector('.notification-dismiss');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', () => this.dismiss(notification.id));
        }
        
        // Bind hover pause
        if (notification.options.duration > 0) {
            el.addEventListener('mouseenter', () => this.pauseDismiss(notification.id));
            el.addEventListener('mouseleave', () => this.resumeDismiss(notification.id));
        }
    }
    
    dismiss(id) {
        const el = this.container.querySelector(`[data-id="${id}"]`);
        if (el) {
            if (this.options.animation) {
                el.classList.remove('show');
                setTimeout(() => {
                    el.remove();
                    this.notifications = this.notifications.filter(n => n.id !== id);
                }, 300);
            } else {
                el.remove();
                this.notifications = this.notifications.filter(n => n.id !== id);
            }
        }
    }
    
    dismissAll() {
        this.notifications.forEach(n => this.dismiss(n.id));
    }
    
    remove(id) {
        const el = this.container.querySelector(`[data-id="${id}"]`);
        if (el) {
            el.remove();
        }
    }
    
    pauseDismiss(id) {
        const notification = this.notifications.find(n => n.id === id);
        if (notification) {
            notification.paused = true;
        }
    }
    
    resumeDismiss(id) {
        const notification = this.notifications.find(n => n.id === id);
        if (notification && notification.paused) {
            delete notification.paused;
            setTimeout(() => {
                this.dismiss(id);
            }, notification.options.duration);
        }
    }
    
    playSound(type) {
        const sounds = {
            success: '/static/sounds/success.mp3',
            error: '/static/sounds/error.mp3',
            warning: '/static/sounds/warning.mp3',
            info: '/static/sounds/info.mp3'
        };
        
        const sound = sounds[type];
        if (sound) {
            const audio = new Audio(sound);
            audio.play().catch(e => console.log('Audio play failed:', e));
        }
    }
    
    generateId() {
        return 'notif_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    update(options = {}) {
        this.options = { ...this.options, ...options };
        
        // Update container position
        this.container.className = `notification-container ${this.options.position}`;
    }
    
    destroy() {
        this.dismissAll();
        this.container.remove();
    }
}

// Notification Center (for displaying history)
class NotificationCenter {
    constructor(options = {}) {
        this.options = {
            title: options.title || 'Notifications',
            maxItems: options.maxItems || 50,
            ...options
        };
        
        this.container = null;
        this.isOpen = false;
        this.notifications = [];
        
        this.init();
    }
    
    init() {
        this.createButton();
        this.createPanel();
        this.loadNotifications();
    }
    
    createButton() {
        const btn = document.createElement('button');
        btn.className = 'notification-center-btn';
        btn.innerHTML = `
            <i class="fas fa-bell"></i>
            <span class="badge">0</span>
        `;
        
        btn.addEventListener('click', () => this.toggle());
        
        document.body.appendChild(btn);
        this.button = btn;
    }
    
    createPanel() {
        const panel = document.createElement('div');
        panel.className = 'notification-center-panel';
        panel.innerHTML = `
            <div class="panel-header">
                <h5>${this.options.title}</h5>
                <button class="close-btn">&times;</button>
            </div>
            <div class="panel-content"></div>
            <div class="panel-footer">
                <button class="mark-all-read">Mark all as read</button>
            </div>
        `;
        
        panel.querySelector('.close-btn').addEventListener('click', () => this.close());
        panel.querySelector('.mark-all-read').addEventListener('click', () => this.markAllRead());
        
        document.body.appendChild(panel);
        this.panel = panel;
        this.content = panel.querySelector('.panel-content');
    }
    
    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }
    
    open() {
        this.panel.classList.add('open');
        this.isOpen = true;
        this.button.classList.add('active');
    }
    
    close() {
        this.panel.classList.remove('open');
        this.isOpen = false;
        this.button.classList.remove('active');
    }
    
    async loadNotifications() {
        try {
            const response = await fetch('/api/v1/notifications/');
            const data = await response.json();
            
            this.notifications = data.notifications;
            this.render();
            this.updateBadge();
        } catch (error) {
            console.error('Failed to load notifications:', error);
        }
    }
    
    render() {
        if (!this.content) return;
        
        if (this.notifications.length === 0) {
            this.content.innerHTML = '<div class="empty-state">No notifications</div>';
            return;
        }
        
        this.content.innerHTML = this.notifications.slice(0, this.options.maxItems).map(n => `
            <div class="notification-item ${n.is_read ? 'read' : 'unread'}" data-id="${n.id}">
                <div class="item-icon">
                    <i class="fas fa-${this.getIcon(n.type)}"></i>
                </div>
                <div class="item-content">
                    <div class="item-title">${n.title}</div>
                    <div class="item-message">${n.message}</div>
                    <div class="item-time">${this.formatTime(n.created_at)}</div>
                </div>
                <button class="item-dismiss" onclick="notificationCenter.dismiss('${n.id}')">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `).join('');
    }
    
    getIcon(type) {
        const icons = {
            'booking': 'calendar-check',
            'payment': 'credit-card',
            'flight': 'plane',
            'promotion': 'gift',
            'system': 'cog',
            'security': 'shield-alt'
        };
        return icons[type] || 'bell';
    }
    
    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} minutes ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)} days ago`;
        
        return date.toLocaleDateString();
    }
    
    updateBadge() {
        const unreadCount = this.notifications.filter(n => !n.is_read).length;
        const badge = this.button.querySelector('.badge');
        
        if (badge) {
            badge.textContent = unreadCount;
            badge.style.display = unreadCount > 0 ? 'inline' : 'none';
        }
    }
    
    async markAsRead(id) {
        try {
            await fetch(`/api/v1/notifications/${id}/read/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            const notification = this.notifications.find(n => n.id === id);
            if (notification) {
                notification.is_read = true;
            }
            
            this.render();
            this.updateBadge();
        } catch (error) {
            console.error('Failed to mark as read:', error);
        }
    }
    
    async markAllRead() {
        try {
            await fetch('/api/v1/notifications/read-all/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            this.notifications.forEach(n => n.is_read = true);
            this.render();
            this.updateBadge();
        } catch (error) {
            console.error('Failed to mark all as read:', error);
        }
    }
    
    async dismiss(id) {
        try {
            await fetch(`/api/v1/notifications/${id}/`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            });
            
            this.notifications = this.notifications.filter(n => n.id !== id);
            this.render();
            this.updateBadge();
        } catch (error) {
            console.error('Failed to dismiss notification:', error);
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
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.notificationManager = new NotificationManager({
        position: 'top-right',
        duration: 5000,
        maxNotifications: 5
    });
    
    if (document.querySelector('[data-notification-center]')) {
        window.notificationCenter = new NotificationCenter({
            title: 'Notifications',
            maxItems: 50
        });
    }
});

// Export for use
window.NotificationManager = NotificationManager;
window.NotificationCenter = NotificationCenter;