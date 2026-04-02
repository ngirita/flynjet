from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Updated pattern to match conversation IDs like CHAT20260324200726LOIG2J
    re_path(r'ws/chat/(?P<conversation_id>[A-Z0-9]+)/$', consumers.ChatConsumer.as_asgi()),
    re_path(r'ws/agent/$', consumers.AgentConsumer.as_asgi()),
]