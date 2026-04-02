// Flight Tracker JavaScript

class FlightTracker {
    constructor(options = {}) {
        this.flightId = options.flightId;
        this.wsUrl = options.wsUrl;
        this.map = options.map;
        this.updateInterval = options.updateInterval || 5000;
        this.onUpdate = options.onUpdate || null;
        
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.positionHistory = [];
        this.maxHistoryPoints = 100;
        
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.startPolling();
    }
    
    connectWebSocket() {
        if (!this.wsUrl) return;
        
        this.ws = new WebSocket(this.wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.requestUpdate();
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.reconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    reconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log('Max reconnection attempts reached');
            return;
        }
        
        setTimeout(() => {
            this.reconnectAttempts++;
            this.connectWebSocket();
        }, 1000 * Math.pow(2, this.reconnectAttempts));
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'position_update':
                this.updatePosition(data.data);
                break;
            case 'status_update':
                this.updateStatus(data.data);
                break;
            case 'notification':
                this.showNotification(data.data);
                break;
            case 'weather_update':
                this.updateWeather(data.data);
                break;
            case 'eta_update':
                this.updateETA(data.data);
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    updatePosition(position) {
        // Add to history
        this.positionHistory.push({
            lat: position.latitude,
            lng: position.longitude,
            timestamp: new Date(position.timestamp || Date.now())
        });
        
        // Keep history size limited
        if (this.positionHistory.length > this.maxHistoryPoints) {
            this.positionHistory.shift();
        }
        
        // Update map
        if (this.map) {
            this.map.updateFlightPosition(
                [position.longitude, position.latitude],
                position.heading
            );
            
            // Update route
            if (this.positionHistory.length > 1) {
                const coordinates = this.positionHistory.map(p => [p.lng, p.lat]);
                this.map.updateRoute(coordinates);
            }
        }
        
        // Update UI
        this.updatePositionUI(position);
        
        // Callback
        if (this.onUpdate) {
            this.onUpdate(position);
        }
    }
    
    updatePositionUI(position) {
        const elements = {
            altitude: document.getElementById('flight-altitude'),
            speed: document.getElementById('flight-speed'),
            heading: document.getElementById('flight-heading'),
            lat: document.getElementById('flight-latitude'),
            lng: document.getElementById('flight-longitude')
        };
        
        if (elements.altitude) {
            elements.altitude.textContent = this.formatAltitude(position.altitude);
        }
        if (elements.speed) {
            elements.speed.textContent = this.formatSpeed(position.speed);
        }
        if (elements.heading) {
            elements.heading.textContent = this.formatHeading(position.heading);
        }
        if (elements.lat) {
            elements.lat.textContent = position.latitude?.toFixed(4) || '--';
        }
        if (elements.lng) {
            elements.lng.textContent = position.longitude?.toFixed(4) || '--';
        }
    }
    
    updateStatus(status) {
        const statusEl = document.getElementById('flight-status');
        if (statusEl) {
            statusEl.textContent = status;
            statusEl.className = `status-${status.toLowerCase()}`;
        }
    }
    
    updateETA(eta) {
        const etaEl = document.getElementById('flight-eta');
        if (etaEl) {
            etaEl.textContent = new Date(eta).toLocaleTimeString();
        }
        
        const progressEl = document.getElementById('flight-progress');
        if (progressEl && eta.progress) {
            progressEl.style.width = `${eta.progress}%`;
            progressEl.setAttribute('aria-valuenow', eta.progress);
        }
    }
    
    updateWeather(weather) {
        const weatherEl = document.getElementById('flight-weather');
        if (weatherEl) {
            weatherEl.innerHTML = `
                <div class="weather-info">
                    <span class="weather-icon">${this.getWeatherIcon(weather.conditions)}</span>
                    <span class="weather-temp">${weather.temperature}°C</span>
                    <span class="weather-wind">${weather.wind_speed} kts</span>
                </div>
            `;
        }
    }
    
    showNotification(notification) {
        // Create toast notification
        const toast = document.createElement('div');
        toast.className = `toast-notification ${notification.type}`;
        toast.innerHTML = `
            <div class="toast-header">
                <strong>${notification.title}</strong>
                <button type="button" class="close" onclick="this.parentElement.parentElement.remove()">&times;</button>
            </div>
            <div class="toast-body">${notification.message}</div>
        `;
        
        document.body.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.remove();
        }, 5000);
    }
    
    requestUpdate() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'request_update',
                flightId: this.flightId
            }));
        }
    }
    
    startPolling() {
        setInterval(() => {
            this.requestUpdate();
        }, this.updateInterval);
    }
    
    setAlert(alertType, threshold, options = {}) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'set_alert',
                alertType: alertType,
                threshold: threshold,
                notifyEmail: options.notifyEmail || false,
                notifyPush: options.notifyPush || false,
                notifySms: options.notifySms || false
            }));
        }
    }
    
    shareTracking(options = {}) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'share',
                hours: options.hours || 24,
                password: options.password || ''
            }));
        }
    }
    
    formatAltitude(alt) {
        if (alt === null || alt === undefined) return '--';
        if (alt > 30000) {
            return `${(alt / 1000).toFixed(0)}K ft`;
        }
        return `${Math.round(alt)} ft`;
    }
    
    formatSpeed(speed) {
        if (speed === null || speed === undefined) return '--';
        return `${Math.round(speed)} kts`;
    }
    
    formatHeading(heading) {
        if (heading === null || heading === undefined) return '--';
        const directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                           'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
        const index = Math.round(heading / 22.5) % 16;
        return `${Math.round(heading)}° ${directions[index]}`;
    }
    
    getWeatherIcon(conditions) {
        const icons = {
            'clear': '☀️',
            'clouds': '☁️',
            'rain': '🌧️',
            'snow': '❄️',
            'thunderstorm': '⛈️',
            'fog': '🌫️'
        };
        
        if (!conditions) return '☁️';
        
        const condition = conditions.toLowerCase();
        for (const [key, icon] of Object.entries(icons)) {
            if (condition.includes(key)) {
                return icon;
            }
        }
        
        return '☁️';
    }
    
    getPositionHistory() {
        return this.positionHistory;
    }
    
    clearHistory() {
        this.positionHistory = [];
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}