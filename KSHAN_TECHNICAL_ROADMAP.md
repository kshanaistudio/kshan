# KSHAN Technical Roadmap & Engineering Action Plan

---

## 1. Roadmap Overview & Prioritization Strategy

This engineering roadmap provides a prioritized, actionable guide to take **KSHAN** from its current functional state to an enterprise-grade, highly scalable, and secure AI event-photography platform.

- **P0 (Critical / Blocker)**: Must fix immediately before any real user data or production deployment. Focuses on security leaks, syntax defects, and crash bugs.
- **P1 (Core MVP Hardening)**: Required for a reliable Minimum Viable Product. Focuses on persistent queuing, vector search performance, and API stability.
- **P2 (Scale & Production Reliability)**: Required for high-traffic wedding seasons and multi-photographer concurrency. Focuses on high-speed image processing (`libvips`), S3 pre-signed direct uploads, and CDN caching.
- **P3 (Advanced Features & Enterprise Expansion)**: Future competitive differentiators, including multi-camera live ingestion, automated client proofing, and AI highlight curation.

---

## 2. Prioritized Implementation Roadmap Table

| Priority | Task Name | Existing Files to Modify | New Component Required | Difficulty | Expected Benefit | Dependencies |
| :---: | :--- | :--- | :--- | :---: | :--- | :--- |
| **P0** | **Revoke & Externalize Hardcoded Secrets** | [`render.yaml`](file:///d:/Face%20recognition/render.yaml), [`kshan_project/settings.py`](file:///d:/Face%20recognition/kshan_project/settings.py), [`deploy_ec2.sh`](file:///d:/Face%20recognition/deploy_ec2.sh) | Secrets manager / clean `.env` template | **Low** | Prevents unauthorized takeover of Cloudflare R2 bucket and Django database. | None |
| **P0** | **Fix JavaScript Syntax Error in Bulk Uploader** | [`static/js/upload.js:57-75`](file:///d:/Face%20recognition/static/js/upload.js#L57-L75) | None | **Low** | Restores reliable drag-and-drop batch photo uploads on all client browsers. | None |
| **P0** | **Replace Hardcoded Superadmin Passkey with Standard RBAC** | [`gallery/views.py:2187`](file:///d:/Face%20recognition/gallery/views.py#L2187), [`templates/master_super_admin_login.html`](file:///d:/Face%20recognition/templates/master_super_admin_login.html) | Django `is_superuser` permission check | **Low** | Eliminates backdoor master access bypass (`/thepranit`). | None |
| **P0** | **Fix Google Drive Sync Signature & Schema Mismatches** | [`gallery/services/gdrive_service.py`](file:///d:/Face%20recognition/gallery/services/gdrive_service.py), [`gallery/models.py`](file:///d:/Face%20recognition/gallery/models.py) | Database Migration for `Event` GDrive fields | **Medium** | Eliminates unhandled 500 crashes during cloud photo imports. | None |
| **P0** | **Fix Missing `rembg` Dependency in requirements.txt** | [`requirements.txt`](file:///d:/Face%20recognition/requirements.txt), [`gallery/views.py:1277`](file:///d:/Face%20recognition/gallery/views.py#L1277) | `rembg>=2.0.50` package | **Low** | Prevents runtime crash when invoking background cutout tool. | None |
| **P1** | **Migrate from ThreadPool to Celery + Redis Task Queue** | [`gallery/services/background_worker.py`](file:///d:/Face%20recognition/gallery/services/background_worker.py), [`gallery/views.py`](file:///d:/Face%20recognition/gallery/views.py), [`kshan_project/settings.py`](file:///d:/Face%20recognition/kshan_project/settings.py) | Celery worker daemon + Redis instance | **High** | Guarantees background face extraction survives server restarts and crashes; supports retries. | Redis server |
| **P1** | **Implement pgvector with HNSW Index for Vector Search** | [`gallery/models.py`](file:///d:/Face%20recognition/gallery/models.py), [`gallery/services/matching_service.py`](file:///d:/Face%20recognition/gallery/services/matching_service.py) | PostgreSQL `pgvector` extension | **Medium** | Replaces linear $O(N)$ BLOB scan with sub-50ms indexed nearest-neighbor vector search. | PostgreSQL DB |
| **P1** | **Secure Direct Photo Views with Signed Session Tokens** | [`gallery/views.py:1087-1120`](file:///d:/Face%20recognition/gallery/views.py#L1087-L1120) | Signed token generator (Django signing) | **Medium** | Prevents unauthorized enumeration and scraping of private event photos. | None |
| **P1** | **Decompose Monolithic views.py into Modular Viewsets** | [`gallery/views.py`](file:///d:/Face%20recognition/gallery/views.py), [`gallery/urls.py`](file:///d:/Face%20recognition/gallery/urls.py) | Package `gallery/views/` (`auth.py`, `studio.py`, `guest.py`, `api.py`) | **Medium** | Drastically improves codebase maintainability, testability, and code hygiene. | None |
| **P1** | **Add Automated Unit & Integration Tests for ML & APIs** | [`gallery/tests.py`](file:///d:/Face%20recognition/gallery/tests.py) | Pytest test suite with synthetic fixtures | **Medium** | Catches regressions across face detection, matching, uploads, and billing. | None |
| **P2** | **Replace Pillow with `libvips` / Imagor for High-Speed Thumbnailing** | [`gallery/services/image_service.py`](file:///d:/Face%20recognition/gallery/services/image_service.py) | `pyvips` / Go `imagor` microservice | **Medium** | Reduces RAM consumption by 75% and speeds up thumbnail generation by 400%. | `libvips` C library |
| **P2** | **Implement Direct Camera-to-Cloud S3 / R2 Multipart Uploads** | [`gallery/views.py`](file:///d:/Face%20recognition/gallery/views.py), [`static/js/upload.js`](file:///d:/Face%20recognition/static/js/upload.js) | S3 Pre-signed URL API endpoint | **High** | Uploads multi-gigabyte wedding card dumps directly from browser to R2 without hitting web app RAM. | Cloudflare R2 |
| **P2** | **Add Webhook Handlers for Razorpay Payment Notifications** | [`gallery/views.py`](file:///d:/Face%20recognition/gallery/views.py), [`gallery/services/razorpay_service.py`](file:///d:/Face%20recognition/gallery/services/razorpay_service.py) | `POST /api/webhooks/razorpay/` endpoint | **Medium** | Guarantees subscription activation even if client browser disconnects before redirect. | Razorpay Webhook |
| **P2** | **Introduce GPU Acceleration for High-Volume Ingestion** | [`gallery/services/face_service.py`](file:///d:/Face%20recognition/gallery/services/face_service.py), [`Dockerfile`](file:///d:/Face%20recognition/Dockerfile) | ONNX Runtime CUDA / TensorRT execution provider | **High** | Speeds up face detection on 10,000+ photo wedding albums from 1 hour to < 5 minutes. | NVIDIA GPU instance |
| **P3** | **Automated AI Album Storytelling & Smart Curation** | [`gallery/models.py`](file:///d:/Face%20recognition/gallery/models.py), [`gallery/views.py`](file:///d:/Face%20recognition/gallery/views.py) | Quality assessment & aesthetic scoring model | **High** | Auto-detects blurry, closed-eye, and duplicate shots; groups wedding highlights automatically. | Celery |
| **P3** | **Native Mobile App (Flutter / React Native) with Offline Sync** | New client repository | Mobile client app | **High** | Allows photographers to shoot in low-connectivity banquet halls and sync when connected. | REST APIs |
| **P3** | **Decentralized Filecoin / IPFS Archival Storage Worker** | [`gallery/services/storage_service.py`](file:///d:/Face%20recognition/gallery/services/storage_service.py) | Filecoin Synapse Cloudflare Worker | **Medium** | Provides permanent, tamper-proof cold storage backups for wedding client deliverables. | Synapse SDK |

---

## 3. Detailed Technical Specifications for Key Upgrades

### Specification 1: Celery + Redis Asynchronous Queue (P1)
```python
# kshan_project/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kshan_project.settings')
app = Celery('kshan')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# gallery/tasks.py
from celery import shared_task
from .services.background_worker import process_single_photo

@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def process_photo_task(self, photo_id):
    try:
        process_single_photo(photo_id)
    except Exception as exc:
        raise self.retry(exc=exc)
```

### Specification 2: PostgreSQL pgvector Vector Search (P1)
```sql
-- PostgreSQL vector schema
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE gallery_face ADD COLUMN embedding_vec vector(512);

-- Create HNSW cosine similarity index
CREATE INDEX ON gallery_face USING hnsw (embedding_vec vector_cosine_ops)
WITH (m = 16, ef_construction = 64);

-- Querying with strict event scoping:
SELECT photo_id, 1 - (embedding_vec <=> '[0.021, -0.045, ...]') AS similarity
FROM gallery_face
WHERE event_id = 42
ORDER BY embedding_vec <=> '[0.021, -0.045, ...]'
LIMIT 100;
```
