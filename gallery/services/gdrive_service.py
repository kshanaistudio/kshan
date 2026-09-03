import re
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger("kshan.gdrive")

_drive_service = None

def get_gdrive_service():
    """
    Initializes and returns Google Drive API v3 service using either:
    1. OAuth user credentials (gdrive_token.json) -> Uses personal Google Drive quota.
    2. Service Account credentials (gdrive_credentials.json) -> For Google Workspace / Shared Drives.
    """
    global _drive_service
    if _drive_service is not None:
        return _drive_service

    # Check OAuth first
    try:
        from .gdrive_oauth import get_gdrive_oauth_service
        oauth_srv = get_gdrive_oauth_service()
        if oauth_srv:
            _drive_service = oauth_srv
            logger.info("Google Drive v3 API initialized via User OAuth token.")
            return _drive_service
    except Exception as e:
        logger.debug(f"OAuth service check: {e}")

    credentials_path = getattr(settings, 'GDRIVE_CREDENTIALS_PATH', None)
    if not credentials_path:
        credentials_path = settings.BASE_DIR / "gdrive_credentials.json"

    if not Path(credentials_path).exists():
        logger.warning(f"Google Drive credentials not found at: {credentials_path}")
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        scopes = ['https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=scopes
        )
        _drive_service = build('drive', 'v3', credentials=creds, cache_discovery=False)
        logger.info("Google Drive v3 API service initialized successfully.")
        return _drive_service
    except Exception as e:
        logger.error(f"Failed to initialize Google Drive service: {e}")
        return None


def extract_gdrive_folder_id(folder_url_or_id: str) -> str | None:
    """
    Extracts the folder ID from a Google Drive URL or returns the raw ID.
    Examples:
      - https://drive.google.com/drive/folders/1Bi-uCnylamcH7QHERmA4VUr3_mqphhud?usp=drive_link -> 1Bi-uCnylamcH7QHERmA4VUr3_mqphhud
      - 1Bi-uCnylamcH7QHERmA4VUr3_mqphhud -> 1Bi-uCnylamcH7QHERmA4VUr3_mqphhud
    """
    if not folder_url_or_id:
        return None

    folder_url_or_id = folder_url_or_id.strip()
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', folder_url_or_id)
    if match:
        return match.group(1)

    # If it's already a clean alphanumeric ID
    if re.match(r'^[a-zA-Z0-9_-]{15,}$', folder_url_or_id):
        return folder_url_or_id

    return None


def upload_photo_to_gdrive(file_path: str | Path, folder_url_or_id: str, original_filename: str = None) -> dict | None:
    """
    Uploads a photo to the specified Google Drive folder.
    """
    service = get_gdrive_service()
    if not service:
        logger.warning("Google Drive service unavailable. Skipping GDrive upload.")
        return None

    folder_id = extract_gdrive_folder_id(folder_url_or_id)
    if not folder_id:
        logger.error(f"Invalid Google Drive folder identifier: {folder_url_or_id}")
        return None

    path_obj = Path(file_path)
    if not path_obj.exists():
        logger.error(f"Local file does not exist for Google Drive upload: {file_path}")
        return None

    filename = original_filename or path_obj.name

    try:
        from googleapiclient.http import MediaFileUpload

        # Determine MIME type
        ext = path_obj.suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp"
        }
        mime_type = mime_map.get(ext, "image/jpeg")

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }

        media = MediaFileUpload(
            str(path_obj),
            mimetype=mime_type,
            resumable=True
        )

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink',
            supportsAllDrives=True
        ).execute()

        logger.info(f"Successfully uploaded {filename} to Google Drive folder {folder_id} (Drive File ID: {uploaded_file.get('id')})")
        return uploaded_file

    except Exception as e:
        logger.error(f"Error uploading {filename} to Google Drive: {e}")
        return None


def get_all_gdrive_image_files_recursive(service, folder_id: str, current_sub_folder_name: str = None) -> list[dict]:
    """
    Recursively discovers all image files across subfolders (e.g. Wedding -> Candid -> Mehendi -> Photos).
    """
    files_to_import = []
    
    # Query all children in folder (both files and subfolders)
    page_token = None
    while True:
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken, files(id, name, mimeType, size)",
            pageSize=100,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        for item in results.get('files', []):
            mime_type = item.get('mimeType', '')
            name = item.get('name', '')

            if mime_type == 'application/vnd.google-apps.folder':
                # Traverse subfolder recursively
                sub_folder_label = f"{current_sub_folder_name} / {name}" if current_sub_folder_name else name
                sub_files = get_all_gdrive_image_files_recursive(service, item['id'], sub_folder_label)
                files_to_import.extend(sub_files)
            elif (
                mime_type.startswith('image/') or 
                name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.heic'))
            ):
                item['album_name'] = current_sub_folder_name
                files_to_import.append(item)

        page_token = results.get('nextPageToken')
        if not page_token:
            break

    return files_to_import


def list_and_import_gdrive_photos(event, folder_url_or_id: str = None) -> dict:
    """
    Recursively scans Google Drive folders, imports all photos into KSHAN,
    creates matching albums (e.g. Mehendi, Candid), and triggers AI face recognition.
    """
    from io import BytesIO
    from googleapiclient.http import MediaIoBaseDownload
    from ..models import Photo, Album, AlbumPhoto
    from .image_service import compute_sha256, get_image_metadata
    from .storage_service import save_uploaded_photo
    from .background_worker import queue_batch_processing

    service = get_gdrive_service()
    if not service:
        return {"success": False, "error": "Google Drive API service is not authenticated."}

    target_url = folder_url_or_id or event.google_drive_folder_url
    folder_id = extract_gdrive_folder_id(target_url)
    if not folder_id:
        return {"success": False, "error": "Invalid or missing Google Drive folder URL / ID."}

    try:
        # Recursively find all image files across all nested subfolders
        items = get_all_gdrive_image_files_recursive(service, folder_id)
        if not items:
            return {"success": True, "message": "No photo files found in this Google Drive folder or its subfolders.", "imported_count": 0, "skipped_count": 0}

        saved_photo_ids = []
        skipped_duplicates = 0
        errors = []
        album_cache = {}

        for item in items:
            file_id = item['id']
            file_name = item['name']
            album_name = item.get('album_name')

            try:
                # Download photo bytes from Google Drive
                request_media = service.files().get_media(fileId=file_id, supportsAllDrives=True)
                file_buffer = BytesIO()
                downloader = MediaIoBaseDownload(file_buffer, request_media)
                
                done = False
                while not done:
                    status, done = downloader.next_chunk()

                content = file_buffer.getvalue()
                if not content:
                    continue

                # Save photo to event storage and Cloudflare R2
                saved_filename, saved_path = save_uploaded_photo(
                    event.event_code, 
                    file_name, 
                    content, 
                    storage_destination=event.storage_destination
                )
                file_hash = compute_sha256(str(saved_path))

                # Check duplicates
                existing_photo = Photo.objects.filter(event=event, file_hash=file_hash).first()
                if existing_photo:
                    saved_path.unlink(missing_ok=True)
                    skipped_duplicates += 1
                    photo = existing_photo
                else:
                    meta = get_image_metadata(str(saved_path))
                    exif = meta.get("exif", {})

                    photo = Photo.objects.create(
                        event=event,
                        filename=saved_filename,
                        original_filename=file_name,
                        file_path=str(saved_path),
                        file_size=meta.get("file_size", len(content)),
                        width=meta.get("width", 0),
                        height=meta.get("height", 0),
                        file_hash=file_hash,
                        processing_status="pending",
                        uploaded_by_type="gdrive_import",
                        exif_camera=exif.get("camera", ""),
                        exif_lens=exif.get("lens", ""),
                        exif_focal_length=exif.get("focal_length", ""),
                        exif_aperture=exif.get("aperture", ""),
                        exif_exposure_time=exif.get("exposure_time", ""),
                        exif_iso=exif.get("iso", ""),
                        exif_date_taken=exif.get("date_taken")
                    )
                    saved_photo_ids.append(photo.id)

                # If photo came from a subfolder, link it into a matching Album
                if album_name:
                    if album_name not in album_cache:
                        album, _ = Album.objects.get_or_create(
                            event=event,
                            name=album_name,
                            defaults={"description": f"Imported from Google Drive: {album_name}"}
                        )
                        album_cache[album_name] = album
                    
                    target_album = album_cache[album_name]
                    AlbumPhoto.objects.get_or_create(album=target_album, photo=photo)

            except Exception as item_err:
                logger.error(f"Error importing Drive photo {file_name}: {item_err}")
                errors.append(f"{file_name}: {str(item_err)}")

        # Queue AI face recognition indexing on all newly imported photos
        if saved_photo_ids:
            queue_batch_processing(saved_photo_ids)

        return {
            "success": True,
            "message": f"Successfully imported & indexed {len(saved_photo_ids)} photo(s) from Google Drive across all subfolders! {skipped_duplicates} duplicate(s) skipped.",
            "imported_count": len(saved_photo_ids),
            "skipped_count": skipped_duplicates,
            "photo_ids": saved_photo_ids,
            "errors": errors
        }

    except Exception as e:
        logger.error(f"Google Drive recursive import error: {e}")
        return {"success": False, "error": str(e)}


