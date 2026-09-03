---
title: KSHAN Studio
emoji: 📸
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: 5.20.0
app_file: app.py
pinned: false
license: mit
---

# KSHAN — AI Face Discovery & Photography Studio

**KSHAN** is an end-to-end, high-performance **Face Recognition Photo Gallery System** built with **Django**, **SQLite**, **InsightFace (ResNet-50 ArcFace buffalo_l)**, and a modern dark UI.

Photographers and event admins can bulk-upload thousands of event photos. Attendees simply upload a single selfie (or capture one with their camera) to automatically find every photo they appear in with 100% precision.

---

## Key Features

1. **State-of-the-Art Face Recognition (`buffalo_l`)**:
   - Uses **InsightFace ResNet-50 ArcFace** (`w600k_r50` + `det_10g`), achieving **99.83% accuracy** on the LFW benchmark.
   - Detects faces with minimum confidence and bounding box size filters, storing 512-dimension L2-normalized `float32` embeddings as binary BLOBs in SQLite.
2. **Fast Vector Cosine Similarity Search**:
   - Vectorized matrix dot product with NumPy across pre-indexed event faces.
   - Sub-second search across thousands of faces without re-running face detection on event photos.
3. **Background Worker Queue**:
   - Asynchronous thread pool processes hundreds of photos in the background without blocking the UI.
   - Live real-time progress bar with percentage, completed count, and detected face counts.
4. **Duplicate Protection**:
   - Computes streaming **SHA-256** hashes to prevent duplicate photo uploads and redundant processing.
5. **Lossless Storage & High-Quality Thumbnails**:
   - Original photos are preserved untouched.
   - 500px aspect-ratio thumbnails generated automatically with EXIF orientation correction.
6. **Gallery & Download Engine**:
   - Responsive masonry/grid view with match percentage badges.
   - Full-resolution Lightbox preview.
   - Single photo download & multi-photo batch **ZIP download**.
7. **Django Admin & Custom Management**:
   - Built-in Django authentication and session security (`/admin/login/`). Default: `admin` / `admin123`.
   - Django admin interface at `/django-admin/`.
   - Event creation, bulk drag-and-drop uploader, photo deletion, and failed photo reprocessing.

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Apply Migrations & Initialize Admin
```bash
python manage.py migrate
```

### 3. Run the Server
```bash
python manage.py runserver 8000
```

Open `http://127.0.0.1:8000` in your web browser.

---

## User & Admin Workflow

1. **Admin Login**:
   - Go to `http://127.0.0.1:8000/admin/login/`
   - Default credentials:
     - **Username**: `admin`
     - **Password**: `admin123`
2. **Create Event**:
   - Click **Create New Event**, e.g., name `Rahul & Priya Wedding`, code `RP2026`.
3. **Bulk Upload Photos**:
   - Open event details and drag-and-drop event photos into the upload zone.
   - Watch the live progress bar as faces and embeddings are extracted into SQLite.
4. **User Face Search**:
   - Attendees open `http://127.0.0.1:8000` and enter event code `RP2026` (or visit `http://127.0.0.1:8000/event/RP2026/`).
   - Upload a selfie or take a photo with the live webcam.
   - View matching photos in the gallery and download individual or selected ZIP archives!
