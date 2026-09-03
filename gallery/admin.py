from django.contrib import admin
from .models import PhotographerProfile, Event, Photo, Face, SearchLog, DownloadLog

@admin.register(PhotographerProfile)
class PhotographerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'studio_name', 'display_name', 'phone', 'city', 'created_at')
    search_fields = ('user__username', 'studio_name', 'display_name', 'phone')

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'event_code', 'photographer', 'event_type', 'status', 'event_date', 'created_at')
    list_filter = ('event_type', 'status', 'photographer')
    search_fields = ('name', 'event_code', 'photographer__username')

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'event', 'processing_status', 'is_highlight', 'uploaded_at')
    list_filter = ('processing_status', 'is_highlight', 'event')
    search_fields = ('original_filename', 'filename')

@admin.register(Face)
class FaceAdmin(admin.ModelAdmin):
    list_display = ('id', 'photo', 'event', 'confidence', 'created_at')
    list_filter = ('event',)

@admin.register(SearchLog)
class SearchLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'number_of_matches', 'timestamp')
    list_filter = ('event', 'timestamp')

@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'is_batch', 'batch_count', 'timestamp')
    list_filter = ('event', 'is_batch', 'timestamp')
