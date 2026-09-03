import os
import json
import base64
import re
import time
from pathlib import Path
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.conf import settings
from django.db.models import Sum, Count

from .models import (
    Event, Photo, Face, PhotographerProfile, SearchLog, DownloadLog, 
    SubEvent, GuestRegistration, GuestFavorite, Album, AlbumPhoto,
    PaymentOrder, GuestPurchase, Collection, WhatsAppOTPVerification
)
from .services.face_service import get_face_service
from .services.matching_service import find_matching_photos
from .services.image_service import compute_sha256, get_image_metadata
from .services.storage_service import (
    save_uploaded_photo, 
    create_zip_archive, 
    delete_event_storage, 
    cleanup_temp_files
)
from .services.background_worker import (
    queue_photo_processing, 
    queue_batch_processing, 
    get_event_progress
)
from .services.razorpay_service import create_razorpay_order, verify_razorpay_signature

# Helper to ensure profile exists
def get_or_create_profile(user):
    profile, _ = PhotographerProfile.objects.get_or_create(user=user)
    return profile

# ================= PUBLIC GUEST HTML VIEWS =================

@ensure_csrf_cookie
def home_view(request):
    return render(request, "index.html")

@ensure_csrf_cookie
def event_view(request, event_code):
    code = event_code.strip().upper()
    try:
        event = Event.objects.select_related('photographer', 'photographer__profile', 'cover_photo').get(event_code=code)
    except Event.DoesNotExist:
        return render(request, "index.html", {
            "error": f"Event code '{code}' was not found. Please check and try again."
        }, status=404)

    # PIN Protection Check
    if event.access_mode == 'pin':
        session_pin = request.session.get(f"pin_verified_{event.event_code}")
        if not session_pin:
            return render(request, "event_pin.html", {"event": event})

    photo_count = Photo.objects.filter(event=event, processing_status="completed").count()
    highlights_count = Photo.objects.filter(event=event, processing_status="completed", is_highlight=True).count()
    profile = getattr(event.photographer, 'profile', None)

    return render(request, "event.html", {
        "event": event,
        "photo_count": photo_count,
        "highlights_count": highlights_count,
        "profile": profile
    })

def event_verify_pin_api(request, event_code):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    code = event_code.strip().upper()
    event = get_object_or_404(Event, event_code=code)
    pin = request.POST.get("pin", "").strip()
    if event.access_pin and pin == event.access_pin:
        request.session[f"pin_verified_{event.event_code}"] = True
        return JsonResponse({"success": True})
    return JsonResponse({"error": "Incorrect event PIN. Please try again."}, status=403)

@ensure_csrf_cookie
def event_gallery_view(request, event_code):
    code = event_code.strip().upper()
    try:
        event = Event.objects.select_related('photographer', 'photographer__profile').get(event_code=code)
    except Event.DoesNotExist:
        return render(request, "index.html", {
            "error": f"Event '{code}' was not found."
        }, status=404)

    profile = getattr(event.photographer, 'profile', None)
    return render(request, "gallery.html", {
        "event": event,
        "profile": profile
    })

def public_highlights_api(request, event_code):
    code = event_code.strip().upper()
    event = get_object_or_404(Event, event_code=code)
    if not event.public_gallery_enabled:
        return JsonResponse({"error": "Public gallery is disabled for this event."}, status=403)

    highlights = Photo.objects.filter(event=event, processing_status="completed", is_highlight=True)

    return JsonResponse({
        "event_id": event.id,
        "event_name": event.name,
        "event_code": event.event_code,
        "photos": [p.to_dict() for p in highlights]
    })

# ================= PHOTOGRAPHER AUTH & VIEWS =================

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        studio_name = request.POST.get("studio_name", "").strip()
        phone = request.POST.get("phone", "").strip()

        if not username or not password:
            return render(request, "signup.html", {"error": "Username and password are required."})

        if User.objects.filter(username=username).exists():
            return render(request, "signup.html", {"error": f"Username '{username}' is already taken."})

        user = User.objects.create_user(username=username, email=email, password=password)
        PhotographerProfile.objects.create(
            user=user,
            studio_name=studio_name or f"{username.capitalize()} Studio",
            display_name=username.capitalize(),
            phone=phone
        )
        login(request, user)
        return redirect('admin_dashboard')

    return render(request, "signup.html", {"error": None})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('admin_dashboard')

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            get_or_create_profile(user)
            return redirect('admin_dashboard')
        else:
            return render(request, "login.html", {
                "error": "Invalid username or password"
            }, status=401)

    return render(request, "login.html", {"error": None})

@csrf_exempt
def send_whatsapp_otp_api(request):
    """
    Generates and sends a 6-digit WhatsApp OTP to a studio phone number using Meta Cloud API.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    phone = data.get("phone", "").strip()
    purpose = data.get("purpose", "login")  # 'login' or 'signup'
    
    if not phone:
        return JsonResponse({"success": False, "error": "Please enter your WhatsApp phone number."}, status=400)

    import random
    from django.utils import timezone
    from datetime import timedelta
    from .services.whatsapp_service import send_whatsapp_otp, normalize_phone_number

    norm_phone = normalize_phone_number(phone)
    if not norm_phone or len(norm_phone) < 10:
        return JsonResponse({"success": False, "error": "Please enter a valid 10-digit WhatsApp number."}, status=400)

    # For login purpose, check if a photographer with this phone exists
    if purpose == 'login':
        profile_match = PhotographerProfile.objects.filter(phone__icontains=phone[-10:]).select_related('user').first()
        if not profile_match:
            # Check by username if username is formatted as phone
            user_match = User.objects.filter(username=phone[-10:]).first()
            if not user_match:
                return JsonResponse({
                    "success": False, 
                    "error": "No studio account found with this phone number. Please create an account first."
                }, status=404)

    # Generate 6-digit cryptographic OTP
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = timezone.now() + timedelta(minutes=10)

    # Invalidate previous unverified OTPs for this phone
    WhatsAppOTPVerification.objects.filter(phone=norm_phone, purpose=purpose, is_verified=False).delete()

    # Save to database
    WhatsAppOTPVerification.objects.create(
        phone=norm_phone,
        otp_code=otp_code,
        purpose=purpose,
        expires_at=expires_at
    )

    # Send via Meta WhatsApp Cloud API
    res = send_whatsapp_otp(norm_phone, otp_code)
    
    if res.get("success"):
        return JsonResponse({
            "success": True,
            "message": f"WhatsApp OTP sent to +{norm_phone}!",
            "phone": norm_phone,
            "mock": res.get("mock", False),
            "dev_otp": res.get("otp_code") if res.get("mock") else None
        })
    else:
        return JsonResponse({
            "success": False,
            "error": res.get("error", "Failed to deliver WhatsApp message.")
        }, status=500)


@csrf_exempt
def verify_whatsapp_otp_api(request):
    """
    Verifies WhatsApp OTP code and logs photographer in or approves registration.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        data = request.POST

    phone = data.get("phone", "").strip()
    otp_code = data.get("otp_code", "").strip()
    purpose = data.get("purpose", "login")
    studio_name = data.get("studio_name", "").strip()
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()

    from .services.whatsapp_service import normalize_phone_number
    norm_phone = normalize_phone_number(phone)

    if not norm_phone or not otp_code:
        return JsonResponse({"success": False, "error": "Phone number and OTP code are required."}, status=400)

    # Find the most recent active OTP
    record = WhatsAppOTPVerification.objects.filter(
        phone=norm_phone,
        otp_code=otp_code,
        purpose=purpose,
        is_verified=False
    ).order_by('-created_at').first()

    if not record or record.is_expired():
        return JsonResponse({"success": False, "error": "Invalid or expired OTP code. Please request a new one."}, status=400)

    # Mark OTP as verified
    record.is_verified = True
    record.save(update_fields=['is_verified'])

    if purpose == 'login':
        # Find user by profile phone or username
        profile = PhotographerProfile.objects.filter(phone__icontains=norm_phone[-10:]).select_related('user').first()
        user = profile.user if profile else None
        if not user:
            user = User.objects.filter(username=norm_phone[-10:]).first()

        if not user:
            return JsonResponse({"success": False, "error": "Associated user account could not be found."}, status=404)

        # Log user in directly
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return JsonResponse({
            "success": True,
            "message": f"Welcome back, {profile.studio_name if profile else user.username}!",
            "redirect_url": "/admin/"
        })

    elif purpose == 'signup':
        # Create user and profile
        final_username = username or norm_phone[-10:]
        if User.objects.filter(username=final_username).exists():
            # If user already exists, just log them in
            user = User.objects.get(username=final_username)
        else:
            import uuid
            random_pw = uuid.uuid4().hex
            user = User.objects.create_user(
                username=final_username,
                email=email or f"{final_username}@kshan.app",
                password=random_pw
            )
            PhotographerProfile.objects.create(
                user=user,
                studio_name=studio_name or f"{final_username.capitalize()} Studio",
                display_name=studio_name or final_username,
                phone=norm_phone
            )

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return JsonResponse({
            "success": True,
            "message": "Studio account created and verified successfully!",
            "redirect_url": "/admin/"
        })

    return JsonResponse({"success": True})

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required(login_url='/login/')
def admin_dashboard_view(request):
    user = request.user
    profile = get_or_create_profile(user)

    # Photographer view: Strictly scoped to the logged-in photographer
    events = Event.objects.filter(photographer=user).select_related('cover_photo').prefetch_related('photos').order_by('-created_at')
    total_events = events.count()
    active_events = events.filter(status='published').count()
    
    event_ids = events.values_list('id', flat=True)
    total_photos = Photo.objects.filter(event_id__in=event_ids).count()
    total_processed = Photo.objects.filter(event_id__in=event_ids, processing_status='completed').count()
    total_failed = Photo.objects.filter(event_id__in=event_ids, processing_status='failed').count()
    total_faces = Face.objects.filter(event_id__in=event_ids).count()
    total_searches = SearchLog.objects.filter(event_id__in=event_ids).count()
    total_matches = SearchLog.objects.filter(event_id__in=event_ids, number_of_matches__gt=0).count()
    match_rate = round((total_matches / total_searches * 100), 1) if total_searches > 0 else 0.0
    total_guests = GuestRegistration.objects.filter(event_id__in=event_ids).count()
    total_downloads = DownloadLog.objects.filter(event_id__in=event_ids).aggregate(total=Sum('batch_count'))['total'] or 0

    # Calculate Total Storage in GB / MB
    total_bytes = Photo.objects.filter(event_id__in=event_ids).aggregate(total=Sum('file_size'))['total'] or 0
    storage_gb = round(total_bytes / (1024 * 1024 * 1024), 2)
    storage_percent = min(round((storage_gb / 100.0) * 100, 1), 100.0) # assuming 100GB plan
    if total_bytes >= 1024 * 1024 * 1024:
        storage_display = f"{total_bytes / (1024 * 1024 * 1024):.2f} GB"
    elif total_bytes >= 1024 * 1024:
        storage_display = f"{total_bytes / (1024 * 1024):.1f} MB"
    elif total_bytes > 0:
        storage_display = f"{total_bytes / 1024:.1f} KB"
    else:
        storage_display = "0.0 GB"

    # Recent Searches
    recent_searches = SearchLog.objects.filter(event_id__in=event_ids).select_related('event').order_by('-timestamp')[:8]

    return render(request, "admin_dashboard.html", {
        "user": user,
        "profile": profile,
        "events": events,
        "total_events": total_events,
        "active_events": active_events,
        "total_photos": total_photos,
        "total_processed": total_processed,
        "total_failed": total_failed,
        "total_faces": total_faces,
        "total_searches": total_searches,
        "total_matches": total_matches,
        "match_rate": match_rate,
        "total_guests": total_guests,
        "total_downloads": total_downloads,
        "storage_display": storage_display,
        "storage_gb": storage_gb,
        "storage_percent": storage_percent,
        "recent_searches": recent_searches,
    })

@login_required(login_url='/login/')
def studio_events_view(request):
    user = request.user
    profile = get_or_create_profile(user)
    events = Event.objects.filter(photographer=user).select_related('cover_photo').prefetch_related('photos')
    total_events = events.count()

    return render(request, "studio_events.html", {
        "user": user,
        "profile": profile,
        "events": events,
        "total_events": total_events,
    })

def admin_event_view(request, event_code):
    # Check if logged in as user or authenticated as master superadmin
    is_master = request.session.get("is_master_superadmin", False)
    if not request.user.is_authenticated and not is_master:
        return redirect('/login/')

    code = event_code.strip().upper()
    # Superusers and Master SuperAdmin can inspect any event; photographers can only view their own
    if (request.user.is_authenticated and request.user.is_superuser) or is_master:
        event = get_object_or_404(Event, event_code=code)
    else:
        event = get_object_or_404(Event, event_code=code, photographer=request.user)

    photos = Photo.objects.filter(event=event).order_by('-uploaded_at')
    progress = get_event_progress(event.id)
    profile = get_or_create_profile(request.user) if request.user.is_authenticated else (event.photographer.profile if hasattr(event.photographer, 'profile') else None)

    # Analytics for this event
    searches_count = SearchLog.objects.filter(event=event).count()
    downloads_count = DownloadLog.objects.filter(event=event).aggregate(total=Sum('batch_count'))['total'] or 0
    guests_count = GuestRegistration.objects.filter(event=event).count()
    subevents_count = SubEvent.objects.filter(event=event).count()
    albums_count = Album.objects.filter(event=event).count()

    total_bytes = photos.aggregate(total=Sum('file_size'))['total'] or 0
    storage_mb = round(total_bytes / (1024 * 1024), 2)
    storage_gb = round(total_bytes / (1024 * 1024 * 1024), 3)

    return render(request, "admin_event.html", {
        "event": event,
        "photos": photos,
        "progress": progress,
        "profile": profile,
        "searches_count": searches_count,
        "downloads_count": downloads_count,
        "guests_count": guests_count,
        "subevents_count": subevents_count,
        "albums_count": albums_count,
        "storage_mb": storage_mb,
        "storage_gb": storage_gb,
    })

@login_required(login_url='/login/')
def admin_profile_view(request):
    profile = get_or_create_profile(request.user)
    if request.method == "POST":
        profile.studio_name = request.POST.get("studio_name", "").strip()
        profile.display_name = request.POST.get("display_name", "").strip()
        profile.phone = request.POST.get("phone", "").strip()
        profile.city = request.POST.get("city", "").strip()
        profile.website = request.POST.get("website", "").strip()
        profile.instagram = request.POST.get("instagram", "").strip()
        profile.bio = request.POST.get("bio", "").strip()
        profile.whatsapp_number = request.POST.get("whatsapp_number", "").strip() or None
        profile.booking_url = request.POST.get("booking_url", "").strip() or None
        
        if request.FILES.get("profile_photo"):
            profile.profile_photo = request.FILES.get("profile_photo")
        if request.FILES.get("studio_logo"):
            profile.studio_logo = request.FILES.get("studio_logo")
        elif request.POST.get("remove_studio_logo") == "1":
            if profile.studio_logo:
                try:
                    profile.studio_logo.delete(save=False)
                except Exception:
                    pass
            profile.studio_logo = None
            
        profile.save()
        return render(request, "admin_profile.html", {"profile": profile, "success": "Profile updated successfully!"})

    return render(request, "admin_profile.html", {"profile": profile})

@login_required(login_url='/login/')
def admin_settings_view(request):
    profile = get_or_create_profile(request.user)
    return render(request, "admin_settings.html", {"profile": profile})

@login_required(login_url='/login/')
def studio_analytics_view(request):
    user = request.user
    profile = get_or_create_profile(user)
    events = Event.objects.filter(photographer=user).select_related('cover_photo')
    event_ids = events.values_list('id', flat=True)

    total_events = events.count()
    total_photos = Photo.objects.filter(event_id__in=event_ids).count()
    total_faces = Face.objects.filter(event_id__in=event_ids).count()
    total_searches = SearchLog.objects.filter(event_id__in=event_ids).count()
    total_downloads = DownloadLog.objects.filter(event_id__in=event_ids).aggregate(total=Sum('batch_count'))['total'] or 0

    recent_searches = SearchLog.objects.filter(event_id__in=event_ids).select_related('event').order_by('-timestamp')[:20]
    recent_downloads = DownloadLog.objects.filter(event_id__in=event_ids).select_related('event', 'photo').order_by('-timestamp')[:20]

    return render(request, "studio_analytics.html", {
        "user": user,
        "profile": profile,
        "events": events,
        "total_events": total_events,
        "total_photos": total_photos,
        "total_faces": total_faces,
        "total_searches": total_searches,
        "total_downloads": total_downloads,
        "recent_searches": recent_searches,
        "recent_downloads": recent_downloads,
    })

@login_required(login_url='/login/')
def studio_proofing_view(request):
    user = request.user
    profile = get_or_create_profile(user)
    events = Event.objects.filter(photographer=user)
    return render(request, "studio_proofing.html", {
        "user": user,
        "profile": profile,
        "events": events
    })

@csrf_exempt
def search_face_api(request, event_id=None, event_code=None):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    if event_code:
        code = event_code.strip().upper()
        event = get_object_or_404(Event, event_code=code)
    else:
        event = get_object_or_404(Event, id=event_id)
    image_bytes = None

    uploaded_file = (
        request.FILES.get("selfie") or 
        request.FILES.get("file") or 
        request.FILES.get("image")
    )

    if uploaded_file:
        image_bytes = uploaded_file.read()
    elif request.POST.get("image_base64"):
        raw_b64 = re.sub(r"^data:image/.+;base64,", "", request.POST.get("image_base64"))
        try:
            image_bytes = base64.b64decode(raw_b64)
        except Exception:
            return JsonResponse({"error": "Invalid base64 image data"}, status=400)

    if not image_bytes:
        return JsonResponse({"error": "No selfie photo provided"}, status=400)

    cleanup_temp_files()

    face_service = get_face_service()
    try:
        query_embedding = face_service.validate_and_extract_selfie(image_bytes)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=422)
    except Exception as e:
        return JsonResponse({"error": f"Face recognition error: {str(e)}"}, status=500)

    threshold = float(request.POST.get("threshold", settings.FACE_MATCH_THRESHOLD))
    matches = find_matching_photos(event_id=event.id, query_embedding=query_embedding, threshold=threshold)

    # Privacy-conscious search analytics log (NO selfie stored)
    try:
        anon_session = request.session.session_key or "guest_anon"
        SearchLog.objects.create(
            event=event,
            number_of_matches=len(matches),
            anonymous_session_id=anon_session[:64]
        )
    except Exception:
        pass

    return JsonResponse({
        "event_id": event.id,
        "event_name": event.name,
        "event_code": event.event_code,
        "match_count": len(matches),
        "threshold": threshold,
        "photos": matches
    })

def upload_photos_api(request, event_id=None, event_code=None):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    is_master = request.session.get("is_master_superadmin", False)
    if not request.user.is_authenticated and not is_master:
        return JsonResponse({"error": "Authentication required"}, status=401)

    # Lookup event by event_id or event_code
    if event_code:
        code = event_code.strip().upper()
        if (request.user.is_authenticated and request.user.is_superuser) or is_master:
            event = get_object_or_404(Event, event_code=code)
        else:
            event = get_object_or_404(Event, event_code=code, photographer=request.user)
    else:
        if (request.user.is_authenticated and request.user.is_superuser) or is_master:
            event = get_object_or_404(Event, id=event_id)
        else:
            event = get_object_or_404(Event, id=event_id, photographer=request.user)

    files = request.FILES.getlist("photos") or request.FILES.getlist("files")
    
    uploaded_by_type = request.POST.get("uploaded_by_type", "official")
    sub_event_id = request.POST.get("sub_event_id")

    if not files:
        return JsonResponse({"error": "No image files found in upload payload."}, status=400)

    saved_photo_ids = []
    skipped_duplicates = 0
    errors = []

    for f in files:
        filename = f.name or "photo.jpg"
        ext = Path(filename).suffix.lower()
        if ext not in settings.SUPPORTED_EXTENSIONS:
            errors.append(f"Unsupported format for {filename}")
            continue

        content = f.read()
        if len(content) == 0:
            continue

        saved_filename, saved_path = save_uploaded_photo(
            event.event_code, 
            filename, 
            content
        )
        file_hash = compute_sha256(str(saved_path))

        if Photo.objects.filter(event=event, file_hash=file_hash).exists():
            try:
                saved_path.unlink(missing_ok=True)
            except Exception:
                pass
            skipped_duplicates += 1
            continue
            
        # Extract EXIF and Image Metadata
        meta = get_image_metadata(str(saved_path))
        exif = meta.get("exif", {})

        photo = Photo.objects.create(
            event=event,
            sub_event_id=sub_event_id if sub_event_id else None,
            filename=saved_filename,
            original_filename=filename,
            file_path=str(saved_path),
            file_size=meta.get("file_size", len(content)),
            width=meta.get("width", 0),
            height=meta.get("height", 0),
            file_hash=file_hash,
            processing_status="pending",
            uploaded_by_type=uploaded_by_type,
            exif_camera=exif.get("camera", ""),
            exif_lens=exif.get("lens", ""),
            exif_focal_length=exif.get("focal_length", ""),
            exif_aperture=exif.get("aperture", ""),
            exif_exposure_time=exif.get("exposure_time", ""),
            exif_iso=exif.get("iso", ""),
            exif_date_taken=exif.get("date_taken")
        )
        saved_photo_ids.append(photo.id)

    if saved_photo_ids:
        queue_batch_processing(saved_photo_ids)

    return JsonResponse({
        "message": f"Uploaded {len(saved_photo_ids)} photo(s). {skipped_duplicates} duplicate(s) skipped.",
        "uploaded_count": len(saved_photo_ids),
        "skipped_count": skipped_duplicates,
        "photo_ids": saved_photo_ids,
        "errors": errors
    })

def guest_upload_photo_api(request, event_code):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    code = event_code.strip().upper()
    event = get_object_or_404(Event, event_code=code)
    
    if not event.allow_guest_upload:
        return JsonResponse({"error": "Guest uploads are currently disabled for this event."}, status=403)

    files = request.FILES.getlist("photos") or request.FILES.getlist("files")
    guest_name = request.POST.get("guest_name", "Anonymous Guest").strip()

    if not files:
        return JsonResponse({"error": "No image files found in upload payload."}, status=400)

    saved_photo_ids = []
    skipped_duplicates = 0
    errors = []

    for f in files:
        filename = f.name or "photo.jpg"
        ext = Path(filename).suffix.lower()
        if ext not in settings.SUPPORTED_EXTENSIONS:
            errors.append(f"Unsupported format for {filename}")
            continue

        content = f.read()
        if len(content) == 0:
            continue

        saved_filename, saved_path = save_uploaded_photo(event.event_code, filename, content)
        file_hash = compute_sha256(str(saved_path))

        if Photo.objects.filter(event=event, file_hash=file_hash).exists():
            try:
                saved_path.unlink(missing_ok=True)
            except Exception:
                pass
            skipped_duplicates += 1
            continue
            
        # Extract EXIF and Image Metadata
        meta = get_image_metadata(str(saved_path))
        exif = meta.get("exif", {})

        photo = Photo.objects.create(
            event=event,
            filename=saved_filename,
            original_filename=filename,
            file_path=str(saved_path),
            file_size=meta.get("file_size", len(content)),
            width=meta.get("width", 0),
            height=meta.get("height", 0),
            file_hash=file_hash,
            processing_status="pending",
            uploaded_by_type="guest",
            uploaded_by_guest_name=guest_name,
            exif_camera=exif.get("camera", ""),
            exif_lens=exif.get("lens", ""),
            exif_focal_length=exif.get("focal_length", ""),
            exif_aperture=exif.get("aperture", ""),
            exif_exposure_time=exif.get("exposure_time", ""),
            exif_iso=exif.get("iso", ""),
            exif_date_taken=exif.get("date_taken")
        )
        saved_photo_ids.append(photo.id)

    if saved_photo_ids:
        queue_batch_processing(saved_photo_ids)

    return JsonResponse({
        "message": f"Successfully shared {len(saved_photo_ids)} photo(s).",
        "uploaded_count": len(saved_photo_ids),
        "skipped_count": skipped_duplicates,
        "photo_ids": saved_photo_ids,
        "errors": errors
    })


def get_progress_api(request, event_id):
    return JsonResponse(get_event_progress(event_id))

def reprocess_failed_api(request, event_id):
    is_master = request.session.get("is_master_superadmin", False)
    if not request.user.is_authenticated and not is_master:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    if (request.user.is_authenticated and request.user.is_superuser) or is_master:
        event = get_object_or_404(Event, id=event_id)
    else:
        event = get_object_or_404(Event, id=event_id, photographer=request.user)
    failed_photos = Photo.objects.filter(event=event, processing_status="failed")
    pids = list(failed_photos.values_list('id', flat=True))
    queue_batch_processing(pids)
    return JsonResponse({"message": f"Queued {len(pids)} failed photos for reprocessing", "count": len(pids)})

def delete_photo_api(request, photo_id):
    is_master = request.session.get("is_master_superadmin", False)
    if not request.user.is_authenticated and not is_master:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    if (request.user.is_authenticated and request.user.is_superuser) or is_master:
        photo = get_object_or_404(Photo, id=photo_id)
    else:
        photo = get_object_or_404(Photo, id=photo_id, event__photographer=request.user)
    try:
        if photo.file_path and Path(photo.file_path).exists():
            Path(photo.file_path).unlink(missing_ok=True)
        if photo.thumbnail_path and Path(photo.thumbnail_path).exists():
            Path(photo.thumbnail_path).unlink(missing_ok=True)
    except Exception:
        pass
    photo.delete()
    return JsonResponse({"message": "Photo deleted successfully"})

def delete_all_photos_api(request, event_id):
    is_master = request.session.get("is_master_superadmin", False)
    if not request.user.is_authenticated and not is_master:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    if (request.user.is_authenticated and request.user.is_superuser) or is_master:
        event = get_object_or_404(Event, id=event_id)
    else:
        event = get_object_or_404(Event, id=event_id, photographer=request.user)
    photos = Photo.objects.filter(event=event)
    count = photos.count()
    
    # Delete local files
    for photo in photos:
        try:
            if photo.file_path and Path(photo.file_path).exists():
                Path(photo.file_path).unlink(missing_ok=True)
            if photo.thumbnail_path and Path(photo.thumbnail_path).exists():
                Path(photo.thumbnail_path).unlink(missing_ok=True)
        except Exception:
            pass
            
    # Delete from Cloudflare R2
    from .services.storage_service import delete_event_storage
    delete_event_storage(event.event_code)
    
    # Delete from database
    photos.delete()
    return JsonResponse({"message": f"Successfully deleted all {count} photo(s) from event and Cloudflare R2.", "count": count})

def set_event_cover_api(request, event_id, photo_id):
    is_master = request.session.get("is_master_superadmin", False)
    if not request.user.is_authenticated and not is_master:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    if (request.user.is_authenticated and request.user.is_superuser) or is_master:
        event = get_object_or_404(Event, id=event_id)
        photo = get_object_or_404(Photo, id=photo_id, event=event)
    else:
        event = get_object_or_404(Event, id=event_id, photographer=request.user)
        photo = get_object_or_404(Photo, id=photo_id, event=event)
    event.cover_photo = photo
    event.save(update_fields=['cover_photo'])
    return JsonResponse({"message": "Event cover photo updated successfully!"})

def toggle_highlight_photo_api(request, photo_id):
    is_master = request.session.get("is_master_superadmin", False)
    if not request.user.is_authenticated and not is_master:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    if (request.user.is_authenticated and request.user.is_superuser) or is_master:
        photo = get_object_or_404(Photo, id=photo_id)
    else:
        photo = get_object_or_404(Photo, id=photo_id, event__photographer=request.user)
    photo.is_highlight = not photo.is_highlight
    photo.save(update_fields=['is_highlight'])
    return JsonResponse({
        "message": f"Photo {'added to' if photo.is_highlight else 'removed from'} highlights.",
        "is_highlight": photo.is_highlight
    })

def update_event_settings_api(request, event_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    
    try:
        body = json.loads(request.body.decode("utf-8"))
    except Exception:
        body = request.POST

    if "name" in body:
        event.name = body.get("name").strip()
    if "event_type" in body:
        event.event_type = body.get("event_type")
    if "event_date" in body:
        event.event_date = body.get("event_date").strip()
    if "location" in body:
        event.location = body.get("location").strip()
    if "description" in body:
        event.description = body.get("description").strip()
    if "status" in body:
        event.status = body.get("status")
    if "public_gallery_enabled" in body:
        event.public_gallery_enabled = str(body.get("public_gallery_enabled")).lower() == 'true'
    if "access_mode" in body:
        event.access_mode = body.get("access_mode")
    if "access_pin" in body:
        event.access_pin = body.get("access_pin").strip()
    if "password" in body:
        event.password = body.get("password").strip()
    if "expires_at" in body:
        from datetime import datetime
        date_str = body.get("expires_at").strip()
        if date_str:
            try:
                event.expires_at = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            event.expires_at = None
    if "allow_guest_download" in body:
        event.allow_guest_download = str(body.get("allow_guest_download")).lower() == 'true'
    if "allow_guest_upload" in body:
        event.allow_guest_upload = str(body.get("allow_guest_upload")).lower() == 'true'
    if "watermark_enabled" in body:
        event.watermark_enabled = str(body.get("watermark_enabled")).lower() == 'true'
    if "visibility" in body:
        event.visibility = body.get("visibility")
    if "pricing_model" in body:
        event.pricing_model = body.get("pricing_model")
    if "price_per_photo" in body:
        try:
            event.price_per_photo = int(body.get("price_per_photo", 0))
        except (ValueError, TypeError):
            pass
    if "price_full_event" in body:
        try:
            event.price_full_event = int(body.get("price_full_event", 0))
        except (ValueError, TypeError):
            pass

    event.save()
    return JsonResponse({"message": "Event settings saved successfully!", "event": event.to_dict()})

def create_event_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    
    if request.content_type == "application/json":
        try:
            body = json.loads(request.body.decode("utf-8"))
        except Exception:
            body = {}
        name = body.get("name", "").strip()
        code = body.get("event_code", "").strip().upper()
        date = body.get("event_date", "").strip()
        loc = body.get("location", "").strip()
        etype = body.get("event_type", "wedding")
        desc = body.get("description", "").strip()
    else:
        name = request.POST.get("name", "").strip()
        code = request.POST.get("event_code", "").strip().upper()
        date = request.POST.get("event_date", "").strip()
        loc = request.POST.get("location", "").strip()
        etype = request.POST.get("event_type", "wedding")
        desc = request.POST.get("description", "").strip()

    if not code:
        # Auto-generate event code if not provided
        code = f"EV{int(time.time()) % 100000:05d}"
        
    if Event.objects.filter(event_code=code).exists():
        return JsonResponse({"error": f"Event code '{code}' already exists"}, status=400)

    event = Event.objects.create(
        photographer=request.user,
        name=name,
        event_code=code,
        event_date=date,
        location=loc,
        event_type=etype,
        description=desc
    )
    return JsonResponse({"message": "Event created successfully", "event": event.to_dict()}, status=201)

def delete_event_api(request, event_id):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Unauthorized"}, status=401)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    event_code = event.event_code
    event.delete()
    delete_event_storage(event_code)
    return JsonResponse({"message": f"Event '{event_code}' and all related photos deleted"})

# ================= PHOTO SERVING & ZIP DOWNLOAD =================

def get_thumbnail_view(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    if photo.thumbnail_path and Path(photo.thumbnail_path).exists():
        return FileResponse(open(photo.thumbnail_path, 'rb'), content_type="image/jpeg")
    if photo.file_path and Path(photo.file_path).exists():
        return FileResponse(open(photo.file_path, 'rb'), content_type="image/jpeg")
    raise Http404("Photo image not found")

def view_photo_full(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    if not photo.file_path or not Path(photo.file_path).exists():
        raise Http404("Photo not found")
    ext = Path(photo.file_path).suffix.lower()
    content_type = "image/png" if ext == ".png" else "image/webp" if ext == ".webp" else "image/jpeg"
    return FileResponse(open(photo.file_path, 'rb'), content_type=content_type)

def check_guest_download_access(event, photo=None, session_id=None, user=None):
    """
    Checks if a download is authorized:
    - If event photographer is requesting, always allowed.
    - If event is free, allowed.
    - If event is paid, checks if session or user has unlocked the full event or specific photo.
    """
    if user and user.is_authenticated and (user == event.photographer or user.is_staff):
        return True, "Authorized as Photographer/Staff"

    if event.pricing_model == 'free':
        return True, "Free download"

    if not session_id:
        return False, "Payment required to download original photos."

    # Check if session has full event purchase
    has_full_event = GuestPurchase.objects.filter(
        event=event,
        anonymous_session_id=session_id,
        is_full_event=True
    ).exists()
    if has_full_event:
        return True, "Full event unlocked"

    if photo and event.pricing_model == 'paid_per_photo':
        has_photo = GuestPurchase.objects.filter(
            event=event,
            photo=photo,
            anonymous_session_id=session_id
        ).exists()
        if has_photo:
            return True, "Photo unlocked"

    return False, f"Payment required: Event requires {'₹' + str(event.price_full_event) + ' for full album' if event.pricing_model == 'paid_full_event' else '₹' + str(event.price_per_photo) + ' per photo'}."


def download_photo_view(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    if not photo.file_path or not Path(photo.file_path).exists():
        raise Http404("Photo not found")

    session_id = request.GET.get("session_id") or request.session.session_key
    allowed, reason = check_guest_download_access(photo.event, photo=photo, session_id=session_id, user=request.user)
    if not allowed:
        return JsonResponse({"detail": reason, "requires_payment": True, "event_code": photo.event.event_code, "pricing_model": photo.event.pricing_model, "price": photo.event.price_per_photo if photo.event.pricing_model == 'paid_per_photo' else photo.event.price_full_event}, status=402)

    # Log download
    try:
        DownloadLog.objects.create(event=photo.event, photo=photo, is_batch=False, batch_count=1)
    except Exception:
        pass

    response = FileResponse(open(photo.file_path, 'rb'), as_attachment=True, filename=photo.original_filename)
    return response

@csrf_exempt
def download_batch_zip(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        photo_ids = data.get("photo_ids", [])
        session_id = data.get("session_id") or request.session.session_key
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    if not photo_ids:
        return JsonResponse({"detail": "No photo IDs provided"}, status=400)

    photos = Photo.objects.filter(id__in=photo_ids).select_related('event')
    if not photos.exists():
        return JsonResponse({"detail": "No photos found"}, status=404)

    first_event = photos.first().event
    allowed, reason = check_guest_download_access(first_event, session_id=session_id, user=request.user)
    if not allowed:
        return JsonResponse({"detail": reason, "requires_payment": True, "event_code": first_event.event_code, "pricing_model": first_event.pricing_model, "price_full_event": first_event.price_full_event, "price_per_photo": first_event.price_per_photo}, status=402)

    photos_info = [
        {"file_path": p.file_path, "original_filename": p.original_filename}
        for p in photos if p.file_path and Path(p.file_path).exists()
    ]
    if not photos_info:
        return JsonResponse({"detail": "None of the selected photos exist on disk"}, status=404)

    # Log batch download
    try:
        DownloadLog.objects.create(event=first_event, is_batch=True, batch_count=len(photos_info))
    except Exception:
        pass

    zip_buffer = create_zip_archive(photos_info)
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="kshan_photos_{len(photos_info)}.zip"'
    return response

# ================= QR CODE & SHARING =================

import io
import qrcode

def event_qr_code_view(request, event_code):
    code = event_code.strip().upper()
    event = get_object_or_404(Event, event_code=code)
    
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    event_url = f"{scheme}://{host}/event/{event.event_code}/"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(event_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#141413", back_color="#FFFFFF")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    download = request.GET.get("download")
    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    if download:
        response["Content-Disposition"] = f'attachment; filename="kshan_qr_{event.event_code}.png"'
    return response

@login_required(login_url='/login/')
def event_share_view(request, event_code):
    code = event_code.strip().upper()
    event = get_object_or_404(Event, event_code=code, photographer=request.user)
    profile = get_or_create_profile(request.user)
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    event_url = f"{scheme}://{host}/event/{event.event_code}/"

    return render(request, "admin_share.html", {
        "event": event,
        "profile": profile,
        "event_url": event_url,
    })

@csrf_exempt
def remove_background_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    image_file = request.FILES.get("image")
    if not image_file:
        return JsonResponse({"error": "No image provided"}, status=400)

    try:
        from rembg import remove
        from PIL import Image

        input_image = Image.open(image_file)
        # Convert or ensure RGBA
        output_image = remove(input_image)

        buffer = io.BytesIO()
        output_image.save(buffer, format="PNG")
        buffer.seek(0)

        b64_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return JsonResponse({
            "success": True,
            "image_b64": f"data:image/png;base64,{b64_str}"
        })
    except Exception as e:
        return JsonResponse({"error": f"Background removal failed: {str(e)}"}, status=500)


# ================= MODULE 1: SUB-EVENT / CEREMONY FOLDERS =================

@csrf_exempt
@login_required
def create_sub_event_api(request, event_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)
    import re as _re
    slug = _re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    # ensure unique slug within event
    base_slug = slug
    counter = 1
    while SubEvent.objects.filter(event=event, slug=slug).exists():
        slug = f'{base_slug}-{counter}'
        counter += 1
    order = event.sub_events.count()
    sub = SubEvent.objects.create(event=event, name=name, slug=slug, order=order)
    return JsonResponse({'success': True, 'sub_event': {'id': sub.id, 'name': sub.name, 'slug': sub.slug, 'order': sub.order}})


@csrf_exempt
@login_required
def delete_sub_event_api(request, event_id, sub_event_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    sub = get_object_or_404(SubEvent, id=sub_event_id, event=event)
    sub.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
def assign_photos_to_sub_event_api(request, event_id, sub_event_id):
    """Assign or unassign photos to a ceremony folder."""
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    sub = None
    if str(sub_event_id) != '0':
        sub = get_object_or_404(SubEvent, id=sub_event_id, event=event)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    photo_ids = data.get('photo_ids', [])
    if not isinstance(photo_ids, list):
        return JsonResponse({'error': 'photo_ids must be a list'}, status=400)
    updated = Photo.objects.filter(id__in=photo_ids, event=event).update(sub_event=sub)
    return JsonResponse({'success': True, 'updated': updated})


@login_required
def list_sub_events_api(request, event_id):
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    subs = list(event.sub_events.values('id', 'name', 'slug', 'order'))
    for s in subs:
        s['photo_count'] = Photo.objects.filter(event=event, sub_event_id=s['id']).count()
    return JsonResponse({'sub_events': subs})


# ================= MODULE 2: GUEST RSVP REGISTRATION =================

@csrf_exempt
def guest_register_api(request, event_code):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, event_code=event_code.upper())
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name is required'}, status=400)
    phone = data.get('phone', '').strip() or None
    email = data.get('email', '').strip() or None
    session_id = data.get('session_id', '') or ''
    
    reg = GuestRegistration.objects.create(
        event=event,
        name=name,
        phone=phone,
        email=email,
        anonymous_session_id=session_id
    )

    # 100% Free WhatsApp Direct Welcome deep link with personalized greeting & event URL
    from urllib.parse import quote
    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    event_url = f"{scheme}://{host}/event/{event.event_code}/"
    studio_name = event.photographer.profile.studio_name if (event.photographer and hasattr(event.photographer, 'profile')) else "KSHAN Studio"
    
    welcome_text = (
        f"📸 *Hello {name}!* Welcome to *{event.name}*!\n\n"
        f"✨ Your photos are being indexed in real-time by *{studio_name}*.\n\n"
        f"🔗 Find all your AI-matched photos anytime here:\n{event_url}\n\n"
        f"Enjoy the celebrations! 🎉"
    )

    clean_phone = "".join(ch for ch in phone if ch.isdigit()) if phone else ""
    if clean_phone and len(clean_phone) == 10:
        clean_phone = "91" + clean_phone

    wa_send_url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={quote(welcome_text)}" if clean_phone else f"https://api.whatsapp.com/send?text={quote(welcome_text)}"

    return JsonResponse({
        'success': True, 
        'registration_id': reg.id,
        'guest_name': name,
        'whatsapp_welcome_url': wa_send_url,
        'welcome_message': welcome_text,
        'has_phone': bool(clean_phone)
    })


@login_required
def guest_list_api(request, event_id):
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    regs = event.guest_registrations.all()[:200]
    return JsonResponse({'guests': [r.to_dict() for r in regs]})


@login_required
def studio_guests_view(request):
    events = Event.objects.filter(photographer=request.user).prefetch_related('guest_registrations')
    event_data = []
    for ev in events:
        event_data.append({
            'event': ev,
            'guest_count': ev.guest_registrations.count(),
        })
    return render(request, 'studio_guests.html', {'event_data': event_data, 'events': events})


# ================= MODULE 3: WHATSAPP SHARE =================

@csrf_exempt
def whatsapp_link_api(request, event_code):
    event = get_object_or_404(Event, event_code=event_code.upper())
    from django.urls import reverse
    from urllib.parse import quote
    gallery_url = request.build_absolute_uri(f'/event/{event.event_code}/')
    msg = f'🎉 View your photos from *{event.name}*!\n\nFind your moments: {gallery_url}'
    wa_link = f'https://wa.me/?text={quote(msg)}'
    return JsonResponse({'whatsapp_link': wa_link, 'message': msg, 'gallery_url': gallery_url})


# ================= MODULE 4: LIVE PROJECTOR BEAM MODE =================

@login_required
def beam_view(request, event_code):
    event = get_object_or_404(Event, event_code=event_code.upper(), photographer=request.user)
    profile = get_or_create_profile(request.user)
    return render(request, 'beam.html', {'event': event, 'profile': profile})


@csrf_exempt
def beam_photos_api(request, event_code):
    """Returns the latest N completed photos for the beam slideshow."""
    event = get_object_or_404(Event, event_code=event_code.upper())
    limit = int(request.GET.get('limit', 30))
    photos = Photo.objects.filter(event=event, processing_status='completed').order_by('-uploaded_at')[:limit]
    data = []
    for p in photos:
        data.append({
            'id': p.id,
            'url': request.build_absolute_uri(p.view_url),
            'thumb_url': request.build_absolute_uri(p.thumbnail_url),
            'filename': p.original_filename,
        })
    return JsonResponse({'photos': data})


# ================= MODULE 5: BULK PHOTO ACTIONS =================

@csrf_exempt
@login_required
def bulk_delete_photos_api(request, event_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    photo_ids = data.get('photo_ids', [])
    if not isinstance(photo_ids, list) or not photo_ids:
        return JsonResponse({'error': 'photo_ids list required'}, status=400)
    photos = Photo.objects.filter(id__in=photo_ids, event=event)
    count = photos.count()
    for p in photos:
        try:
            if p.file_path and os.path.exists(p.file_path):
                os.remove(p.file_path)
            if p.thumbnail_path and os.path.exists(p.thumbnail_path):
                os.remove(p.thumbnail_path)
        except Exception:
            pass
    photos.delete()
    return JsonResponse({'success': True, 'deleted': count})


@csrf_exempt
@login_required
def bulk_highlight_photos_api(request, event_id):
    if request.method != 'PATCH':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    photo_ids = data.get('photo_ids', [])
    highlight = bool(data.get('highlight', True))
    updated = Photo.objects.filter(id__in=photo_ids, event=event).update(is_highlight=highlight)
    return JsonResponse({'success': True, 'updated': updated})


@login_required
def photo_info_api(request, photo_id):
    photo = get_object_or_404(Photo, id=photo_id)
    if photo.event.photographer != request.user:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    return JsonResponse({
        'id': photo.id,
        'filename': photo.original_filename,
        'file_size': photo.file_size,
        'width': photo.width,
        'height': photo.height,
        'processing_status': photo.processing_status,
        'is_highlight': photo.is_highlight,
        'face_count': photo.faces.count(),
        'uploaded_at': photo.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if photo.uploaded_at else '',
        'sub_event': photo.sub_event.name if photo.sub_event else None,
        'thumbnail_url': photo.thumbnail_url,
        'view_url': photo.view_url,
        'uploaded_by_type': photo.uploaded_by_type,
        'uploaded_by_guest_name': photo.uploaded_by_guest_name or '',
        'exif_camera': photo.exif_camera or '',
        'exif_lens': photo.exif_lens or '',
        'exif_focal_length': photo.exif_focal_length or '',
        'exif_aperture': photo.exif_aperture or '',
        'exif_exposure_time': photo.exif_exposure_time or '',
        'exif_iso': photo.exif_iso or '',
        'exif_date_taken': photo.exif_date_taken.strftime('%b %d, %Y, %I:%M %p') if photo.exif_date_taken else '',
    })


# ================= MODULE 6: GUEST FAVORITES / HEARTING =================

@csrf_exempt
def toggle_favorite_api(request, event_code):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, event_code=event_code.upper())
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    photo_id = data.get('photo_id')
    session_id = data.get('session_id', '')
    if not photo_id or not session_id:
        return JsonResponse({'error': 'photo_id and session_id required'}, status=400)
    photo = get_object_or_404(Photo, id=photo_id, event=event)
    fav, created = GuestFavorite.objects.get_or_create(
        photo=photo, anonymous_session_id=session_id,
        defaults={'event': event}
    )
    if not created:
        fav.delete()
        return JsonResponse({'success': True, 'favorited': False})
    return JsonResponse({'success': True, 'favorited': True})


@csrf_exempt
def get_favorites_api(request, event_code):
    event = get_object_or_404(Event, event_code=event_code.upper())
    session_id = request.GET.get('session_id', '')
    if not session_id:
        return JsonResponse({'favorites': []})
    favs = GuestFavorite.objects.filter(event=event, anonymous_session_id=session_id).values_list('photo_id', flat=True)
    return JsonResponse({'favorites': list(favs)})


# ================= MODULE 8: REPROCESS ALL PHOTOS =================

@csrf_exempt
@login_required
def reprocess_all_api(request, event_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    photos = Photo.objects.filter(event=event).exclude(processing_status='completed')
    pids = list(photos.values_list('id', flat=True))
    if not pids:
        photos_all = Photo.objects.filter(event=event)
        pids = list(photos_all.values_list('id', flat=True))
    queue_batch_processing(pids)
    return JsonResponse({'message': f'Queued {len(pids)} photos for re-indexing', 'count': len(pids)})


# ================= MODULE E: ALBUM SYSTEM =================

@login_required
def album_list_api(request, event_id):
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    albums = Album.objects.filter(event=event).annotate(photo_count=Count('album_photos'))
    data = []
    for a in albums:
        cover = a.cover_photo
        data.append({
            'id': a.id,
            'name': a.name,
            'description': a.description or '',
            'photo_count': a.photo_count,
            'cover_url': cover.thumbnail_url if cover else '',
            'created_at': a.created_at.strftime('%Y-%m-%d %H:%M') if a.created_at else '',
        })
    return JsonResponse({'albums': data})


@csrf_exempt
@login_required
def album_create_api(request, event_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    name = body.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Album name is required'}, status=400)
    description = body.get('description', '').strip()
    album = Album.objects.create(event=event, name=name, description=description)
    return JsonResponse({
        'success': True,
        'album': {'id': album.id, 'name': album.name, 'description': album.description or '', 'photo_count': 0}
    }, status=201)


@csrf_exempt
@login_required
def album_delete_api(request, event_id, album_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    album = get_object_or_404(Album, id=album_id, event=event)
    album.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
def album_add_photos_api(request, event_id, album_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    album = get_object_or_404(Album, id=album_id, event=event)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    photo_ids = body.get('photo_ids', [])
    if not isinstance(photo_ids, list):
        return JsonResponse({'error': 'photo_ids must be a list'}, status=400)
    added = 0
    max_order = AlbumPhoto.objects.filter(album=album).order_by('-order').values_list('order', flat=True).first() or 0
    for pid in photo_ids:
        photo = Photo.objects.filter(id=pid, event=event).first()
        if photo and not AlbumPhoto.objects.filter(album=album, photo=photo).exists():
            max_order += 1
            AlbumPhoto.objects.create(album=album, photo=photo, order=max_order)
            added += 1
    if added > 0 and not album.cover_photo:
        first_photo = AlbumPhoto.objects.filter(album=album).order_by('order').first()
        if first_photo:
            album.cover_photo = first_photo.photo
            album.save(update_fields=['cover_photo'])
    return JsonResponse({'success': True, 'added': added})


@csrf_exempt
@login_required
def album_remove_photo_api(request, event_id, album_id, photo_id):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    album = get_object_or_404(Album, id=album_id, event=event)
    ap = AlbumPhoto.objects.filter(album=album, photo_id=photo_id).first()
    if ap:
        ap.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@login_required
def album_set_cover_api(request, event_id, album_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    album = get_object_or_404(Album, id=album_id, event=event)
    try:
        body = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    photo_id = body.get('photo_id')
    if not photo_id:
        return JsonResponse({'error': 'photo_id required'}, status=400)
    photo = get_object_or_404(Photo, id=photo_id, event=event)
    album.cover_photo = photo
    album.save(update_fields=['cover_photo'])
    return JsonResponse({'success': True})


@login_required
def album_detail_api(request, event_id, album_id):
    event = get_object_or_404(Event, id=event_id, photographer=request.user)
    album = get_object_or_404(Album, id=album_id, event=event)
    album_photos = AlbumPhoto.objects.filter(album=album).select_related('photo').order_by('order')
    photos_data = []
    for ap in album_photos:
        p = ap.photo
        photos_data.append({
            'id': p.id,
            'thumbnail_url': p.thumbnail_url,
            'view_url': p.view_url,
            'original_filename': p.original_filename,
            'order': ap.order,
        })
    return JsonResponse({
        'album': {
            'id': album.id,
            'name': album.name,
            'description': album.description or '',
            'cover_url': album.cover_photo.thumbnail_url if album.cover_photo else '',
            'photo_count': len(photos_data),
        },
        'photos': photos_data,
    })


@csrf_exempt
def public_album_view(request, event_code, album_id):
    code = event_code.strip().upper()
    event = get_object_or_404(Event, event_code=code)
    album = get_object_or_404(Album, id=album_id, event=event)
    profile = getattr(event.photographer, 'profile', None)
    album_photos = AlbumPhoto.objects.filter(album=album).select_related('photo').order_by('order')
    photos_data = []
    for ap in album_photos:
        p = ap.photo
        photos_data.append({
            'id': p.id,
            'thumbnail_url': p.thumbnail_url,
            'view_url': p.view_url,
            'original_filename': p.original_filename,
        })
    return render(request, 'public_album.html', {
        'event': event,
        'album': album,
        'photos': photos_data,
        'profile': profile,
    })


# ================= RAZORPAY BILLING & PAYMENT VIEWS =================

@login_required
def studio_billing_view(request):
    """Studio subscription and billing management page."""
    profile = get_or_create_profile(request.user)
    orders = PaymentOrder.objects.filter(user=request.user).order_by('-created_at')[:20]
    
    total_events = Event.objects.filter(photographer=request.user).count()
    
    return render(request, "studio_billing.html", {
        "profile": profile,
        "orders": orders,
        "total_events": total_events,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
    })


@csrf_exempt
@login_required
def create_subscription_order_api(request):
    """Creates a Razorpay order for Photographer Subscription Plan or Event Pass."""
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        plan_tier = data.get("plan_tier") # 'pro_monthly', 'studio_annual', 'event_pass'
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    pricing_map = {
        'demo_test': {'amount': 1, 'name': 'Demo / Live Test Checkout (₹1)'},
        'event_pass': {'amount': 499, 'name': 'Single Event Unlimited Pass (₹499)'},
        'pro_monthly': {'amount': 1499, 'name': 'Pro Monthly Subscription (₹1,499/mo)'},
        'studio_annual': {'amount': 12999, 'name': 'Studio Annual Subscription (₹12,999/yr)'},
    }

    if plan_tier not in pricing_map:
        return JsonResponse({"detail": "Invalid subscription plan selected"}, status=400)

    plan_info = pricing_map[plan_tier]
    amount = plan_info['amount']

    try:
        order = create_razorpay_order(
            amount_in_rupees=amount,
            receipt=f"sub_{request.user.id}_{int(time.time())}",
            notes={
                "user_id": request.user.id,
                "username": request.user.username,
                "plan_tier": plan_tier,
            }
        )
        
        # Save PaymentOrder
        payment_order = PaymentOrder.objects.create(
            order_id=order["id"],
            payment_type='event_pass' if plan_tier == 'event_pass' else 'photographer_plan',
            status='created',
            amount=amount,
            currency='INR',
            user=request.user,
            notes=json.dumps({"plan_tier": plan_tier, "plan_name": plan_info['name']})
        )

        return JsonResponse({
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": settings.RAZORPAY_KEY_ID,
            "plan_name": plan_info['name'],
            "user_name": request.user.get_full_name() or request.user.username,
            "user_email": request.user.email,
        })
    except Exception as e:
        return JsonResponse({"detail": f"Failed to initialize payment: {str(e)}"}, status=500)


@csrf_exempt
@login_required
def verify_subscription_payment_api(request):
    """Verifies Razorpay payment signature for photographer subscription and activates plan."""
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body.decode('utf-8'))
        order_id = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature = data.get("razorpay_signature")
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    if not order_id or not payment_id or not signature:
        return JsonResponse({"detail": "Missing payment verification parameters"}, status=400)

    payment_order = get_object_or_404(PaymentOrder, order_id=order_id, user=request.user)

    is_valid = verify_razorpay_signature(order_id, payment_id, signature)
    if not is_valid:
        payment_order.status = 'failed'
        payment_order.save(update_fields=['status'])
        return JsonResponse({"detail": "Cryptographic signature verification failed"}, status=400)

    # Mark paid
    payment_order.payment_id = payment_id
    payment_order.signature = signature
    payment_order.status = 'paid'
    
    from django.utils import timezone
    payment_order.paid_at = timezone.now()
    payment_order.save()

    # Update photographer profile
    profile = get_or_create_profile(request.user)
    try:
        notes_data = json.loads(payment_order.notes or "{}")
        plan_tier = notes_data.get("plan_tier")
    except Exception:
        plan_tier = 'pro_monthly'

    if plan_tier == 'demo_test':
        profile.subscription_tier = 'pro_monthly'
        profile.plan_expires_at = timezone.now() + timezone.timedelta(days=7) # 7-day demo trial
        profile.event_credits += 1
    elif plan_tier == 'event_pass':
        profile.event_credits += 1
    elif plan_tier == 'pro_monthly':
        profile.subscription_tier = 'pro_monthly'
        profile.plan_expires_at = timezone.now() + timezone.timedelta(days=30)
    elif plan_tier == 'studio_annual':
        profile.subscription_tier = 'studio_annual'
        profile.plan_expires_at = timezone.now() + timezone.timedelta(days=365)
    
    profile.save()

    return JsonResponse({
        "success": True,
        "message": f"Payment of ₹{payment_order.amount} verified! Your plan has been updated.",
        "subscription_tier": profile.subscription_tier,
        "event_credits": profile.event_credits,
        "plan_expires_at": profile.plan_expires_at.strftime("%Y-%m-%d") if profile.plan_expires_at else None,
    })


@csrf_exempt
def create_guest_payment_order_api(request, event_code):
    """Creates a Razorpay order for a guest to buy a single photo or full event album unlock."""
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    code = event_code.strip().upper()
    event = get_object_or_404(Event, event_code=code)

    try:
        data = json.loads(request.body.decode('utf-8'))
        purchase_type = data.get("purchase_type") # 'photo' or 'full_event'
        photo_id = data.get("photo_id")
        session_id = data.get("session_id") or request.session.session_key
        guest_email = data.get("email", "").strip()
        guest_phone = data.get("phone", "").strip()
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    if not session_id:
        # Create a session key if not exists
        if not request.session.session_key:
            request.session.save()
        session_id = request.session.session_key

    photo = None
    if purchase_type == 'photo':
        if not photo_id:
            return JsonResponse({"detail": "photo_id required for single photo purchase"}, status=400)
        photo = get_object_or_404(Photo, id=photo_id, event=event)
        amount = event.price_per_photo if event.price_per_photo > 0 else 49
        item_name = f"Photo Download: {photo.original_filename}"
        payment_type = 'guest_photo_download'
    elif purchase_type == 'full_event':
        amount = event.price_full_event if event.price_full_event > 0 else 299
        item_name = f"All Event Photos Pass: {event.name}"
        payment_type = 'guest_event_unlock'
    else:
        return JsonResponse({"detail": "Invalid purchase_type. Must be 'photo' or 'full_event'"}, status=400)

    try:
        order = create_razorpay_order(
            amount_in_rupees=amount,
            receipt=f"gst_{event.event_code}_{int(time.time())}",
            notes={
                "event_code": event.event_code,
                "purchase_type": purchase_type,
                "photo_id": photo_id or "",
                "session_id": session_id,
            }
        )

        payment_order = PaymentOrder.objects.create(
            order_id=order["id"],
            payment_type=payment_type,
            status='created',
            amount=amount,
            currency='INR',
            event=event,
            photo=photo,
            guest_session_id=session_id,
            guest_email=guest_email,
            guest_phone=guest_phone,
            notes=json.dumps({"item_name": item_name, "purchase_type": purchase_type})
        )

        return JsonResponse({
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": settings.RAZORPAY_KEY_ID,
            "item_name": item_name,
            "event_name": event.name,
            "session_id": session_id,
        })
    except Exception as e:
        return JsonResponse({"detail": f"Failed to initiate order: {str(e)}"}, status=500)


@csrf_exempt
def verify_guest_payment_api(request, event_code):
    """Verifies Razorpay payment signature for guest photo/album purchase and grants download permission."""
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)

    code = event_code.strip().upper()
    event = get_object_or_404(Event, event_code=code)

    try:
        data = json.loads(request.body.decode('utf-8'))
        order_id = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature = data.get("razorpay_signature")
        session_id = data.get("session_id") or request.session.session_key
    except Exception:
        return JsonResponse({"detail": "Invalid JSON"}, status=400)

    if not order_id or not payment_id or not signature:
        return JsonResponse({"detail": "Missing payment verification parameters"}, status=400)

    payment_order = get_object_or_404(PaymentOrder, order_id=order_id, event=event)

    is_valid = verify_razorpay_signature(order_id, payment_id, signature)
    if not is_valid:
        payment_order.status = 'failed'
        payment_order.save(update_fields=['status'])
        return JsonResponse({"detail": "Cryptographic signature verification failed"}, status=400)

    from django.utils import timezone
    payment_order.payment_id = payment_id
    payment_order.signature = signature
    payment_order.status = 'paid'
    payment_order.paid_at = timezone.now()
    payment_order.save()

    active_session_id = session_id or payment_order.guest_session_id

    # Grant guest purchase
    is_full = (payment_order.payment_type == 'guest_event_unlock')
    GuestPurchase.objects.create(
        event=event,
        photo=payment_order.photo if not is_full else None,
        anonymous_session_id=active_session_id,
        payment_order=payment_order,
        is_full_event=is_full
    )

    return JsonResponse({
        "success": True,
        "message": "Payment verified successfully! Your download is now unlocked.",
        "purchase_type": "full_event" if is_full else "photo",
        "photo_id": payment_order.photo.id if payment_order.photo else None,
        "session_id": active_session_id,
    })


# ================= MASTER SUPER ADMIN VIEW (/thepranit) =================

@ensure_csrf_cookie
def thepranit_admin_view(request):
    """
    Master root administrative control panel for the whole software system.
    Protected by master passkey 'thepranit' or superuser authentication.
    """
    # Check if already authenticated in session
    if request.session.get("is_master_superadmin"):
        # Handle SuperAdmin POST actions (delete event, change tier, toggle status)
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "delete_event":
                event_id = request.POST.get("event_id")
                try:
                    ev = Event.objects.get(id=event_id)
                    delete_event_storage(ev)
                    ev.delete()
                    return JsonResponse({"success": True, "message": "Event deleted successfully."})
                except Exception as e:
                    return JsonResponse({"success": False, "error": str(e)}, status=400)

            elif action == "toggle_publish":
                event_id = request.POST.get("event_id")
                try:
                    ev = Event.objects.get(id=event_id)
                    ev.is_published = not ev.is_published
                    ev.save(update_fields=['is_published'])
                    return JsonResponse({"success": True, "is_published": ev.is_published})
                except Exception as e:
                    return JsonResponse({"success": False, "error": str(e)}, status=400)

            elif action == "update_tier":
                user_id = request.POST.get("user_id")
                new_tier = request.POST.get("tier", "starter")
                try:
                    target_user = User.objects.get(id=user_id)
                    prof = get_or_create_profile(target_user)
                    prof.subscription_tier = new_tier
                    prof.save(update_fields=['subscription_tier'])
                    return JsonResponse({"success": True, "message": "Subscription tier updated."})
                except Exception as e:
                    return JsonResponse({"success": False, "error": str(e)}, status=400)

            elif action == "update_site_watermark":
                site_settings = GlobalSiteSettings.get_settings()
                site_settings.site_watermark_enabled = request.POST.get("site_watermark_enabled") == "1"
                site_settings.site_brand_name = request.POST.get("site_brand_name", "KSHAN").strip()
                try:
                    site_settings.site_watermark_opacity = float(request.POST.get("site_watermark_opacity", 0.85))
                except Exception:
                    pass
                if request.FILES.get("site_watermark_logo"):
                    site_settings.site_watermark_logo = request.FILES.get("site_watermark_logo")
                elif request.POST.get("remove_site_logo") == "1":
                    if site_settings.site_watermark_logo:
                        try:
                            site_settings.site_watermark_logo.delete(save=False)
                        except Exception:
                            pass
                    site_settings.site_watermark_logo = None
                site_settings.save()
                return JsonResponse({"success": True, "message": "Site-wide watermark settings updated successfully."})

        # Fetch comprehensive database stats
        all_events = Event.objects.select_related('photographer', 'photographer__profile').order_by('-created_at')
        all_users = User.objects.select_related('profile').prefetch_related('events').order_by('-date_joined')
        all_orders = PaymentOrder.objects.select_related('event').order_by('-created_at')[:20]
        site_settings = GlobalSiteSettings.get_settings()
        
        total_events = all_events.count()
        total_users = all_users.count()
        total_photos = Photo.objects.count()
        total_faces = Face.objects.count()
        
        # Calculate total revenue from paid orders
        revenue_data = PaymentOrder.objects.filter(status='paid').aggregate(total=Sum('amount'))
        total_revenue = revenue_data['total'] or 0

        return render(request, "master_super_admin.html", {
            "all_events": all_events,
            "all_users": all_users,
            "all_orders": all_orders,
            "site_settings": site_settings,
            "total_events": total_events,
            "total_users": total_users,
            "total_photos": total_photos,
            "total_faces": total_faces,
            "total_revenue": total_revenue,
        })

    # If POST request on login gate, verify passkey
    if request.method == "POST":
        entered_pass = request.POST.get("super_password", "").strip()
        if entered_pass == "thepranit":
            request.session["is_master_superadmin"] = True
            return redirect("/thepranit/")
        else:
            return render(request, "master_super_admin_login.html", {
                "error": "Invalid master passkey. Access denied."
            })

    # Render login gate
    return render(request, "master_super_admin_login.html")


def thepranit_logout_view(request):
    """
    Clears the superadmin session and locks the panel.
    """
    if "is_master_superadmin" in request.session:
        del request.session["is_master_superadmin"]
    return redirect("/thepranit/")



