import json
import logging
from django.shortcuts import render, redirect
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .room_service import room_service

logger = logging.getLogger("kshan.faceshare.views")

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def faceshare_landing_view(request):
    """
    FaceShare Home / Entry point.
    Shows Create Room & Join Room options with privacy highlights.
    """
    context = {
        'ttl_minutes': getattr(settings, 'FACESHARE_ROOM_TTL_MINUTES', 60),
        'max_photos': getattr(settings, 'FACESHARE_MAX_PHOTOS', 300),
        'max_participants': getattr(settings, 'FACESHARE_MAX_PARTICIPANTS', 15),
    }
    return render(request, 'faceshare/landing.html', context)

def faceshare_host_view(request, room_code):
    """
    Host Dashboard for managing photo batch, local face scanning, and WebRTC streaming.
    """
    room_code = room_code.upper()
    host_token = request.GET.get('token')
    
    if not host_token or not room_service.verify_host(room_code, host_token):
        # Invalid host token redirect to create room
        return redirect('/faceshare/?error=invalid_host')

    room = room_service.get_room(room_code)
    if not room:
        return redirect('/faceshare/?error=room_expired')

    context = {
        'room_code': room_code,
        'host_token': host_token,
        'expires_at': room['expires_at'],
        'stun_url': getattr(settings, 'WEBRTC_STUN_URL', 'stun:stun.l.google.com:19302'),
        'turn_url': getattr(settings, 'WEBRTC_TURN_URL', ''),
        'turn_username': getattr(settings, 'WEBRTC_TURN_USERNAME', ''),
        'turn_credential': getattr(settings, 'WEBRTC_TURN_CREDENTIAL', ''),
        'match_threshold': getattr(settings, 'FACESHARE_MATCH_THRESHOLD', 0.62),
        'max_photos': getattr(settings, 'FACESHARE_MAX_PHOTOS', 300),
    }
    return render(request, 'faceshare/host_room.html', context)

def faceshare_participant_view(request, room_code):
    """
    Participant view:
    1. Enter display name & send join request.
    2. Wait for host approval.
    3. Take selfie & extract embedding locally.
    4. View matched photos & download directly via WebRTC DataChannel.
    """
    room_code = room_code.upper()
    room = room_service.get_room(room_code)
    if not room:
        return render(request, 'faceshare/room_not_found.html', {'room_code': room_code})

    context = {
        'room_code': room_code,
        'host_name': room['host_name'],
        'expires_at': room['expires_at'],
        'stun_url': getattr(settings, 'WEBRTC_STUN_URL', 'stun:stun.l.google.com:19302'),
        'turn_url': getattr(settings, 'WEBRTC_TURN_URL', ''),
        'turn_username': getattr(settings, 'WEBRTC_TURN_USERNAME', ''),
        'turn_credential': getattr(settings, 'WEBRTC_TURN_CREDENTIAL', ''),
    }
    return render(request, 'faceshare/participant_room.html', context)

# ── REST API Endpoints ──────────────────────────────────────────────

@require_http_methods(["POST"])
def api_create_room(request):
    """
    Create a new ephemeral FaceShare room.
    """
    try:
        data = json.loads(request.body or '{}')
    except Exception:
        data = {}

    host_name = data.get('host_name', 'Trip Host')
    client_ip = get_client_ip(request)
    room_data = room_service.create_room(host_name=host_name, client_ip=client_ip)

    return JsonResponse({
        'success': True,
        'room_code': room_data['room_code'],
        'host_token': room_data['host_token'],
        'host_url': f"/faceshare/host/{room_data['room_code']}/?token={room_data['host_token']}",
        'join_url': f"/faceshare/join/{room_data['room_code']}/",
        'expires_at': room_data['expires_at'],
        'max_photos': room_data['max_photos'],
    })

@require_http_methods(["POST"])
def api_join_room(request, room_code):
    """
    Participant join request.
    """
    try:
        data = json.loads(request.body or '{}')
    except Exception:
        data = {}

    display_name = data.get('display_name', 'Guest')
    client_ip = get_client_ip(request)
    result = room_service.join_request(room_code, display_name=display_name, client_ip=client_ip)

    if not result.get('success'):
        return JsonResponse(result, status=400)

    return JsonResponse(result)

@require_http_methods(["GET"])
def api_room_status(request, room_code):
    """
    Poll room availability and participant status.
    """
    room = room_service.get_room(room_code)
    if not room:
        return JsonResponse({'success': False, 'error': 'Room not found or expired.'}, status=404)
    return JsonResponse({'success': True, 'room': room})

@require_http_methods(["POST"])
def api_end_room(request, room_code):
    """
    Host explicitly terminates room.
    """
    try:
        data = json.loads(request.body or '{}')
    except Exception:
        data = {}

    token = data.get('host_token') or request.GET.get('token')
    if not token or not room_service.verify_host(room_code, token):
        return JsonResponse({'success': False, 'error': 'Unauthorized.'}, status=403)

    room_service.destroy_room(room_code, token)
    return JsonResponse({'success': True, 'message': 'Room ended successfully.'})
