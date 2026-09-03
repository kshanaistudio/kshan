from django.urls import path
from . import views

urlpatterns = [
    # Public Guest HTML Views
    path('', views.home_view, name='home'),
    path('event/<str:event_code>/', views.event_view, name='event_view'),
    path('event/<str:event_code>', views.event_view),
    path('event/<str:event_code>/gallery/', views.event_gallery_view, name='event_gallery'),
    path('event/<str:event_code>/gallery', views.event_gallery_view),
    path('gallery/<str:event_code>/', views.event_gallery_view, name='event_gallery_alias'),
    path('gallery/<str:event_code>', views.event_gallery_view),

    # Photographer Auth Views
    path('signup/', views.signup_view, name='signup'),
    path('signup', views.signup_view),
    path('login/', views.login_view, name='login'),
    path('login', views.login_view),
    path('logout/', views.logout_view, name='logout'),
    path('logout', views.logout_view),
    path('api/auth/whatsapp/send-otp/', views.send_whatsapp_otp_api, name='send_whatsapp_otp'),
    path('api/auth/whatsapp/send-otp', views.send_whatsapp_otp_api),
    path('api/auth/whatsapp/verify-otp/', views.verify_whatsapp_otp_api, name='verify_whatsapp_otp'),
    path('api/auth/whatsapp/verify-otp', views.verify_whatsapp_otp_api),

    # Master Super Admin Route (/thepranit)
    path('thepranit/', views.thepranit_admin_view, name='thepranit_admin'),
    path('thepranit', views.thepranit_admin_view),
    path('thepranit/logout/', views.thepranit_logout_view, name='thepranit_logout'),
    path('thepranit/logout', views.thepranit_logout_view),
    
    # Legacy admin redirect to new login
    path('admin/login/', views.login_view),
    path('admin/logout/', views.logout_view),

    # Photographer Dashboard & Workspace
    path('admin/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin', views.admin_dashboard_view),
    path('studio/', views.admin_dashboard_view, name='studio_dashboard'),
    path('studio', views.admin_dashboard_view),
    path('studio/events/', views.studio_events_view, name='studio_events'),
    path('studio/events', views.studio_events_view),
    path('studio/analytics/', views.studio_analytics_view, name='studio_analytics'),
    path('studio/analytics', views.studio_analytics_view),
    path('studio/proofing/', views.studio_proofing_view, name='studio_proofing'),
    path('studio/proofing', views.studio_proofing_view),
    path('admin/events/<str:event_code>/', views.admin_event_view, name='admin_event_view'),
    path('admin/events/<str:event_code>', views.admin_event_view),
    path('admin/profile/', views.admin_profile_view, name='admin_profile'),
    path('admin/profile', views.admin_profile_view),
    path('admin/settings/', views.admin_settings_view, name='admin_settings'),
    path('admin/settings', views.admin_settings_view),
    path('admin/events/<str:event_code>/share/', views.event_share_view, name='admin_event_share'),
    path('admin/events/<str:event_code>/share', views.event_share_view),

    # Public REST APIs for Guest App
    path('api/events/<int:event_id>/search-face/', views.search_face_api, name='search_face'),
    path('api/events/<int:event_id>/search-face', views.search_face_api),
    path('api/events/<str:event_code>/search/', views.search_face_api, name='search_face_code'),
    path('api/events/<str:event_code>/search', views.search_face_api),
    path('api/events/<str:event_code>/search-face/', views.search_face_api),
    path('api/events/<str:event_code>/search-face', views.search_face_api),
    path('api/events/<str:event_code>/verify-pin/', views.event_verify_pin_api, name='verify_pin'),
    path('api/events/<str:event_code>/highlights/', views.public_highlights_api, name='public_highlights'),

    # Photographer REST APIs
    path('api/events/<int:event_id>/photos/', views.upload_photos_api, name='upload_photos'),
    path('api/events/<int:event_id>/photos', views.upload_photos_api),
    path('api/events/<str:event_code>/photos/', views.upload_photos_api, name='upload_photos_by_code'),
    path('api/events/<str:event_code>/photos', views.upload_photos_api),

    path('api/admin/events/<int:event_id>/progress/', views.get_progress_api, name='get_progress'),
    path('api/admin/events/<int:event_id>/progress', views.get_progress_api),

    path('api/admin/events/<int:event_id>/reprocess-failed/', views.reprocess_failed_api, name='reprocess_failed'),
    path('api/admin/events/<int:event_id>/reprocess-failed', views.reprocess_failed_api),

    path('api/admin/events/<int:event_id>/delete-photos/', views.delete_all_photos_api, name='delete_all_photos'),
    path('api/admin/events/<int:event_id>/delete-photos', views.delete_all_photos_api),

    path('api/admin/events/<int:event_id>/settings/', views.update_event_settings_api, name='update_event_settings'),
    path('api/admin/events/<int:event_id>/set-cover/<int:photo_id>/', views.set_event_cover_api, name='set_event_cover'),
    path('api/admin/photos/<int:photo_id>/toggle-highlight/', views.toggle_highlight_photo_api, name='toggle_highlight'),

    path('api/admin/photos/<int:photo_id>/', views.delete_photo_api, name='delete_photo'),
    path('api/admin/photos/<int:photo_id>', views.delete_photo_api),

    path('api/admin/events/', views.create_event_api, name='create_event'),
    path('api/admin/events', views.create_event_api),
    path('api/admin/events/<int:event_id>/', views.delete_event_api, name='delete_event'),
    path('api/admin/events/<int:event_id>', views.delete_event_api),

    # Photo Assets & Downloads
    path('api/photos/<int:photo_id>/thumbnail/', views.get_thumbnail_view, name='photo_thumbnail'),
    path('api/photos/<int:photo_id>/thumbnail', views.get_thumbnail_view),

    path('api/photos/<int:photo_id>/view/', views.view_photo_full, name='photo_view'),
    path('api/photos/<int:photo_id>/view', views.view_photo_full),

    path('api/photos/<int:photo_id>/download/', views.download_photo_view, name='photo_download'),
    path('api/photos/<int:photo_id>/download', views.download_photo_view),

    path('api/photos/download-batch/', views.download_batch_zip, name='download_batch_zip'),
    path('api/photos/download-batch', views.download_batch_zip),

    # QR Generation & AI Tools
    path('api/events/<str:event_code>/qr/', views.event_qr_code_view, name='event_qr_code'),
    path('api/events/<str:event_code>/qr', views.event_qr_code_view),
    path('api/tools/remove-bg/', views.remove_background_api, name='remove_background_api'),
    path('api/tools/remove-bg', views.remove_background_api),

    # Module 1: Sub-Event / Ceremony Folders
    path('api/admin/events/<int:event_id>/sub-events/', views.list_sub_events_api, name='list_sub_events'),
    path('api/admin/events/<int:event_id>/sub-events/create/', views.create_sub_event_api, name='create_sub_event'),
    path('api/admin/events/<int:event_id>/sub-events/<int:sub_event_id>/delete/', views.delete_sub_event_api, name='delete_sub_event'),
    path('api/admin/events/<int:event_id>/sub-events/<int:sub_event_id>/assign/', views.assign_photos_to_sub_event_api, name='assign_sub_event'),

    # Module 2: Guest RSVP Registration
    path('api/events/<str:event_code>/register/', views.guest_register_api, name='guest_register'),
    path('api/events/<str:event_code>/register', views.guest_register_api),
    path('api/admin/events/<int:event_id>/guests/', views.guest_list_api, name='guest_list'),
    path('studio/guests/', views.studio_guests_view, name='studio_guests'),
    path('studio/guests', views.studio_guests_view),

    # Module 3: WhatsApp Share
    path('api/events/<str:event_code>/whatsapp-link/', views.whatsapp_link_api, name='whatsapp_link'),
    path('api/events/<str:event_code>/whatsapp-link', views.whatsapp_link_api),

    # Module 4: Live Projector Beam Mode
    path('event/<str:event_code>/beam/', views.beam_view, name='beam_view'),
    path('event/<str:event_code>/beam', views.beam_view),
    path('api/events/<str:event_code>/beam-photos/', views.beam_photos_api, name='beam_photos'),
    path('api/events/<str:event_code>/beam-photos', views.beam_photos_api),

    # Module 5: Bulk Photo Actions & Info
    path('api/admin/events/<int:event_id>/photos/bulk-delete/', views.bulk_delete_photos_api, name='bulk_delete_photos'),
    path('api/admin/events/<int:event_id>/photos/bulk-highlight/', views.bulk_highlight_photos_api, name='bulk_highlight_photos'),
    path('api/admin/photos/<int:photo_id>/info/', views.photo_info_api, name='photo_info'),
    path('api/admin/photos/<int:photo_id>/info', views.photo_info_api),

    # Module 6: Guest Favorites / Hearting
    path('api/events/<str:event_code>/favorite/', views.toggle_favorite_api, name='toggle_favorite'),
    path('api/events/<str:event_code>/favorite', views.toggle_favorite_api),
    path('api/events/<str:event_code>/favorites/', views.get_favorites_api, name='get_favorites'),
    path('api/events/<str:event_code>/favorites', views.get_favorites_api),

    # Module 7: Guest Photo Contribution (Plan 3.0 - Module H)
    path('api/events/<str:event_code>/guest-upload/', views.guest_upload_photo_api, name='guest_upload'),
    path('api/events/<str:event_code>/guest-upload', views.guest_upload_photo_api),

    # Module E: Album System
    path('api/admin/events/<int:event_id>/albums/', views.album_list_api, name='album_list'),
    path('api/admin/events/<int:event_id>/albums/create/', views.album_create_api, name='album_create'),
    path('api/admin/events/<int:event_id>/albums/<int:album_id>/', views.album_detail_api, name='album_detail'),
    path('api/admin/events/<int:event_id>/albums/<int:album_id>/delete/', views.album_delete_api, name='album_delete'),
    path('api/admin/events/<int:event_id>/albums/<int:album_id>/add-photos/', views.album_add_photos_api, name='album_add_photos'),
    path('api/admin/events/<int:event_id>/albums/<int:album_id>/remove-photo/<int:photo_id>/', views.album_remove_photo_api, name='album_remove_photo'),
    path('api/admin/events/<int:event_id>/albums/<int:album_id>/set-cover/', views.album_set_cover_api, name='album_set_cover'),
    path('event/<str:event_code>/album/<int:album_id>/', views.public_album_view, name='public_album_view'),

    # Razorpay Studio Billing & Subscriptions
    path('studio/billing/', views.studio_billing_view, name='studio_billing'),
    path('studio/billing', views.studio_billing_view),
    path('api/billing/create-subscription-order/', views.create_subscription_order_api, name='create_subscription_order'),
    path('api/billing/verify-subscription-payment/', views.verify_subscription_payment_api, name='verify_subscription_payment'),

    # Razorpay Guest Photo & Album Downloads
    path('api/events/<str:event_code>/create-guest-order/', views.create_guest_payment_order_api, name='create_guest_order'),
    path('api/events/<str:event_code>/verify-guest-payment/', views.verify_guest_payment_api, name='verify_guest_payment'),
]

