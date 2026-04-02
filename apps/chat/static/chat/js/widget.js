// Chat Widget JavaScript

class ChatWidget {
    constructor(options = {}) {
        this.wsUrl = options.wsUrl;
        this.conversationId = options.conversationId;
        this.userName = options.userName || 'Guest';
        this.userEmail = options.userEmail || '';
        this.onMessage = options.onMessage || null;
        
        this.ws = null;
        this.messages = [];
        this.isOpen = false;
        this.isTyping = false;
        this.typingTimeout = null;
        this.unreadCount = 0;
        
        this.init();
    }
    
    init() {
        this.createWidget();
        this.setupEventListeners();
        this.connectWebSocket();
    }
    
    createWidget() {
        const widget = document.createElement('div');
        widget.className = 'chat-widget';
        widget.innerHTML = `
            <div class="chat-button" onclick="chatWidget.toggle()">
                <i class="fas fa-comment"></i>
                <span class="notification-badge" id="chatNotification" style="display: none;">0</span>
            </div>
            <div class="chat-window" id="chatWindow">
                <div class="chat-header">
                    <div>
                        <h5>FlynJet Support</h5>
                        <div class="status">
                            <span class="status-dot online" id="chatStatus"></span>
                            <span id="statusText">Online</span>
                        </div>
                    </div>
                    <button class="close-chat" onclick="chatWidget.toggle()">&times;</button>
                </div>
                <div class="chat-messages" id="chatMessages"></div>
                <div class="chat-input-area">
                    <div class="suggestions" id="suggestions"></div>
                    <div class="input-group">
                        <input type="text" id="chatInput" placeholder="Type your message..." 
                               onkeypress="chatWidget.handleKeyPress(event)">
                        <button onclick="chatWidget.sendMessage()" id="sendButton">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                    <div class="typing-indicator" id="typingIndicator" style="display: none;">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(widget);
    }
    
    setupEventListeners() {
        // Add emoji picker (optional)
        // Add file upload (optional)
    }
    
    connectWebSocket() {
        if (!this.wsUrl) return;
        
        this.ws = new WebSocket(this.wsUrl);
        
        this.ws.onopen = () => {
            console.log('Chat WebSocket connected');
            this.updateStatus('online');
            this.sendSystemMessage('Connected to support');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('Chat WebSocket disconnected');
            this.updateStatus('offline');
            this.sendSystemMessage('Disconnected from support');
            
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
                this.connectWebSocket();
            }, 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('Chat WebSocket error:', error);
            this.updateStatus('error');
        };
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'history':
                this.displayHistory(data.messages);
                break;
                
            case 'message':
                this.displayMessage(data.data, 'received');
                this.hideTyping();
                this.incrementUnread();
                break;
                
            case 'typing':
                if (data.isTyping) {
                    this.showTyping();
                } else {
                    this.hideTyping();
                }
                break;
                
            case 'suggestions':
                this.displaySuggestions(data.suggestions);
                break;
                
            case 'system':
                this.displaySystemMessage(data.message);
                break;
                
            case 'queue_update':
                this.displayQueueUpdate(data.position);
                break;
                
            case 'agent_assigned':
                this.displayAgentAssigned(data.agent);
                break;
                
            default:
                console.log('Unknown message type:', data.type);
        }
        
        if (this.onMessage) {
            this.onMessage(data);
        }
    }
    
    sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Display message immediately
        this.displayMessage({
            message: message,
            timestamp: new Date().toISOString(),
            sender: 'You'
        }, 'sent');
        
        // Send via WebSocket
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'message',
                message: message
            }));
        }
        
        // Clear input
        input.value = '';
        
        // Stop typing indicator
        this.sendTyping(false);
    }
    
    sendTyping(isTyping) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'typing',
                isTyping: isTyping
            }));
        }
    }
    
    sendReadReceipt(messageId) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'read',
                messageId: messageId
            }));
        }
    }
    
    sendRating(rating, feedback = '') {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'rating',
                rating: rating,
                feedback: feedback
            }));
        }
    }
    
    requestHuman() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'transfer'
            }));
        }
    }
    
    displayMessage(messageData, type) {
        const messages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        
        const time = new Date(messageData.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit'
        });
        
        const sender = messageData.sender_name || messageData.sender || 'Support';
        
        messageDiv.innerHTML = `
            ${type === 'received' ? `
                <div class="message-avatar">${sender.charAt(0)}</div>
            ` : ''}
            <div class="message-content">
                <div class="message-sender">${sender}</div>
                <div>${this.escapeHtml(messageData.message)}</div>
                <div class="message-time">${time}</div>
            </div>
        `;
        
        messages.appendChild(messageDiv);
        messages.scrollTop = messages.scrollHeight;
        
        // Send read receipt for received messages
        if (type === 'received' && messageData.id) {
            this.sendReadReceipt(messageData.id);
        }
    }
    
    displayHistory(messages) {
        const messagesDiv = document.getElementById('chatMessages');
        messagesDiv.innerHTML = '';
        
        messages.forEach(msg => {
            const type = msg.is_ai ? 'received' : (msg.is_agent ? 'received' : 'sent');
            this.displayMessage(msg, type);
        });
    }
    
    displaySystemMessage(text) {
        const messages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message system';
        messageDiv.innerHTML = `
            <div class="message-content">
                <div>${this.escapeHtml(text)}</div>
            </div>
        `;
        messages.appendChild(messageDiv);
        messages.scrollTop = messages.scrollHeight;
    }
    
    displaySuggestions(suggestions) {
        const container = document.getElementById('suggestions');
        container.innerHTML = '';
        
        suggestions.forEach(suggestion => {
            const btn = document.createElement('button');
            btn.className = 'suggestion-btn';
            btn.textContent = suggestion;
            btn.onclick = () => {
                document.getElementById('chatInput').value = suggestion;
                this.sendMessage();
            };
            container.appendChild(btn);
        });
    }
    
    displayQueueUpdate(position) {
        this.displaySystemMessage(`You are #${position} in the queue. An agent will be with you shortly.`);
    }
    
    displayAgentAssigned(agentName) {
        this.displaySystemMessage(`Agent ${agentName} has joined the conversation.`);
        this.updateStatus('online');
    }
    
    showTyping() {
        document.getElementById('typingIndicator').style.display = 'flex';
    }
    
    hideTyping() {
        document.getElementById('typingIndicator').style.display = 'none';
    }
    
    updateStatus(status) {
        const dot = document.getElementById('chatStatus');
        const text = document.getElementById('statusText');
        
        dot.className = `status-dot ${status}`;
        
        switch(status) {
            case 'online':
                text.textContent = 'Online';
                break;
            case 'offline':
                text.textContent = 'Offline';
                break;
            case 'away':
                text.textContent = 'Away';
                break;
            case 'error':
                text.textContent = 'Connection Error';
                break;
        }
    }
    
    incrementUnread() {
        if (!this.isOpen) {
            this.unreadCount++;
            const badge = document.getElementById('chatNotification');
            badge.textContent = this.unreadCount;
            badge.style.display = 'flex';
        }
    }
    
    resetUnread() {
        this.unreadCount = 0;
        const badge = document.getElementById('chatNotification');
        badge.style.display = 'none';
    }
    
    toggle() {
        const window = document.getElementById('chatWindow');
        this.isOpen = !this.isOpen;
        
        if (this.isOpen) {
            window.classList.add('active');
            this.resetUnread();
        } else {
            window.classList.remove('active');
        }
    }
    
    handleKeyPress(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage();
        } else {
            // Send typing indicator
            if (!this.isTyping) {
                this.isTyping = true;
                this.sendTyping(true);
            }
            
            // Clear typing timeout
            clearTimeout(this.typingTimeout);
            
            // Set new timeout
            this.typingTimeout = setTimeout(() => {
                this.isTyping = false;
                this.sendTyping(false);
            }, 2000);
        }
    }
    
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
    
    disconnect() {
        if (this.ws) {
            this.ws.close();
        }
    }
}