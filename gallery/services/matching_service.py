import logging
import numpy as np
from django.conf import settings
from ..models import Face, Photo

logger = logging.getLogger("kshan.matching_service")

def find_matching_photos(
    event_id: int,
    query_embedding: np.ndarray,
    threshold: float = settings.FACE_MATCH_THRESHOLD
) -> list[dict]:
    """
    Fast vectorized similarity search across all stored face embeddings in a Django event.
    """
    face_records = (
        Face.objects.filter(event_id=event_id, photo__processing_status="completed")
        .select_related("photo")
        .values(
            "id", "photo_id", "embedding", "confidence", "bounding_box",
            "photo__filename", "photo__original_filename", "photo__width",
            "photo__height", "photo__file_size"
        )
    )

    if not face_records.exists():
        logger.info(f"No face embeddings found in database for event_id: {event_id}")
        return []

    embeddings_list = []
    metadata_list = []

    for row in face_records:
        emb_bytes = row["embedding"]
        try:
            emb_vector = np.frombuffer(emb_bytes, dtype=np.float32)
            if emb_vector.shape[0] == 512:
                embeddings_list.append(emb_vector)
                metadata_list.append({
                    "face_id": row["id"],
                    "photo_id": row["photo_id"],
                    "confidence": row["confidence"],
                    "bbox": row["bounding_box"],
                    "filename": row["photo__filename"],
                    "original_filename": row["photo__original_filename"],
                    "width": row["photo__width"],
                    "height": row["photo__height"],
                    "file_size": row["photo__file_size"]
                })
        except Exception as e:
            logger.warning(f"Skipping corrupted embedding: {e}")

    if not embeddings_list:
        return []

    embeddings_matrix = np.vstack(embeddings_list)

    q_norm = np.linalg.norm(query_embedding)
    query_vec = (query_embedding / q_norm) if q_norm > 0 else query_embedding

    similarities = np.dot(embeddings_matrix, query_vec)
    matched_photos_map = {}

    for idx, sim in enumerate(similarities):
        sim_score = float(sim)
        if sim_score >= threshold:
            meta = metadata_list[idx]
            photo_id = meta["photo_id"]

            if photo_id not in matched_photos_map or sim_score > matched_photos_map[photo_id]["similarity"]:
                matched_photos_map[photo_id] = {
                    "id": photo_id,
                    "photo_id": photo_id,
                    "filename": meta["filename"],
                    "original_filename": meta["original_filename"],
                    "similarity": round(sim_score, 4),
                    "confidence": round(meta["confidence"], 4),
                    "width": meta["width"],
                    "height": meta["height"],
                    "file_size": meta["file_size"],
                    "thumbnail_url": f"/api/photos/{photo_id}/thumbnail/",
                    "view_url": f"/api/photos/{photo_id}/view/",
                    "original_url": f"/api/photos/{photo_id}/view/",
                    "download_url": f"/api/photos/{photo_id}/download/"
                }

    results = sorted(matched_photos_map.values(), key=lambda x: x["similarity"], reverse=True)
    logger.info(f"Event {event_id} search: found {len(results)} matching photos (threshold={threshold}).")
    return results
