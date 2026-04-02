// Chat WebSocket Manager

class ChatWebSocket {
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
        this.messageQueue = [];
        this.pingInterval = null;
        
        this.connect();
    }
    
    connect() {
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = (event) => {
                console.log('Chat WebSocket connected');
                this.reconnectAttempts = 0;
                
                // Send queued messages
                while (this.messageQueue.length > 0) {
                    const message = this.messageQueue.shift();
                    this.send(message);
                }
                
                // Start ping interval
                this.startPing();
                
                if (this.options.onOpen) {
                    this.options.onOpen(event);
                }
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                
                // Handle different message types
                if (data.type === 'pong') {
                    console.log('Received pong');
                    return;
                }
                
                if (this.options.onMessage) {
                    this.options.onMessage(data);
                }
            };
            
            this.ws.onclose = (event) => {
                console.log('Chat WebSocket closed');
                this.stopPing();
                
                if (this.options.onClose) {
                    this.options.onClose(event);
                }
                
                if (this.options.reconnect) {
                    this.reconnect();
                }
            };
            
            this.ws.onerror = (event) => {
                console.error('Chat WebSocket error:', event);
                
                if (this.options.onError) {
                    this.options.onError(event);
                }
            };
            
        } catch (error) {
            console.error('Chat WebSocket connection error:', error);
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
        }, this.options.reconnectInterval * Math.pow(2, this.reconnectAttempts));
    }
    
    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
            return true;
        } else {
            // Queue message for later
            this.messageQueue.push(data);
            return false;
        }
    }
    
    startPing() {
        this.pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000); // Send ping every 30 seconds
    }
    
    stopPing() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }
    
    close() {
        this.stopPing();
        this.options.reconnect = false;
        if (this.ws) {
            this.ws.close();
        }
    }
    
    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Export for use
window.ChatWebSocket = ChatWebSocket;