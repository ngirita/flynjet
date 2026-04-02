// Agent Dashboard JavaScript

class AgentDashboard {
    constructor(options = {}) {
        this.wsUrl = options.wsUrl;
        this.agentId = options.agentId;
        this.agentName = options.agentName;
        
        this.ws = null;
        this.currentConversation = null;
        this.queue = [];
        this.activeConversations = [];
        this.quickResponses = this.loadQuickResponses();
        
        this.init();
    }
    
    init() {
        this.connectWebSocket();
        this.setupEventListeners();
        this.loadQueue();
    }
    
    connectWebSocket() {
        this.ws = new WebSocket(this.wsUrl);
        
        this.ws.onopen = () => {
            console.log('Agent WebSocket connected');
            this.updateStatus('online');
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('Agent WebSocket disconnected');
            this.updateStatus('offline');
            
            // Attempt to reconnect
            setTimeout(() => {
                this.connectWebSocket();
            }, 5000);
        };
        
        this.ws.onerror = (error) => {
            console.error('Agent WebSocket error:', error);
        };
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'queue':
                this.updateQueue(data.queue);
                break;
                
            case 'new_queue':
                this.addToQueue(data.data);
                break;
                
            case 'queue_update':
                this.updateQueuePositions(data.queue);
                break;
                
            case 'message':
                if (data.conversation_id === this.currentConversation) {
                    this.displayMessage(data.message, 'received');
                }
                this.updateConversationPreview(data.conversation_id, data.message);
                break;
                
            case 'typing':
                if (data.conversation_id === this.currentConversation) {
                    if (data.is_typing) {
                        this.showTyping();
                    } else {
                        this.hideTyping();
                    }
                }
                break;
                
            case 'conversation_assigned':
                this.addToActive(data.conversation);
                break;
                
            case 'conversation_resolved':
                this.removeFromActive(data.conversation_id);
                break;
                
            default:
                console.log('Unknown message type:', data.type);
        }
    }
    
    loadQueue() {
        fetch('/api/v1/chat/agent/queue/')
            .then(response => response.json())
            .then(data => {
                this.updateQueue(data.queue);
            });
    }
    
    updateQueue(queue) {
        this.queue = queue;
        this.renderQueue();
    }
    
    addToQueue(item) {
        this.queue.push(item);
        this.renderQueue();
        this.showNotification('New customer in queue', 'info');
    }
    
    removeFromQueue(conversationId) {
        this.queue = this.queue.filter(item => item.conversation_id !== conversationId);
        this.renderQueue();
    }
    
    addToActive(conversation) {
        this.activeConversations.push(conversation);
        this.renderActiveConversations();
    }
    
    removeFromActive(conversationId) {
        this.activeConversations = this.activeConversations.filter(
            c => c.id !== conversationId
        );
        this.renderActiveConversations();
    }
    
    acceptConversation(conversationId) {
        fetch(`/api/v1/chat/agent/accept/${conversationId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCsrfToken()
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                this.removeFromQueue(conversationId);
                this.openConversation(conversationId);
            }
        });
    }
    
    openConversation(conversationId) {
        this.currentConversation = conversationId;
        
        // Load conversation history
        fetch(`/api/v1/chat/conversations/${conversationId}/`)
            .then(response => response.json())
            .then(data => {
                this.displayConversation(data);
            });
        
        // Highlight in active list
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-conversation-id="${conversationId}"]`).classList.add('active');
    }
    
    displayConversation(conversation) {
        // Update header
        document.getElementById('currentCustomer').textContent = conversation.user_email;
        document.getElementById('currentSubject').textContent = conversation.subject;
        
        // Display messages
        const messagesDiv = document.getElementById('chatMessages');
        messagesDiv.innerHTML = '';
        
        conversation.messages.forEach(msg => {
            this.displayMessage(msg, msg.sender === this.agentId ? 'sent' : 'received');
        });
        
        // Update customer info
        this.updateCustomerInfo(conversation.user_details);
        
        // Update booking info if available
        if (conversation.booking) {
            this.updateBookingInfo(conversation.booking);
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
        
        const sender = messageData.sender_name || messageData.sender || 'Customer';
        
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
    }
    
    sendMessage() {
        const input = document.getElementById('agentMessageInput');
        const message = input.value.trim();
        
        if (!message || !this.currentConversation) return;
        
        // Display message
        this.displayMessage({
            message: message,
            timestamp: new Date().toISOString(),
            sender_name: this.agentName
        }, 'sent');
        
        // Send via WebSocket
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'message',
                conversation_id: this.currentConversation,
                message: message
            }));
        }
        
        // Clear input
        input.value = '';
        
        // Stop typing
        this.sendTyping(false);
    }
    
    sendTyping(isTyping) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'typing',
                is_typing: isTyping
            }));
        }
    }
    
    sendQuickResponse(response) {
        document.getElementById('agentMessageInput').value = response;
        this.sendMessage();
    }
    
    resolveConversation() {
        if (!this.currentConversation) return;
        
        if (confirm('Mark this conversation as resolved?')) {
            fetch(`/api/v1/chat/conversations/${this.currentConversation}/resolve/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCsrfToken()
                }
            })
            .then(response => response.json())
            .then(data => {
                this.removeFromActive(this.currentConversation);
                this.currentConversation = null;
                this.clearConversationView();
            });
        }
    }
    
    transferConversation() {
        if (!this.currentConversation) return;
        
        const reason = prompt('Reason for transfer:');
        if (reason) {
            fetch(`/api/v1/chat/conversations/${this.currentConversation}/transfer/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCsrfToken()
                },
                body: JSON.stringify({ reason: reason })
            });
        }
    }
    
    updateCustomerInfo(customer) {
        const infoDiv = document.getElementById('customerInfo');
        if (!infoDiv) return;
        
        infoDiv.innerHTML = `
            <div class="info-row">
                <span class="info-label">Name:</span>
                <span class="info-value">${customer.full_name || customer.email}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Email:</span>
                <span class="info-value">${customer.email}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Member since:</span>
                <span class="info-value">${new Date(customer.date_joined).toLocaleDateString()}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Total bookings:</span>
                <span class="info-value">${customer.total_bookings || 0}</span>
            </div>
        `;
    }
    
    updateBookingInfo(booking) {
        const bookingDiv = document.getElementById('bookingInfo');
        if (!bookingDiv) return;
        
        bookingDiv.innerHTML = `
            <div class="booking-summary">
                <div class="booking-route">
                    <span>${booking.departure_airport}</span>
                    <i class="fas fa-arrow-right"></i>
                    <span>${booking.arrival_airport}</span>
                </div>
                <div class="booking-dates">
                    <i class="fas fa-calendar"></i> ${new Date(booking.departure_datetime).toLocaleString()}
                </div>
                <div class="booking-reference">
                    Ref: ${booking.booking_reference}
                </div>
            </div>
        `;
    }
    
    renderQueue() {
        const queueList = document.getElementById('queueList');
        if (!queueList) return;
        
        if (this.queue.length === 0) {
            queueList.innerHTML = '<p class="text-muted text-center py-3">No customers in queue</p>';
            return;
        }
        
        queueList.innerHTML = this.queue.map(item => `
            <div class="queue-item" data-conversation-id="${item.conversation_id}" 
                 onclick="agentDashboard.acceptConversation('${item.conversation_id}')">
                <div class="user-info">
                    <span class="user-name">${item.user}</span>
                    <span class="wait-time">${item.waiting_time}</span>
                </div>
                <div class="subject">${item.subject}</div>
                <div class="message-preview">${item.message_preview || 'No messages yet'}</div>
            </div>
        `).join('');
    }
    
    renderActiveConversations() {
        const activeList = document.getElementById('activeConversations');
        if (!activeList) return;
        
        activeList.innerHTML = this.activeConversations.map(conv => `
            <div class="conversation-item ${conv.id === this.currentConversation ? 'active' : ''}" 
                 data-conversation-id="${conv.id}" onclick="agentDashboard.openConversation('${conv.id}')">
                <div class="user-info">
                    <span class="user-name">${conv.user_email}</span>
                    <span class="time">${new Date(conv.started_at).toLocaleTimeString()}</span>
                </div>
                <div class="subject">${conv.subject}</div>
            </div>
        `).join('');
    }
    
    clearConversationView() {
        document.getElementById('currentCustomer').textContent = 'Select a conversation';
        document.getElementById('currentSubject').textContent = '';
        document.getElementById('chatMessages').innerHTML = '';
        document.getElementById('customerInfo').innerHTML = '';
        document.getElementById('bookingInfo').innerHTML = '';
    }
    
    showTyping() {
        document.getElementById('typingIndicator').style.display = 'flex';
    }
    
    hideTyping() {
        document.getElementById('typingIndicator').style.display = 'none';
    }
    
    showNotification(message, type) {
        // Implementation depends on notification system
        console.log(`[${type}] ${message}`);
    }
    
    updateStatus(status) {
        const toggle = document.getElementById('statusToggle');
        if (toggle) {
            toggle.className = `status-toggle ${status}`;
            toggle.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        }
    }
    
    loadQuickResponses() {
        return [
            "Thank you for contacting FlynJet. How may I assist you today?",
            "I'll check that for you right away.",
            "Is there anything else I can help you with?",
            "Thank you for your patience.",
            "Let me transfer you to a specialist who can better assist with this.",
            "I apologize for the inconvenience.",
            "I've processed your request. You should receive a confirmation email shortly."
        ];
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
    
    escapeHtml(unsafe) {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}