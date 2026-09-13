# KSHAN Implementation Baseline (Phase 0)

**Date**: 2026-09-13
**Git Branch Created**: `hardening/kshan-production-readiness`
**Baseline Commit**: `6fa12c6` ("Fix light-mode mobile drawer contrast and update cache busting tag")

---

## 1. System & Architecture Configuration

| Component | Baseline Configuration |
|---|---|
| **Django Framework** | Django 5.1.6, Python 3.11.9 |
| **Database** | SQLite default (`db.sqlite3`), with optional Supabase PostgreSQL via `dj_database_url` |
| **Active Face Model** | InsightFace `buffalo_s` (SCRFD detector + ResNet50 ArcFace 512D) |
| **Active Storage** | Local filesystem (`storage/events/`) with optional Cloudflare R2 / S3 |
| **Web / Realtime** | Daphne + Django Channels (In-Memory channel layer, Redis optional) |
| **Background Processing**| In-memory `ThreadPoolExecutor` worker |

---

## 2. Baseline Test & Migration Status

- `python manage.py check`: Passed with 0 issues.
- `python manage.py makemigrations --check --dry-run`: No uncommitted or missing migrations detected.
- `python manage.py test`: 0 existing automated tests ran (`NO TESTS RAN`).
- `.gitignore` verification: `.env`, `db.sqlite3`, `storage/events/*`, `logs/*.log`, `venv/`, and keys are properly ignored.

---

## 3. Existing Security Audit Findings Verified

1. **Hardcoded Secrets**:
   - `render.yaml`: Hardcoded Cloudflare R2 credentials (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT_URL`, `R2_ACCOUNT_ID`).
   - `deploy_ec2.sh`: Hardcoded Firebase API keys, R2 keys, Razorpay test key/secret, and superadmin password (`Debug@45`).
   - `gallery/management/commands/create_admin.py`: Hardcoded superuser creation with credentials `thepranit` / `Debug@45`.
2. **Master Superadmin Backdoor (`/thepranit`)**:
   - `gallery/views.py`: Bypass authentication checking plaintext string `entered_pass == "thepranit"`.
3. **Insecure Direct Object Reference (IDOR) & Unprotected Endpoints**:
   - `gallery/views.py`: `get_thumbnail_view` and `view_photo_full` serve full original and thumbnail images without verifying event ownership, guest permissions, or private album access.
4. **Cookie & Transport Security**:
   - `kshan_project/settings.py`: `SESSION_COOKIE_SECURE = False`, `ALLOWED_HOSTS = ['*']`, missing HSTS and SSL redirect headers in production.
5. **Upload Validation**:
   - File uploads rely strictly on client file extensions (`.jpg`, `.png`, etc.) without verifying magic byte signatures, decoding image structure with Pillow, or limiting decompression bounds.

---

## 4. Files Targeted for Phase 1 Hardening

- `render.yaml`
- `deploy_ec2.sh`
- `deploy_native.sh`
- `.env.example`
- `gallery/management/commands/create_admin.py`
- `kshan_project/settings.py`
- `gallery/views.py`
- `gallery/services/storage_service.py`
- `templates/master_super_admin_login.html`
- `templates/master_super_admin.html`
- `gallery/tests/test_security.py` [NEW]
