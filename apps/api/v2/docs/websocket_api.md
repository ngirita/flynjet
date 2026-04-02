# FlynJet WebSocket API Documentation v2

## Overview
The FlynJet WebSocket API provides real-time updates for flight tracking, chat support, and notifications.

## Connection

### Base URL


### Authentication
Include JWT token in the connection URL:

wss://api.flynjet.com/v2/ws/?token=<your-jwt-token>


Or use the `Authorization` header during WebSocket handshake.

## Connection Management

### Ping/Pong
The server sends a ping every 30 seconds. Clients should respond with a pong to keep the connection alive.

**Server -> Client:**
```json
{
    "type": "ping",
    "timestamp": "2024-01-01T12:00:00Z"
}