// FlynJet WebSocket Manager

class WebSocketManager {
    constructor(options = {}) {
        this.options = {
            reconnect: true,
            reconnectInterval: 3000,
            maxReconnectAttempts: 10,
            pingInterval: 30000,
            pongTimeout: 5000,
            debug: false,
            ...options
        };
        
        this.connections = new Map();
        this.reconnectAttempts = new Map();
        this.pingIntervals = new Map();
    }
    
    connect(name, url, handlers = {}) {
        if (this.connections.has(name)) {
            this.log(`Connection ${name} already exists`);
            return this.connections.get(name);
        }
        
        this.log(`Connecting to ${name} at ${url}`);
        
        const ws = new WebSocket(url);
        
        ws.onopen = (event) => {
            this.log(`Connected to ${name}`);
            this.reconnectAttempts.set(name, 0);
            this.startPing(name, ws);
            
            if (handlers.onOpen) {
                handlers.onOpen(event);
            }
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.log(`Received message from ${name}:`, data);
                
                if (data.type === 'pong') {
                    this.handlePong(name);
                }
                
                if (handlers.onMessage) {
                    handlers.onMessage(data);
                }
            } catch (error) {
                this.log(`Error parsing message from ${name}:`, error);
            }
        };
        
        ws.onclose = (event) => {
            this.log(`Disconnected from ${name}`);
            this.stopPing(name);
            
            if (handlers.onClose) {
                handlers.onClose(event);
            }
            
            if (this.options.reconnect) {
                this.reconnect(name, url, handlers);
            }
        };
        
        ws.onerror = (event) => {
            this.log(`Error on ${name}:`, event);
            
            if (handlers.onError) {
                handlers.onError(event);
            }
        };
        
        this.connections.set(name, ws);
        return ws;
    }
    
    reconnect(name, url, handlers) {
        const attempts = this.reconnectAttempts.get(name) || 0;
        
        if (attempts >= this.options.maxReconnectAttempts) {
            this.log(`Max reconnection attempts reached for ${name}`);
            return;
        }
        
        const delay = this.options.reconnectInterval * Math.pow(2, attempts);
        
        this.log(`Reconnecting to ${name} in ${delay}ms (attempt ${attempts + 1})`);
        
        setTimeout(() => {
            this.reconnectAttempts.set(name, attempts + 1);
            this.connect(name, url, handlers);
        }, delay);
    }
    
    disconnect(name) {
        const ws = this.connections.get(name);
        if (ws) {
            this.stopPing(name);
            ws.close();
            this.connections.delete(name);
            this.reconnectAttempts.delete(name);
            this.log(`Disconnected from ${name}`);
        }
    }
    
    disconnectAll() {
        this.connections.forEach((ws, name) => {
            this.disconnect(name);
        });
    }
    
    send(name, data) {
        const ws = this.connections.get(name);
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
            this.log(`Sent message to ${name}:`, data);
            return true;
        }
        
        this.log(`Cannot send message to ${name}: connection not open`);
        return false;
    }
    
    startPing(name, ws) {
        const interval = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
                this.log(`Sent ping to ${name}`);
                
                // Set pong timeout
                setTimeout(() => {
                    if (!this.pongReceived) {
                        this.log(`Pong timeout for ${name}`);
                        ws.close();
                    }
                }, this.options.pongTimeout);
            }
        }, this.options.pingInterval);
        
        this.pingIntervals.set(name, interval);
    }
    
    stopPing(name) {
        const interval = this.pingIntervals.get(name);
        if (interval) {
            clearInterval(interval);
            this.pingIntervals.delete(name);
        }
    }
    
    handlePong(name) {
        this.log(`Received pong from ${name}`);
        this.pongReceived = true;
        setTimeout(() => {
            this.pongReceived = false;
        }, 100);
    }
    
    isConnected(name) {
        const ws = this.connections.get(name);
        return ws && ws.readyState === WebSocket.OPEN;
    }
    
    getState(name) {
        const ws = this.connections.get(name);
        if (!ws) return 'disconnected';
        
        switch (ws.readyState) {
            case WebSocket.CONNECTING: return 'connecting';
            case WebSocket.OPEN: return 'open';
            case WebSocket.CLOSING: return 'closing';
            case WebSocket.CLOSED: return 'closed';
            default: return 'unknown';
        }
    }
    
    log(...args) {
        if (this.options.debug) {
            console.log('[WebSocketManager]', ...args);
        }
    }
}

// Tracking WebSocket
class TrackingWebSocket {
    constructor(bookingId, options = {}) {
        this.bookingId = bookingId;
        this.manager = new WebSocketManager({
            debug: options.debug || false,
            ...options
        });
        
        this.handlers = {
            onPosition: options.onPosition || null,
            onStatus: options.onStatus || null,
            onWeather: options.onWeather || null,
            onAlert: options.onAlert || null,
            ...options
        };
        
        this.connect();
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws/tracking/${this.bookingId}/`;
        
        this.manager.connect('tracking', url, {
            onMessage: (data) => this.handleMessage(data),
            onOpen: () => console.log('Tracking WebSocket connected'),
            onClose: () => console.log('Tracking WebSocket disconnected'),
            onError: (error) => console.error('Tracking WebSocket error:', error)
        });
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'position':
                if (this.handlers.onPosition) {
                    this.handlers.onPosition(data.data);
                }
                break;
            case 'status':
                if (this.handlers.onStatus) {
                    this.handlers.onStatus(data.data);
                }
                break;
            case 'weather':
                if (this.handlers.onWeather) {
                    this.handlers.onWeather(data.data);
                }
                break;
            case 'alert':
                if (this.handlers.onAlert) {
                    this.handlers.onAlert(data.data);
                }
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    send(data) {
        this.manager.send('tracking', data);
    }
    
    setAlert(alertType, threshold, options = {}) {
        this.send({
            type: 'set_alert',
            alert_type: alertType,
            threshold: threshold,
            notify_email: options.notifyEmail || false,
            notify_push: options.notifyPush || false,
            notify_sms: options.notifySms || false
        });
    }
    
    disconnect() {
        this.manager.disconnect('tracking');
    }
}

// Chat WebSocket
class ChatWebSocket {
    constructor(conversationId, options = {}) {
        this.conversationId = conversationId;
        this.manager = new WebSocketManager({
            debug: options.debug || false,
            ...options
        });
        
        this.handlers = {
            onMessage: options.onMessage || null,
            onTyping: options.onTyping || null,
            onRead: options.onRead || null,
            onQueue: options.onQueue || null,
            onAgentAssigned: options.onAgentAssigned || null,
            ...options
        };
        
        this.typingTimeout = null;
        this.connect();
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws/chat/${this.conversationId}/`;
        
        this.manager.connect('chat', url, {
            onMessage: (data) => this.handleMessage(data),
            onOpen: () => console.log('Chat WebSocket connected'),
            onClose: () => console.log('Chat WebSocket disconnected'),
            onError: (error) => console.error('Chat WebSocket error:', error)
        });
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'message':
                if (this.handlers.onMessage) {
                    this.handlers.onMessage(data.data);
                }
                break;
            case 'typing':
                if (this.handlers.onTyping) {
                    this.handlers.onTyping(data.is_typing);
                }
                break;
            case 'read_receipt':
                if (this.handlers.onRead) {
                    this.handlers.onRead(data.message_id);
                }
                break;
            case 'queue_update':
                if (this.handlers.onQueue) {
                    this.handlers.onQueue(data.position, data.estimated_wait_time);
                }
                break;
            case 'agent_assigned':
                if (this.handlers.onAgentAssigned) {
                    this.handlers.onAgentAssigned(data.agent);
                }
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    sendMessage(message, attachments = []) {
        this.manager.send('chat', {
            type: 'message',
            message: message,
            attachments: attachments
        });
        
        // Stop typing indicator
        this.sendTyping(false);
    }
    
    sendTyping(isTyping) {
        this.manager.send('chat', {
            type: 'typing',
            is_typing: isTyping
        });
    }
    
    sendReadReceipt(messageId) {
        this.manager.send('chat', {
            type: 'read',
            message_id: messageId
        });
    }
    
    requestHuman(reason = '') {
        this.manager.send('chat', {
            type: 'transfer',
            reason: reason
        });
    }
    
    sendRating(rating, feedback = '') {
        this.manager.send('chat', {
            type: 'rating',
            rating: rating,
            feedback: feedback
        });
    }
    
    handleTyping(isTyping) {
        // Clear existing timeout
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        }
        
        // Send typing indicator
        this.sendTyping(isTyping);
        
        // Set timeout to stop typing
        if (isTyping) {
            this.typingTimeout = setTimeout(() => {
                this.sendTyping(false);
            }, 3000);
        }
    }
    
    disconnect() {
        this.manager.disconnect('chat');
    }
}

// Notifications WebSocket
class NotificationsWebSocket {
    constructor(options = {}) {
        this.manager = new WebSocketManager({
            debug: options.debug || false,
            ...options
        });
        
        this.handlers = {
            onNotification: options.onNotification || null,
            ...options
        };
        
        this.connect();
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws/notifications/`;
        
        this.manager.connect('notifications', url, {
            onMessage: (data) => this.handleMessage(data),
            onOpen: () => console.log('Notifications WebSocket connected'),
            onClose: () => console.log('Notifications WebSocket disconnected'),
            onError: (error) => console.error('Notifications WebSocket error:', error)
        });
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'notification':
                if (this.handlers.onNotification) {
                    this.handlers.onNotification(data.data);
                }
                break;
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    markRead(notificationId) {
        this.manager.send('notifications', {
            type: 'mark_read',
            notification_id: notificationId
        });
    }
    
    markAllRead() {
        this.manager.send('notifications', {
            type: 'mark_all_read'
        });
    }
    
    disconnect() {
        this.manager.disconnect('notifications');
    }
}

// Export for use
window.WebSocketManager = WebSocketManager;
window.TrackingWebSocket = TrackingWebSocket;
window.ChatWebSocket = ChatWebSocket;
window.NotificationsWebSocket = NotificationsWebSocket;