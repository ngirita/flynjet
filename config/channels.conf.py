# Channels configuration

# Channel layers
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('localhost', 6379)],
            'capacity': 1000,
            'expiry': 60,
        },
    },
}

# Routing
CHANNEL_ROUTING = {
    'websocket': {
        'tracking': 'apps.tracking.routing.websocket_urlpatterns',
        'chat': 'apps.chat.routing.websocket_urlpatterns',
    }
}

# Security
CHANNEL_SECURITY = {
    'ALLOWED_HOSTS': ['*'],
    'CORS_ALLOWED_ORIGINS': [
        'http://localhost:8000',
        'https://flynjet.com',
    ],
}

# Performance
CHANNEL_PERFORMANCE = {
    'worker_threads': 4,
    'task_always_eager': False,
    'task_eager_propagates': False,
}