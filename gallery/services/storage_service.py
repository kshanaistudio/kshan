import os
import shutil
import time
import zipfile
import uuid
import logging
from io import BytesIO
from pathlib import Path
from django.conf import settings

logger = logging.getLogger("kshan.storage_service")

# Cloudflare R2 / S3 client
_s3_client = None

def get_s3_client():
    global _s3_client
    if _s3_client is None and getattr(settings, 'R2_ENABLED', False):
        try:
            import boto3
            from botocore.config import Config

            _s3_client = boto3.client(
                's3',
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(signature_version='s3v4')
            )
            logger.info("Cloudflare R2 S3 client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Cloudflare R2 client: {e}")
            _s3_client = None
    return _s3_client

def upload_to_r2(local_path: str | Path, r2_key: str) -> bool:
    """Uploads a local file to Cloudflare R2 bucket."""
    s3 = get_s3_client()
    if not s3:
        return False
    try:
        bucket = settings.R2_BUCKET_NAME
        s3.upload_file(str(local_path), bucket, r2_key)
        logger.info(f"Uploaded {local_path} to R2 bucket '{bucket}' key '{r2_key}'")
        return True
    except Exception as e:
        logger.error(f"Failed uploading to R2: {e}")
        return False

def get_file_bytes_from_r2(r2_key: str) -> bytes | None:
    """Downloads bytes for an object stored in Cloudflare R2."""
    s3 = get_s3_client()
    if not s3:
        return None
    try:
        bucket = settings.R2_BUCKET_NAME
        response = s3.get_object(Bucket=bucket, Key=r2_key)
        return response['Body'].read()
    except Exception as e:
        logger.warning(f"Could not fetch {r2_key} from R2: {e}")
        return None

def ensure_event_directories(event_code: str) -> tuple[Path, Path]:
    event_dir = settings.EVENTS_STORAGE_DIR / event_code
    originals_dir = event_dir / "originals"
    thumbnails_dir = event_dir / "thumbnails"
    
    originals_dir.mkdir(parents=True, exist_ok=True)
    thumbnails_dir.mkdir(parents=True, exist_ok=True)
    
    return originals_dir, thumbnails_dir

def get_event_original_path(event_code: str, filename: str) -> Path:
    return settings.EVENTS_STORAGE_DIR / event_code / "originals" / filename

def get_event_thumbnail_path(event_code: str, filename: str) -> Path:
    return settings.EVENTS_STORAGE_DIR / event_code / "thumbnails" / filename

def save_uploaded_photo(event_code: str, original_filename: str, content: bytes) -> tuple[str, Path]:
    originals_dir, _ = ensure_event_directories(event_code)
    ext = Path(original_filename).suffix.lower() or ".jpg"
    unique_filename = f"{uuid.uuid4().hex[:12]}_{Path(original_filename).stem}{ext}"
    target_path = originals_dir / unique_filename

    with open(target_path, "wb") as f:
        f.write(content)

    return unique_filename, target_path

def cleanup_temp_files(max_age_seconds: int = 1800):
    now = time.time()
    if settings.TEMP_STORAGE_DIR.exists():
        for item in settings.TEMP_STORAGE_DIR.iterdir():
            if item.is_file():
                try:
                    if now - item.stat().st_mtime > max_age_seconds:
                        item.unlink(missing_ok=True)
                except Exception:
                    pass

def create_zip_archive(photos_info: list[dict]) -> BytesIO:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        seen_names = {}
        for photo in photos_info:
            file_path = photo.get("file_path")
            orig_name = photo.get("original_filename") or Path(file_path).name
            
            if file_path and os.path.exists(file_path):
                if orig_name in seen_names:
                    seen_names[orig_name] += 1
                    stem = Path(orig_name).stem
                    suffix = Path(orig_name).suffix
                    arcname = f"{stem}_{seen_names[orig_name]}{suffix}"
                else:
                    seen_names[orig_name] = 0
                    arcname = orig_name
                
                zip_file.write(file_path, arcname=arcname)

    zip_buffer.seek(0)
    return zip_buffer

def delete_event_storage(event_code: str):
    # Local deletion
    event_dir = settings.EVENTS_STORAGE_DIR / event_code
    if event_dir.exists():
        shutil.rmtree(event_dir, ignore_errors=True)

    # Cloudflare R2 deletion
    s3 = get_s3_client()
    if s3 and getattr(settings, 'R2_ENABLED', False):
        try:
            prefix = f"events/{event_code}/"
            bucket = settings.R2_BUCKET_NAME
            objects = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            if 'Contents' in objects:
                delete_keys = [{'Key': obj['Key']} for obj in objects['Contents']]
                s3.delete_objects(Bucket=bucket, Delete={'Objects': delete_keys})
                logger.info(f"Deleted R2 objects under prefix {prefix}")
        except Exception as e:
            logger.error(f"Failed deleting R2 objects for event {event_code}: {e}")
