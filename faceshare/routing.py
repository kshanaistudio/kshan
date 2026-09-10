from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/faceshare/(?P<room_code>[A-Za-z0-9]+)/?$', consumers.FaceShareSignalingConsumer.as_asgi()),
]
