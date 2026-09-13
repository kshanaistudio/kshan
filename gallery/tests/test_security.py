import io
import json
from PIL import Image
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from gallery.models import Event, Photo, PhotographerProfile, GlobalSiteSettings
from gallery.services.image_service import validate_image_upload

class SecurityAndAuthorizationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.superadmin = User.objects.create_superuser('admin_user', 'admin@kshan.local', 'SuperAdminPass123!')
        self.staff_user = User.objects.create_user('staff_user', 'staff@kshan.local', 'StaffPass123!', is_staff=True)
        self.photographer_a = User.objects.create_user('photographer_a', 'a@kshan.local', 'PhotoPass123!')
        self.photographer_b = User.objects.create_user('photographer_b', 'b@kshan.local', 'PhotoPass123!')
        self.normal_guest = User.objects.create_user('guest_user', 'guest@kshan.local', 'GuestPass123!')

        # Events
        self.event_a = Event.objects.create(
            photographer=self.photographer_a,
            name="Wedding A",
            event_code="EVTA01",
            status="live",
            access_mode="public"
        )
        self.event_pin = Event.objects.create(
            photographer=self.photographer_a,
            name="Private PIN Wedding",
            event_code="EVTPIN",
            status="live",
            access_mode="pin",
            access_pin="9988"
        )
        self.event_draft = Event.objects.create(
            photographer=self.photographer_a,
            name="Draft Wedding",
            event_code="EVTDRF",
            status="draft",
            access_mode="public"
        )

        # Photos
        self.photo_a = Photo.objects.create(
            event=self.event_a,
            filename="photo_a.jpg",
            original_filename="photo_a.jpg",
            file_path="",
            processing_status="completed"
        )
        self.photo_pin = Photo.objects.create(
            event=self.event_pin,
            filename="photo_pin.jpg",
            original_filename="photo_pin.jpg",
            file_path="",
            processing_status="completed"
        )
        self.photo_draft = Photo.objects.create(
            event=self.event_draft,
            filename="photo_draft.jpg",
            original_filename="photo_draft.jpg",
            file_path="",
            processing_status="completed"
        )

    # ─────────────────────────────────────────────────────────────
    # 1. Master Superadmin Authorization (/thepranit)
    # ─────────────────────────────────────────────────────────────
    def test_anonymous_user_cannot_access_thepranit(self):
        resp = self.client.get('/thepranit/')
        # Should render login template, not dashboard
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Superadmin Username')
        self.assertNotContains(resp, 'KSHAN Master Control Center')

    def test_backdoor_passkey_is_rejected(self):
        resp = self.client.post('/thepranit/', {'super_password': 'thepranit'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid superadmin credentials')

    def test_normal_user_cannot_login_to_thepranit(self):
        resp = self.client.post('/thepranit/', {'username': 'photographer_a', 'password': 'PhotoPass123!'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid superadmin credentials')

    def test_staff_non_superuser_cannot_login_to_thepranit(self):
        resp = self.client.post('/thepranit/', {'username': 'staff_user', 'password': 'StaffPass123!'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Invalid superadmin credentials')

    def test_superuser_can_login_and_access_thepranit(self):
        resp = self.client.post('/thepranit/', {'username': 'admin_user', 'password': 'SuperAdminPass123!'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, '/thepranit/')
        
        # Follow redirect
        dashboard_resp = self.client.get('/thepranit/')
        self.assertEqual(dashboard_resp.status_code, 200)
        self.assertContains(dashboard_resp, 'KSHAN Master Control Center')

    # ─────────────────────────────────────────────────────────────
    # 2. Cross-Event Isolation & IDOR Photo Access
    # ─────────────────────────────────────────────────────────────
    def test_draft_event_photo_is_forbidden_to_unauthenticated_guest(self):
        resp = self.client.get(f'/api/photos/{self.photo_draft.id}/thumbnail/')
        self.assertEqual(resp.status_code, 403)

    def test_draft_event_photo_is_accessible_by_owner(self):
        self.client.login(username='photographer_a', password='PhotoPass123!')
        # Will return 404 because file_path is empty on mock DB, but NOT 403 Forbidden
        resp = self.client.get(f'/api/photos/{self.photo_draft.id}/thumbnail/')
        self.assertEqual(resp.status_code, 404)

    def test_pin_protected_photo_is_forbidden_without_pin(self):
        resp = self.client.get(f'/api/photos/{self.photo_pin.id}/thumbnail/')
        self.assertEqual(resp.status_code, 403)
        self.assertIn("PIN required", resp.json().get('error', ''))

    def test_pin_protected_photo_allowed_after_pin_verification(self):
        session = self.client.session
        session[f"pin_verified_{self.event_pin.event_code}"] = True
        session.save()

        resp = self.client.get(f'/api/photos/{self.photo_pin.id}/thumbnail/')
        # Allowed through authorization, returns 404 only because mock file is absent
        self.assertEqual(resp.status_code, 404)

    def test_photographer_cannot_manage_another_photographers_event(self):
        self.client.login(username='photographer_b', password='PhotoPass123!')
        resp = self.client.get(f'/admin/events/{self.event_a.event_code}/')
        self.assertEqual(resp.status_code, 403)

    # ─────────────────────────────────────────────────────────────
    # 3. Upload Security & Image Signature Validation
    # ─────────────────────────────────────────────────────────────
    def _create_test_image_bytes(self, format='JPEG', size=(100, 100)):
        bio = io.BytesIO()
        img = Image.new('RGB', size, color=(200, 150, 100))
        img.save(bio, format=format)
        bio.seek(0)
        return bio.getvalue()

    def test_validate_valid_jpeg(self):
        data = self._create_test_image_bytes('JPEG')
        is_valid, fmt, err = validate_image_upload(data)
        self.assertTrue(is_valid)
        self.assertEqual(fmt, 'jpeg')

    def test_validate_valid_png(self):
        data = self._create_test_image_bytes('PNG')
        is_valid, fmt, err = validate_image_upload(data)
        self.assertTrue(is_valid)
        self.assertEqual(fmt, 'png')

    def test_validate_valid_webp(self):
        data = self._create_test_image_bytes('WEBP')
        is_valid, fmt, err = validate_image_upload(data)
        self.assertTrue(is_valid)
        self.assertEqual(fmt, 'webp')

    def test_reject_fake_extension_spoof(self):
        # Fake JPEG that contains executable/shell text
        fake_content = b"MZ\x90\x00\x03\x00\x00\x00#!/bin/bash\necho Malicious"
        is_valid, fmt, err = validate_image_upload(fake_content)
        self.assertFalse(is_valid)
        self.assertIn("Invalid or corrupted image", err)

    def test_reject_empty_upload(self):
        is_valid, fmt, err = validate_image_upload(b"")
        self.assertFalse(is_valid)
        self.assertIn("empty", err)

    def test_reject_oversized_upload(self):
        data = self._create_test_image_bytes('JPEG')
        # Validate with 50-byte max limit
        is_valid, fmt, err = validate_image_upload(data, max_size_bytes=50)
        self.assertFalse(is_valid)
        self.assertIn("exceeds maximum limit", err)
