const WebSocket = require('ws');
const redis = require('redis');
const jwt = require('jsonwebtoken');
const http = require('http');

// Configuration
const PORT = process.env.PORT || 8001;
const JWT_SECRET = process.env.JWT_SECRET || 'your-secret-key';

// Create server
const server = http.createServer();
const wss = new WebSocket.Server({ server });

// Redis clients
const redisPub = redis.createClient({ url: 'redis://redis:6379' });
const redisSub = redis.createClient({ url: 'redis://redis:6379' });

// Connected clients
const clients = new Map();

// Authentication middleware
function authenticate(connection, req) {
    const token = new URL(req.url, `http://${req.headers.host}`).searchParams.get('token');
    
    if (!token) {
        connection.close(1008, 'Authentication required');
        return false;
    }
    
    try {
        const decoded = jwt.verify(token, JWT_SECRET);
        connection.userId = decoded.user_id;
        connection.userType = decoded.user_type;
        return true;
    } catch (error) {
        connection.close(1008, 'Invalid token');
        return false;
    }
}

// WebSocket connection handler
wss.on('connection', (ws, req) => {
    // Authenticate
    if (!authenticate(ws, req)) {
        return;
    }
    
    // Parse URL to get channel
    const url = new URL(req.url, `http://${req.headers.host}`);
    const path = url.pathname;
    
    // Determine channel
    if (path.startsWith('/ws/tracking/')) {
        const bookingId = path.split('/')[3];
        handleTrackingConnection(ws, bookingId);
    } else if (path.startsWith('/ws/chat/')) {
        const conversationId = path.split('/')[3];
        handleChatConnection(ws, conversationId);
    } else if (path.startsWith('/ws/notifications/')) {
        handleNotificationsConnection(ws);
    } else {
        ws.close(1003, 'Invalid path');
    }
});

// Tracking connection handler
function handleTrackingConnection(ws, bookingId) {
    const channel = `tracking:${bookingId}`;
    
    // Subscribe to Redis channel
    redisSub.subscribe(channel, (err, count) => {
        if (!err) {
            console.log(`Subscribed to ${channel}`);
        }
    });
    
    // Store client
    clients.set(ws, {
        type: 'tracking',
        channel: channel,
        bookingId: bookingId
    });
    
    // Send initial data
    redisPub.get(`tracking:${bookingId}:latest`, (err, data) => {
        if (data && !err) {
            ws.send(JSON.stringify({
                type: 'initial',
                data: JSON.parse(data)
            }));
        }
    });
    
    // Handle messages
    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);
            
            if (data.type === 'set_alert') {
                // Store alert in Redis
                const alertKey = `tracking:${bookingId}:alerts:${ws.userId}`;
                redisPub.setex(alertKey, 86400, JSON.stringify(data));
            }
        } catch (error) {
            console.error('Error handling message:', error);
        }
    });
}

// Chat connection handler
function handleChatConnection(ws, conversationId) {
    const channel = `chat:${conversationId}`;
    
    redisSub.subscribe(channel, (err, count) => {
        if (!err) {
            console.log(`Subscribed to ${channel}`);
        }
    });
    
    clients.set(ws, {
        type: 'chat',
        channel: channel,
        conversationId: conversationId
    });
    
    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);
            data.userId = ws.userId;
            data.timestamp = new Date().toISOString();
            
            // Publish to Redis
            redisPub.publish(channel, JSON.stringify(data));
            
            // Store in database via API
            // This would call the Django API
        } catch (error) {
            console.error('Error handling message:', error);
        }
    });
}

// Notifications connection handler
function handleNotificationsConnection(ws) {
    const channel = `notifications:${ws.userId}`;
    
    redisSub.subscribe(channel, (err, count) => {
        if (!err) {
            console.log(`Subscribed to ${channel}`);
        }
    });
    
    clients.set(ws, {
        type: 'notifications',
        channel: channel,
        userId: ws.userId
    });
    
    // Send unread notifications
    redisPub.get(`notifications:${ws.userId}:unread`, (err, data) => {
        if (data && !err) {
            ws.send(JSON.stringify({
                type: 'unread',
                data: JSON.parse(data)
            }));
        }
    });
}

// Redis subscription handler
redisSub.on('message', (channel, message) => {
    // Find clients subscribed to this channel
    for (const [ws, info] of clients) {
        if (info.channel === channel && ws.readyState === WebSocket.OPEN) {
            ws.send(message);
        }
    }
});

// Clean up disconnected clients
setInterval(() => {
    for (const [ws, info] of clients) {
        if (ws.readyState !== WebSocket.OPEN) {
            clients.delete(ws);
        }
    }
}, 30000);

// Start server
server.listen(PORT, () => {
    console.log(`WebSocket server running on port ${PORT}`);
});

// Graceful shutdown
process.on('SIGTERM', () => {
    console.log('Shutting down...');
    wss.close();
    redisPub.quit();
    redisSub.quit();
    server.close();
});