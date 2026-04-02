// WebSocket Manager for Tracking

class TrackingWebSocket {
    constructor(url, options = {}) {
        this.url = url;
        this.options = {
            reconnect: true,
            reconnectInterval: 3000,
            maxReconnectAttempts: 10,
            onOpen: null,
            onMessage: null,
            onClose: null,
            onError: null,
            ...options
        };
        
        this.ws = null;
        this.reconnectAttempts = 0;
        self = this;
        
        this.connect();
    }
    
    connect() {
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = (event) => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                
                // Send authentication
                this.send({
                    type: 'auth',
                    token: this.getAuthToken()
                });
                
                if (this.options.onOpen) {
                    this.options.onOpen(event);
                }
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                // Handle ping/pong
                if (data.type === 'ping') {
                    this.send({ type: 'pong' });
                    return;
                }
                
                if (this.options.onMessage) {
                    this.options.onMessage(data);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('WebSocket closed');
                
                if (this.options.onClose) {
                    this.options.onClose(event);
                }
                
                if (this.options.reconnect) {
                    this.reconnect();
                }
            };
            
            this.ws.onerror = (event) => {
                console.error('WebSocket error:', event);
                
                if (this.options.onError) {
                    this.options.onError(event);
                }
            };
            
        } catch (error) {
            console.error('WebSocket connection error:', error);
        }
    }
    
    reconnect() {
        if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
            console.log('Max reconnection attempts reached');
            return;
        }
        
        setTimeout(() => {
            console.log(`Reconnecting... Attempt ${this.reconnectAttempts + 1}`);
            this.reconnectAttempts++;
            this.connect();
        }, this.options.reconnectInterval);
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        }
        return false;
    }
    
    getAuthToken() {
        // Get CSRF token from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return '';
    }
    
    close() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
    
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
    
    getState() {
        if (!this.ws) return 'closed';
        
        switch (this.ws.readyState) {
            case WebSocket.CONNECTING: return 'connecting';
            case WebSocket.OPEN: return 'open';
            case WebSocket.CLOSING: return 'closing';
            case WebSocket.CLOSED: return 'closed';
            default: return 'unknown';
        }
    }
}

// Reconnection Manager
class ReconnectionManager {
    constructor() {
        this.websockets = new Map();
        this.checkInterval = 30000; // 30 seconds
        this.startMonitoring();
    }
    
    register(id, ws) {
        this.websockets.set(id, {
            ws: ws,
            lastPing: Date.now(),
            missedPongs: 0
        });
    }
    
    unregister(id) {
        this.websockets.delete(id);
    }
    
    startMonitoring() {
        setInterval(() => {
            this.checkConnections();
        }, this.checkInterval);
    }
    
    checkConnections() {
        const now = Date.now();
        
        for (const [id, data] of this.websockets) {
            // Check if connection is stale (no ping for 2 minutes)
            if (now - data.lastPing > 120000) {
                console.log(`WebSocket ${id} is stale, reconnecting...`);
                data.ws.close();
                data.ws.connect();
            }
        }
    }
    
    recordPing(id) {
        const data = this.websockets.get(id);
        if (data) {
            data.lastPing = Date.now();
            data.missedPongs = 0;
        }
    }
}

// Connection Pool for multiple tracking connections
class TrackingConnectionPool {
    constructor() {
        this.connections = new Map();
        this.maxConnections = 10;
    }
    
    getConnection(flightId) {
        return this.connections.get(flightId);
    }
    
    addConnection(flightId, ws) {
        if (this.connections.size >= this.maxConnections) {
            // Remove oldest connection
            const oldest = this.connections.keys().next().value;
            this.removeConnection(oldest);
        }
        
        this.connections.set(flightId, ws);
    }
    
    removeConnection(flightId) {
        const ws = this.connections.get(flightId);
        if (ws) {
            ws.close();
            this.connections.delete(flightId);
        }
    }
    
    closeAll() {
        for (const [flightId, ws] of this.connections) {
            ws.close();
        }
        this.connections.clear();
    }
}

// Export instances
const wsManager = new ReconnectionManager();
const connectionPool = new TrackingConnectionPool();