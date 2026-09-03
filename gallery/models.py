import json
from django.db import models
from django.contrib.auth.models import User

class PhotographerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    studio_name = models.CharField(max_length=255, blank=True, null=True, default="KSHAN Studio")
    display_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(max_length=255, blank=True, null=True)
    instagram = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_photo = models.ImageField(upload_to="profiles/", blank=True, null=True)
    studio_logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    
    # Watermark Settings
    watermark_enabled = models.BooleanField(default=False)
    watermark_opacity = models.FloatField(default=0.35)
    watermark_position = models.CharField(max_length=20, default='bottom-right', choices=[
        ('center', 'Center'),
        ('bottom-right', 'Bottom Right'),
        ('bottom-left', 'Bottom Left'),
        ('tile', 'Tiled Pattern')
    ])
    watermark_logo = models.ImageField(upload_to="watermarks/", blank=True, null=True)
    
    # Contact & Booking
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True, help_text="International format e.g. 919876543210")
    booking_url = models.URLField(max_length=255, blank=True, null=True, help_text="Booking inquiry link or website")

    # Subscription & Billing (Razorpay)
    subscription_tier = models.CharField(max_length=50, default='starter', choices=[
        ('starter', 'Starter (Free)'),
        ('pro_monthly', 'Pro Monthly (₹1,499/mo)'),
        ('studio_annual', 'Studio Annual (₹12,999/yr)'),
        ('event_pass', 'Event Pass (₹499/event)'),
    ])
    plan_expires_at = models.DateTimeField(blank=True, null=True)
    event_credits = models.IntegerField(default=1)

    # Onboarding Status
    onboarding_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.studio_name or self.user.username

    def to_dict(self):
        return {
            "studio_name": self.studio_name or "KSHAN Studio",
            "display_name": self.display_name or self.user.first_name or self.user.username,
            "phone": self.phone or "",
            "city": self.city or "",
            "website": self.website or "",
            "instagram": self.instagram or "",
            "bio": self.bio or "",
            "profile_photo_url": self.profile_photo.url if self.profile_photo else "",
            "studio_logo_url": self.studio_logo.url if self.studio_logo else "",
            "watermark_enabled": self.watermark_enabled,
            "watermark_position": self.watermark_position,
            "watermark_opacity": self.watermark_opacity,
            "onboarding_completed": self.onboarding_completed,
            "whatsapp_number": self.whatsapp_number or "",
            "booking_url": self.booking_url or "",
            "subscription_tier": self.subscription_tier,
            "plan_expires_at": self.plan_expires_at.strftime("%Y-%m-%d") if self.plan_expires_at else None,
            "event_credits": self.event_credits,
        }


class Event(models.Model):
    EVENT_TYPE_CHOICES = [
        ('wedding', 'Wedding'),
        ('engagement', 'Engagement'),
        ('pre_wedding', 'Pre-Wedding'),
        ('birthday', 'Birthday'),
        ('college', 'College Event'),
        ('corporate', 'Corporate'),
        ('sports', 'Sports'),
        ('festival', 'Festival'),
        ('conference', 'Conference'),
        ('school', 'School Event'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('live', 'LIVE'),
        ('processing', 'PROCESSING'),
        ('draft', 'DRAFT'),
        ('ended', 'ENDED'),
    ]

    ACCESS_MODE_CHOICES = [
        ('public', 'Open Event (Public QR)'),
        ('pin', 'PIN Protected'),
        ('face_only', 'Face Search Only'),
        ('private', 'Private Direct Link Only'),
    ]

    THEME_CHOICES = [
        ('editorial', 'Editorial Luxury'),
        ('minimal', 'Clean Minimal'),
        ('cinema', 'Cinematic Dark'),
        ('wedding', 'Warm Romantic'),
        ('classic', 'Classic Studio'),
    ]

    DOWNLOAD_CHOICES = [
        ('original', 'High-Res Originals & Batch ZIP'),
        ('compressed', 'Web Optimized Only'),
        ('disabled', 'View Only (Downloads Disabled)'),
    ]

    photographer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events', default=1, db_index=True)
    name = models.CharField(max_length=255)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, default='wedding')
    event_date = models.CharField(max_length=50, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    event_code = models.CharField(max_length=50, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='live')
    cover_photo = models.ForeignKey('Photo', on_delete=models.SET_NULL, null=True, blank=True, related_name='covered_events')
    
    # Appearance & Features
    theme = models.CharField(max_length=30, choices=THEME_CHOICES, default='editorial')
    public_gallery_enabled = models.BooleanField(default=True)
    access_mode = models.CharField(max_length=20, choices=ACCESS_MODE_CHOICES, default='public')
    access_pin = models.CharField(max_length=128, blank=True, null=True)
    download_permission = models.CharField(max_length=20, choices=DOWNLOAD_CHOICES, default='original')
    allow_favorites = models.BooleanField(default=True)
    allow_client_proofing = models.BooleanField(default=True)
    
    # New Event Settings (Module G & Monetization)
    password = models.CharField(max_length=128, blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    allow_guest_download = models.BooleanField(default=True)
    allow_guest_upload = models.BooleanField(default=False)
    watermark_enabled = models.BooleanField(default=False)
    visibility = models.CharField(max_length=20, choices=[('public', 'Public'), ('invite', 'Invite Only'), ('private', 'Private')], default='public')
    
    # Guest Monetization (Razorpay)
    pricing_model = models.CharField(max_length=30, choices=[
        ('free', 'Free Downloads'),
        ('paid_per_photo', 'Paid Per Photo'),
        ('paid_full_event', 'Paid Full Album Unlock'),
    ], default='free')
    price_per_photo = models.IntegerField(default=0, help_text="Price in INR for single photo download")
    price_full_event = models.IntegerField(default=0, help_text="Price in INR for full event photo bundle")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.event_code})"


    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "event_type": self.event_type,
            "event_type_display": self.get_event_type_display(),
            "event_date": self.event_date or "",
            "location": self.location or "",
            "description": self.description or "",
            "event_code": self.event_code,
            "status": self.status,
            "status_display": self.get_status_display(),
            "theme": self.theme,
            "public_gallery_enabled": self.public_gallery_enabled,
            "access_mode": self.access_mode,
            "download_permission": self.download_permission,
            "password": self.password or "",
            "expires_at": self.expires_at.strftime("%Y-%m-%d") if self.expires_at else "",
            "allow_guest_download": self.allow_guest_download,
            "allow_guest_upload": self.allow_guest_upload,
            "watermark_enabled": self.watermark_enabled,
            "visibility": self.visibility,
            "pricing_model": self.pricing_model,
            "price_per_photo": self.price_per_photo,
            "price_full_event": self.price_full_event,
            "cover_photo_url": self.cover_photo.thumbnail_url if self.cover_photo else "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "photo_count": self.photos.count(),
            "face_count": self.faces.count()
        }


class SubEvent(models.Model):
    """Ceremony / Sub-Folder within an event (Haldi, Sangeet, Reception etc.)"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='sub_events')
    name = models.CharField(max_length=100)  # e.g. "Haldi", "Sangeet"
    slug = models.CharField(max_length=100, db_index=True)  # url-safe slug
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        unique_together = ('event', 'slug')

    def __str__(self):
        return f"{self.event.name} / {self.name}"


class Photo(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='photos', db_index=True)
    sub_event = models.ForeignKey(SubEvent, on_delete=models.SET_NULL, null=True, blank=True, related_name='photos')
    filename = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    thumbnail_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.IntegerField(default=0)
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    file_hash = models.CharField(max_length=64, db_index=True, blank=True, null=True)
    is_highlight = models.BooleanField(default=False, db_index=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processing_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    error_message = models.TextField(blank=True, null=True)

    # Upload Source (Module D)
    UPLOADED_BY_CHOICES = [
        ('official', 'Official'),
        ('guest', 'Guest'),
        ('team', 'Team')
    ]
    uploaded_by_type = models.CharField(max_length=20, choices=UPLOADED_BY_CHOICES, default='official', db_index=True)
    uploaded_by_guest_name = models.CharField(max_length=255, blank=True, null=True)
    
    # EXIF Data (Module A)
    exif_camera = models.CharField(max_length=255, blank=True, null=True)
    exif_lens = models.CharField(max_length=255, blank=True, null=True)
    exif_focal_length = models.CharField(max_length=100, blank=True, null=True)
    exif_aperture = models.CharField(max_length=100, blank=True, null=True)
    exif_exposure_time = models.CharField(max_length=100, blank=True, null=True)
    exif_iso = models.CharField(max_length=100, blank=True, null=True)
    exif_date_taken = models.DateTimeField(blank=True, null=True)


    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['event', 'processing_status']),
            models.Index(fields=['event', 'file_hash']),
            models.Index(fields=['event', 'is_highlight']),
        ]

    def __str__(self):
        return f"{self.original_filename} [{self.processing_status}]"

    @property
    def thumbnail_url(self):
        return f"/api/photos/{self.id}/thumbnail/"

    @property
    def view_url(self):
        return f"/api/photos/{self.id}/view/"

    def to_dict(self):
        return {
            "id": self.id,
            "event_id": self.event_id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_size": self.file_size,
            "width": self.width,
            "height": self.height,
            "is_highlight": self.is_highlight,
            "uploaded_at": self.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if self.uploaded_at else "",
            "processing_status": self.processing_status,
            "error_message": self.error_message,
            "thumbnail_url": self.thumbnail_url,
            "view_url": self.view_url,
            "face_count": self.faces.count(),
            "uploaded_by_type": self.uploaded_by_type,
            "uploaded_by_guest_name": self.uploaded_by_guest_name,
            "exif_camera": self.exif_camera,
            "exif_lens": self.exif_lens,
            "exif_focal_length": self.exif_focal_length,
            "exif_aperture": self.exif_aperture,
            "exif_exposure_time": self.exif_exposure_time,
            "exif_iso": self.exif_iso,
            "exif_date_taken": self.exif_date_taken.strftime("%b %d, %Y, %I:%M %p") if self.exif_date_taken else ""
        }


class Album(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='albums')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    cover_photo = models.ForeignKey('Photo', on_delete=models.SET_NULL, null=True, blank=True, related_name='covered_albums')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event.name} / Album: {self.name}"

class AlbumPhoto(models.Model):
    album = models.ForeignKey(Album, on_delete=models.CASCADE, related_name='album_photos')
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='in_albums')
    order = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'added_at']
        unique_together = ('album', 'photo')


class Face(models.Model):
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='faces', db_index=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='faces', db_index=True)
    embedding = models.BinaryField()  # 512-d float32 L2-normalized vector BLOB
    confidence = models.FloatField(default=1.0)
    bounding_box = models.TextField(blank=True, null=True)  # JSON [x1, y1, x2, y2]
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['event', 'photo']),
        ]

    def get_bbox(self):
        if self.bounding_box:
            try:
                return json.loads(self.bounding_box)
            except Exception:
                return []
        return []


class Collection(models.Model):
    """Client Proofing & Selection Collection (e.g. Wedding Album Selection)."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='collections')
    title = models.CharField(max_length=255, default="Album Selection")
    access_token = models.CharField(max_length=64, unique=True, db_index=True)
    target_count = models.IntegerField(default=80)
    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(blank=True, null=True)
    client_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.event.name})"


class CollectionItem(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='collection_items')
    is_selected = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)
    comment = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('collection', 'photo')


class SearchLog(models.Model):
    """Privacy-conscious face search log (NO selfies stored)."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='search_logs', db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    number_of_matches = models.IntegerField(default=0)
    anonymous_session_id = models.CharField(max_length=64, blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']


class DownloadLog(models.Model):
    """Tracks downloads for photographer analytics."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='download_logs', db_index=True)
    photo = models.ForeignKey(Photo, on_delete=models.SET_NULL, null=True, blank=True, related_name='download_logs')
    is_batch = models.BooleanField(default=False)
    batch_count = models.IntegerField(default=1)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']


class GuestRegistration(models.Model):
    """Captures guest name/phone/email when they register before face search."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='guest_registrations', db_index=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    anonymous_session_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-registered_at']

    def __str__(self):
        return f"{self.name} @ {self.event.name}"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone or "",
            "email": self.email or "",
            "registered_at": self.registered_at.strftime("%Y-%m-%d %H:%M") if self.registered_at else "",
        }


class GuestFavorite(models.Model):
    """Guest hearts/favorites for photos (session-based, privacy-friendly)."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='guest_favorites', db_index=True)
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name='guest_favorites')
    anonymous_session_id = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('photo', 'anonymous_session_id')
        ordering = ['-created_at']


class PaymentOrder(models.Model):
    """Tracks all Razorpay Orders and Payments for SaaS Plans, Event Passes, and Guest Unlocks."""
    PAYMENT_TYPE_CHOICES = [
        ('photographer_plan', 'Photographer Subscription Plan'),
        ('event_pass', 'Photographer Event Pass'),
        ('guest_photo_download', 'Guest Single Photo Download'),
        ('guest_event_unlock', 'Guest Full Event Album Unlock'),
        ('album_proofing_deposit', 'Client Proofing Album Deposit'),
    ]

    STATUS_CHOICES = [
        ('created', 'Created'),
        ('paid', 'Paid / Captured'),
        ('failed', 'Failed / Cancelled'),
    ]

    order_id = models.CharField(max_length=100, unique=True, db_index=True, help_text="Razorpay Order ID (order_xxx)")
    payment_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="Razorpay Payment ID (pay_xxx)")
    signature = models.CharField(max_length=255, blank=True, null=True)
    
    payment_type = models.CharField(max_length=50, choices=PAYMENT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', db_index=True)
    
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text="Amount in INR")
    currency = models.CharField(max_length=10, default='INR')
    
    # Associated Entities
    user = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='payment_orders')
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, blank=True, null=True, related_name='payment_orders')
    photo = models.ForeignKey(Photo, on_delete=models.SET_NULL, blank=True, null=True, related_name='payment_orders')
    collection = models.ForeignKey(Collection, on_delete=models.SET_NULL, blank=True, null=True, related_name='payment_orders')
    
    guest_session_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    guest_email = models.EmailField(max_length=255, blank=True, null=True)
    guest_phone = models.CharField(max_length=50, blank=True, null=True)
    
    notes = models.TextField(blank=True, null=True, help_text="JSON or descriptive notes")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_id} - {self.payment_type} - {self.status} (₹{self.amount})"

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "payment_id": self.payment_id or "",
            "payment_type": self.payment_type,
            "payment_type_display": self.get_payment_type_display(),
            "status": self.status,
            "amount": float(self.amount),
            "currency": self.currency,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "paid_at": self.paid_at.strftime("%Y-%m-%d %H:%M") if self.paid_at else "",
        }


class GuestPurchase(models.Model):
    """Grants download rights to a guest session/photo upon verified payment."""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='guest_purchases')
    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, blank=True, null=True, related_name='guest_purchases')
    anonymous_session_id = models.CharField(max_length=64, db_index=True)
    payment_order = models.ForeignKey(PaymentOrder, on_delete=models.SET_NULL, blank=True, null=True, related_name='granted_purchases')
    is_full_event = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event', 'anonymous_session_id']),
            models.Index(fields=['photo', 'anonymous_session_id']),
        ]

    def __str__(self):
        return f"Purchase: {self.anonymous_session_id} @ {self.event.name} (Full: {self.is_full_event})"


class WhatsAppOTPVerification(models.Model):
    """Stores one-time verification tokens sent via Meta WhatsApp Cloud API."""
    PURPOSE_CHOICES = [
        ('login', 'Studio Passwordless Login'),
        ('signup', 'Studio Registration'),
        ('guest_register', 'Guest Verification'),
    ]

    phone = models.CharField(max_length=30, db_index=True)
    otp_code = models.CharField(max_length=10)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES, default='login')
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP {self.otp_code} for {self.phone} ({self.purpose})"


class GlobalSiteSettings(models.Model):
    """
    Global software site settings managed by master super admin (/thepranit).
    Includes default bottom-right site logo watermark across all event photos.
    """
    site_watermark_enabled = models.BooleanField(default=True, help_text="Always watermark site logo on bottom-right of photos")
    site_watermark_logo = models.ImageField(upload_to="system/watermarks/", blank=True, null=True)
    site_watermark_opacity = models.FloatField(default=0.85)
    site_brand_name = models.CharField(max_length=100, default="KSHAN")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return f"Global Site Settings (Watermark: {self.site_watermark_enabled})"


