from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/tracking/(?P<booking_id>[0-9a-f-]+)/$', consumers.TrackingConsumer.as_asgi()),
    re_path(r'ws/tracking/share/(?P<token>[0-9a-f-]+)/$', consumers.TrackingShareConsumer.as_asgi()),
]