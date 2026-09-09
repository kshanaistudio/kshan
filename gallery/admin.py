import json
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    PhotographerProfile,
    Event,
    SubEvent,
    Photo,
    Face,
    Album,
    AlbumPhoto,
    Collection,
    CollectionItem,
    SearchLog,
    DownloadLog,
    GuestRegistration,
    GuestFavorite,
    PaymentOrder,
    GuestPurchase,
    WhatsAppOTPVerification,
    GlobalSiteSettings
)

# -----------------------------------------------------------------------------
# Admin Site Branding
# -----------------------------------------------------------------------------
admin.site.site_header = "KSHAN AI — Master Administration"
admin.site.site_title = "KSHAN Admin Console"
admin.site.index_title = "Platform & Operations Control"


# -----------------------------------------------------------------------------
# Inlines
# -----------------------------------------------------------------------------
class SubEventInline(admin.TabularInline):
    model = SubEvent
    extra = 1
    fields = ('name', 'slug', 'order', 'created_at')
    readonly_fields = ('created_at',)


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0
    fields = ('thumbnail_preview', 'original_filename', 'processing_status', 'is_highlight', 'uploaded_by_type', 'uploaded_at')
    readonly_fields = ('thumbnail_preview', 'original_filename', 'processing_status', 'uploaded_at')
    can_delete = True
    show_change_link = True

    def thumbnail_preview(self, obj):
        if obj.id:
            return format_html(
                '<img src="/api/photos/{}/thumbnail/" style="width: 45px; height: 45px; object-fit: cover; border-radius: 6px;" />',
                obj.id
            )
        return "-"
    thumbnail_preview.short_description = "Preview"


class FaceInline(admin.TabularInline):
    model = Face
    extra = 0
    fields = ('id', 'confidence', 'bounding_box', 'created_at')
    readonly_fields = ('id', 'confidence', 'bounding_box', 'created_at')
    can_delete = True


class AlbumPhotoInline(admin.TabularInline):
    model = AlbumPhoto
    extra = 1
    fields = ('photo', 'order', 'added_at')
    readonly_fields = ('added_at',)


class CollectionItemInline(admin.TabularInline):
    model = CollectionItem
    extra = 0
    fields = ('photo', 'is_selected', 'is_favorite', 'comment', 'updated_at')
    readonly_fields = ('updated_at',)


# -----------------------------------------------------------------------------
# Model Admins
# -----------------------------------------------------------------------------
@admin.register(PhotographerProfile)
class PhotographerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'studio_name', 'display_name', 'phone', 'city', 'subscription_badge', 'event_credits', 'created_at')
    list_filter = ('subscription_tier', 'watermark_enabled', 'onboarding_completed')
    search_fields = ('user__username', 'user__email', 'studio_name', 'display_name', 'phone', 'city')
    readonly_fields = ('created_at',)
    fieldsets = (
        ("Studio Identity", {
            "fields": ("user", "studio_name", "display_name", "phone", "city", "website", "instagram", "bio", "profile_photo", "studio_logo")
        }),
        ("Subscription & Credits", {
            "fields": ("subscription_tier", "event_credits", "plan_expires_at", "onboarding_completed")
        }),
        ("Watermark Configuration", {
            "fields": ("watermark_enabled", "watermark_position", "watermark_opacity", "watermark_logo")
        }),
        ("Contact & Direct Booking", {
            "fields": ("whatsapp_number", "booking_url", "created_at")
        }),
    )

    def subscription_badge(self, obj):
        colors = {
            'starter': '#6B7280',
            'pro_monthly': '#3B82F6',
            'studio_annual': '#10B981',
            'event_pass': '#8B5CF6'
        }
        color = colors.get(obj.subscription_tier, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 12px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            obj.get_subscription_tier_display()
        )
    subscription_badge.short_description = "Plan"


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'event_code', 'photographer', 'event_type', 'status_badge', 'photo_count', 'face_count', 'pricing_model', 'event_date', 'created_at')
    list_filter = ('status', 'event_type', 'pricing_model', 'public_gallery_enabled', 'visibility', 'theme')
    search_fields = ('name', 'event_code', 'photographer__username', 'photographer__profile__studio_name', 'location')
    date_hierarchy = 'created_at'
    inlines = [SubEventInline, PhotoInline]
    readonly_fields = ('event_code', 'created_at')
    actions = ['mark_as_live', 'mark_as_ended', 'enable_guest_downloads']

    fieldsets = (
        ("Event Overview", {
            "fields": ("name", "event_code", "photographer", "event_type", "status", "event_date", "location", "description", "cover_photo")
        }),
        ("Appearance & Theme", {
            "fields": ("theme", "public_gallery_enabled", "visibility", "access_mode", "access_pin", "password", "expires_at")
        }),
        ("Guest Privileges & Proofing", {
            "fields": ("download_permission", "allow_guest_download", "allow_guest_upload", "allow_favorites", "allow_client_proofing", "watermark_enabled")
        }),
        ("Monetization & Pricing (Razorpay)", {
            "fields": ("pricing_model", "price_per_photo", "price_full_event")
        }),
        ("Timestamps", {
            "fields": ("created_at",)
        }),
    )

    def photo_count(self, obj):
        return obj.photos.count()
    photo_count.short_description = "Photos"

    def face_count(self, obj):
        return obj.faces.count()
    face_count.short_description = "Indexed Faces"

    def status_badge(self, obj):
        colors = {
            'live': '#10B981',
            'processing': '#F59E0B',
            'draft': '#6B7280',
            'ended': '#EF4444'
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"

    @admin.action(description="Set status to LIVE")
    def mark_as_live(self, request, queryset):
        queryset.update(status='live')

    @admin.action(description="Set status to ENDED")
    def mark_as_ended(self, request, queryset):
        queryset.update(status='ended')

    @admin.action(description="Enable Free Guest Downloads")
    def enable_guest_downloads(self, request, queryset):
        queryset.update(allow_guest_download=True, pricing_model='free')


@admin.register(SubEvent)
class SubEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'slug', 'order', 'photo_count', 'created_at')
    list_filter = ('event',)
    search_fields = ('name', 'slug', 'event__name')
    ordering = ('event', 'order')

    def photo_count(self, obj):
        return obj.photos.count()
    photo_count.short_description = "Photos"


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('preview_image', 'original_filename', 'event', 'sub_event', 'processing_status_badge', 'faces_detected', 'is_highlight', 'uploaded_by_type', 'file_size_display', 'uploaded_at')
    list_filter = ('processing_status', 'is_highlight', 'uploaded_by_type', 'event', 'uploaded_at')
    search_fields = ('original_filename', 'filename', 'event__name', 'event__event_code', 'uploaded_by_guest_name')
    date_hierarchy = 'uploaded_at'
    inlines = [FaceInline]
    readonly_fields = ('preview_large', 'file_size', 'width', 'height', 'file_hash', 'uploaded_at')
    actions = ['mark_as_highlight', 'remove_highlight', 'reset_to_pending']

    fieldsets = (
        ("Photo Information", {
            "fields": ("preview_large", "event", "sub_event", "original_filename", "filename", "file_path", "thumbnail_path")
        }),
        ("Processing & AI Status", {
            "fields": ("processing_status", "is_highlight", "error_message")
        }),
        ("Metadata & Camera EXIF", {
            "fields": ("file_size", "width", "height", "file_hash", "exif_camera", "exif_lens", "exif_focal_length", "exif_aperture", "exif_exposure_time", "exif_iso", "exif_date_taken")
        }),
        ("Upload Source", {
            "fields": ("uploaded_by_type", "uploaded_by_guest_name", "uploaded_at")
        }),
    )

    def preview_image(self, obj):
        return format_html(
            '<img src="/api/photos/{}/thumbnail/" style="width: 45px; height: 45px; object-fit: cover; border-radius: 6px; border: 1px solid #374151;" />',
            obj.id
        )
    preview_image.short_description = "Thumb"

    def preview_large(self, obj):
        return format_html(
            '<a href="/api/photos/{}/view/" target="_blank"><img src="/api/photos/{}/thumbnail/" style="max-width: 320px; max-height: 240px; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);" /><br><span style="font-size: 11px;">Click to view full image</span></a>',
            obj.id, obj.id
        )
    preview_large.short_description = "Image Preview"

    def file_size_display(self, obj):
        if obj.file_size:
            mb = obj.file_size / (1024 * 1024)
            return f"{mb:.2f} MB"
        return "0 KB"
    file_size_display.short_description = "Size"

    def faces_detected(self, obj):
        count = obj.faces.count()
        return format_html('<span style="font-weight: 700; color: #6366F1;">{} faces</span>', count)
    faces_detected.short_description = "AI Faces"

    def processing_status_badge(self, obj):
        colors = {
            'completed': '#10B981',
            'processing': '#3B82F6',
            'pending': '#F59E0B',
            'failed': '#EF4444'
        }
        color = colors.get(obj.processing_status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 7px; border-radius: 4px; font-weight: 600; font-size: 11px;">{}</span>',
            color,
            obj.get_processing_status_display()
        )
    processing_status_badge.short_description = "AI Status"

    @admin.action(description="Mark selected photos as Highlight")
    def mark_as_highlight(self, request, queryset):
        queryset.update(is_highlight=True)

    @admin.action(description="Remove Highlight from selected photos")
    def remove_highlight(self, request, queryset):
        queryset.update(is_highlight=False)

    @admin.action(description="Reset processing status to Pending (re-index)")
    def reset_to_pending(self, request, queryset):
        queryset.update(processing_status='pending', error_message=None)


@admin.register(Face)
class FaceAdmin(admin.ModelAdmin):
    list_display = ('id', 'photo_preview', 'photo', 'event', 'confidence_display', 'bounding_box_display', 'created_at')
    list_filter = ('event',)
    search_fields = ('photo__original_filename', 'event__name')
    readonly_fields = ('embedding_size', 'created_at')

    def photo_preview(self, obj):
        return format_html(
            '<img src="/api/photos/{}/thumbnail/" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px;" />',
            obj.photo_id
        )
    photo_preview.short_description = "Photo"

    def confidence_display(self, obj):
        return f"{obj.confidence * 100:.1f}%"
    confidence_display.short_description = "Confidence"

    def bounding_box_display(self, obj):
        return obj.bounding_box or "Full Image"
    bounding_box_display.short_description = "BBox"

    def embedding_size(self, obj):
        if obj.embedding:
            return f"{len(obj.embedding)} bytes (512-D float32 vector)"
        return "0 bytes"
    embedding_size.short_description = "Embedding Vector"


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'photo_count', 'created_at')
    list_filter = ('event',)
    search_fields = ('name', 'event__name')
    inlines = [AlbumPhotoInline]

    def photo_count(self, obj):
        return obj.album_photos.count()
    photo_count.short_description = "Total Photos"


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ('title', 'event', 'target_count', 'selected_count', 'is_submitted', 'submitted_at', 'created_at')
    list_filter = ('is_submitted', 'event')
    search_fields = ('title', 'event__name', 'access_token')
    inlines = [CollectionItemInline]
    readonly_fields = ('access_token', 'created_at')

    def selected_count(self, obj):
        selected = obj.items.filter(is_selected=True).count()
        total = obj.items.count()
        return f"{selected} / {total} photos"
    selected_count.short_description = "Client Selected"


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ('order_id', 'payment_type_badge', 'amount_display', 'status_badge', 'user', 'event', 'guest_email', 'guest_phone', 'created_at', 'paid_at')
    list_filter = ('status', 'payment_type', 'created_at')
    search_fields = ('order_id', 'payment_id', 'guest_email', 'guest_phone', 'user__username', 'event__name')
    date_hierarchy = 'created_at'
    readonly_fields = ('order_id', 'payment_id', 'signature', 'created_at', 'paid_at')
    actions = ['mark_as_paid', 'mark_as_failed']

    def amount_display(self, obj):
        return f"₹{obj.amount:.2f}"
    amount_display.short_description = "Amount"

    def payment_type_badge(self, obj):
        return obj.get_payment_type_display()
    payment_type_badge.short_description = "Type"

    def status_badge(self, obj):
        colors = {
            'paid': '#10B981',
            'created': '#F59E0B',
            'failed': '#EF4444'
        }
        color = colors.get(obj.status, '#6B7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 9px; border-radius: 10px; font-weight: 700; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Payment Status"

    @admin.action(description="Mark selected orders as Paid")
    def mark_as_paid(self, request, queryset):
        from django.utils import timezone
        queryset.update(status='paid', paid_at=timezone.now())

    @admin.action(description="Mark selected orders as Failed")
    def mark_as_failed(self, request, queryset):
        queryset.update(status='failed')


@admin.register(GuestPurchase)
class GuestPurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'photo', 'is_full_event', 'anonymous_session_id', 'payment_order', 'created_at')
    list_filter = ('is_full_event', 'event', 'created_at')
    search_fields = ('anonymous_session_id', 'event__name', 'payment_order__order_id')


@admin.register(GuestRegistration)
class GuestRegistrationAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'email', 'event', 'registered_at')
    list_filter = ('event', 'registered_at')
    search_fields = ('name', 'phone', 'email', 'event__name')
    date_hierarchy = 'registered_at'


@admin.register(GuestFavorite)
class GuestFavoriteAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'photo', 'anonymous_session_id', 'created_at')
    list_filter = ('event', 'created_at')


@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'number_of_matches', 'anonymous_session_id', 'timestamp')
    list_filter = ('event', 'timestamp')
    date_hierarchy = 'timestamp'


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'photo', 'is_batch', 'batch_count', 'timestamp')
    list_filter = ('is_batch', 'event', 'timestamp')
    date_hierarchy = 'timestamp'


@admin.register(WhatsAppOTPVerification)
class WhatsAppOTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('phone', 'otp_code', 'purpose', 'is_verified', 'expires_at', 'created_at')
    list_filter = ('purpose', 'is_verified', 'created_at')
    search_fields = ('phone', 'otp_code')


@admin.register(GlobalSiteSettings)
class GlobalSiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('site_brand_name', 'site_watermark_enabled', 'site_watermark_opacity', 'updated_at')

    def has_add_permission(self, request):
        return GlobalSiteSettings.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False
