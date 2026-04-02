import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'flynjet.settings')
django.setup()

from apps.chat.routing import websocket_urlpatterns as chat_websocket_urlpatterns
from apps.tracking.routing import websocket_urlpatterns as tracking_websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                chat_websocket_urlpatterns + tracking_websocket_urlpatterns
            )
        )
    ),
})