import logging
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from django.db import close_old_connections
from django.conf import settings
from ..models import Photo, Face, Event
from .image_service import create_thumbnail, get_image_metadata
from .face_service import get_face_service
from .storage_service import get_event_thumbnail_path

logger = logging.getLogger("kshan.background_worker")
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="kshan_django_worker")

def _is_enough_memory_for_face_detection(min_free_mb: int = 350) -> bool:
    """Check if there's enough free RAM to safely run InsightFace (~500MB model)."""
    try:
        import psutil
        free_mb = psutil.virtual_memory().available / (1024 * 1024)
        if free_mb < min_free_mb:
            logger.warning(f"Low memory ({free_mb:.0f} MB free) — skipping face detection to prevent OOM crash.")
            return False
        return True
    except ImportError:
        # psutil not installed — assume ok
        return True


def process_single_photo(photo_id: int):
    close_old_connections()
    try:
        photo = Photo.objects.filter(id=photo_id).select_related('event').first()
        if not photo:
            logger.warning(f"Photo ID {photo_id} not found for processing.")
            return

        event = photo.event
        photo.processing_status = "processing"
        photo.error_message = None
        photo.save(update_fields=['processing_status', 'error_message'])

        original_path = photo.file_path
        if not Path(original_path).exists():
            raise FileNotFoundError(f"Original image file missing: {original_path}")

        # ── Deduplication: compute SHA256 and check for existing photo ──
        from .image_service import compute_sha256
        file_hash = compute_sha256(original_path)
        duplicate = Photo.objects.filter(
            event=event,
            file_hash=file_hash
        ).exclude(id=photo.id).first()
        if duplicate:
            logger.info(f"Duplicate detected: photo {photo.id} matches photo {duplicate.id} — removing.")
            try:
                Path(original_path).unlink(missing_ok=True)
            except Exception:
                pass
            photo.delete()
            return
        photo.file_hash = file_hash

        # ── Extract EXIF and Metadata ──
        metadata = get_image_metadata(original_path)
        photo.width = metadata["width"]
        photo.height = metadata["height"]
        photo.file_size = metadata["file_size"]
        exif = metadata.get("exif", {})
        photo.exif_camera = exif.get("camera", "")
        photo.exif_lens = exif.get("lens", "")
        photo.exif_focal_length = exif.get("focal_length", "")
        photo.exif_aperture = exif.get("aperture", "")
        photo.exif_exposure_time = exif.get("exposure_time", "")
        photo.exif_iso = exif.get("iso", "")
        photo.exif_date_taken = exif.get("date_taken")

        # ── Thumbnail ──
        thumb_path = get_event_thumbnail_path(event.event_code, f"thumb_{Path(photo.filename).stem}.jpg")
        create_thumbnail(original_path, str(thumb_path))
        photo.thumbnail_path = str(thumb_path)

        # ── InsightFace ResNet-50 detection & embeddings ──
        # Only run if enabled AND there is enough free RAM (model needs ~500MB)
        detected_faces = []
        face_recognition_enabled = getattr(settings, 'FACE_RECOGNITION_ENABLED', True)
        if face_recognition_enabled and _is_enough_memory_for_face_detection():
            try:
                face_service = get_face_service()
                detected_faces = face_service.extract_faces_from_image(original_path)
            except Exception as face_err:
                logger.warning(f"Face detection skipped for photo {photo.id}: {face_err}")
        else:
            if not face_recognition_enabled:
                logger.info(f"Face recognition disabled — skipping for photo {photo.id}")

        # ── Apply watermark ──
        from .image_service import apply_watermark
        watermark_name = None
        logo_path = None
        if event.photographer and hasattr(event.photographer, "profile"):
            prof = event.photographer.profile
            watermark_name = prof.studio_name or prof.display_name or event.photographer.username
            if prof.studio_logo and hasattr(prof.studio_logo, 'path') and Path(prof.studio_logo.path).exists():
                logo_path = str(prof.studio_logo.path)
            elif prof.watermark_logo and hasattr(prof.watermark_logo, 'path') and Path(prof.watermark_logo.path).exists():
                logo_path = str(prof.watermark_logo.path)
        elif event.photographer:
            watermark_name = event.photographer.username
        apply_watermark(str(thumb_path), watermark_name, logo_path=logo_path)

        # ── Upload to Cloudflare R2 ──
        from .storage_service import upload_to_r2
        if getattr(settings, 'R2_ENABLED', False):
            try:
                upload_to_r2(thumb_path, f"events/{event.event_code}/thumbnails/{thumb_path.name}")
                upload_to_r2(original_path, f"events/{event.event_code}/originals/{photo.filename}")
            except Exception as r2_err:
                logger.warning(f"R2 background upload warning for photo {photo.id}: {r2_err}")

        # ── Save faces ──
        Face.objects.filter(photo_id=photo.id).delete()
        face_objects = [
            Face(
                photo=photo,
                event=event,
                embedding=face_data["embedding"],
                confidence=face_data["confidence"],
                bounding_box=json.dumps(face_data["bbox"])
            )
            for face_data in detected_faces
        ]
        if face_objects:
            Face.objects.bulk_create(face_objects)

        photo.processing_status = "completed"
        photo.save(update_fields=[
            'file_hash', 'width', 'height', 'file_size', 'thumbnail_path',
            'exif_camera', 'exif_lens', 'exif_focal_length', 'exif_aperture',
            'exif_exposure_time', 'exif_iso', 'exif_date_taken', 'processing_status'
        ])
        logger.info(f"Django Worker: Successfully processed photo {photo.id}: {len(detected_faces)} face(s) saved.")

    except Exception as e:
        logger.error(f"Error processing photo {photo_id}: {e}\n{traceback.format_exc()}")
        try:
            p = Photo.objects.filter(id=photo_id).first()
            if p:
                p.processing_status = "failed"
                p.error_message = str(e)
                p.save(update_fields=['processing_status', 'error_message'])
        except Exception:
            pass
    finally:
        close_old_connections()

def queue_photo_processing(photo_id: int):
    executor.submit(process_single_photo, photo_id)

def queue_batch_processing(photo_ids: list[int]):
    for pid in photo_ids:
        executor.submit(process_single_photo, pid)

def get_event_progress(event_id: int) -> dict:
    close_old_connections()
    photos = Photo.objects.filter(event_id=event_id)
    total = photos.count()
    if total == 0:
        return {
            "total": 0,
            "completed": 0,
            "failed": 0,
            "pending": 0,
            "processing": 0,
            "percentage": 100,
            "is_complete": True,
            "faces_detected": 0
        }

    completed = photos.filter(processing_status="completed").count()
    failed = photos.filter(processing_status="failed").count()
    processing = photos.filter(processing_status="processing").count()
    pending = photos.filter(processing_status="pending").count()
    total_faces = Face.objects.filter(event_id=event_id).count()
    percentage = int(((completed + failed) / total) * 100) if total > 0 else 100

    return {
        "total": total,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "processing": processing,
        "pending_total": pending + processing,
        "percentage": percentage,
        "is_complete": (completed + failed) == total,
        "faces_detected": total_faces
    }
