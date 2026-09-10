from django.urls import path
from . import views

urlpatterns = [
    # Web UI Pages
    path('', views.faceshare_landing_view, name='faceshare_landing'),
    path('host/<str:room_code>/', views.faceshare_host_view, name='faceshare_host'),
    path('join/<str:room_code>/', views.faceshare_participant_view, name='faceshare_participant_join'),
    path('room/<str:room_code>/', views.faceshare_participant_view, name='faceshare_participant_room'),

    # REST APIs (Signaling and room management)
    path('api/create/', views.api_create_room, name='faceshare_api_create'),
    path('api/<str:room_code>/join/', views.api_join_room, name='faceshare_api_join'),
    path('api/<str:room_code>/status/', views.api_room_status, name='faceshare_api_status'),
    path('api/<str:room_code>/end/', views.api_end_room, name='faceshare_api_end'),
]
