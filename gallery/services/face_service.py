import logging
import threading
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from django.conf import settings
from .image_service import load_cv2_image_safe

logger = logging.getLogger("kshan.face_service")

class FaceService:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        logger.info(f"Initializing InsightFace model: {settings.INSIGHTFACE_MODEL_NAME}")
        self.app = FaceAnalysis(
            name=settings.INSIGHTFACE_MODEL_NAME,
            providers=["CPUExecutionProvider"]
        )
        self.app.prepare(ctx_id=0, det_size=settings.DETECTION_SIZE)
        logger.info(f"InsightFace model {settings.INSIGHTFACE_MODEL_NAME} initialized successfully.")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def extract_faces_from_image(self, image_path_or_bytes) -> list[dict]:
        """
        Detects faces in an image and extracts normalized 512-dim ArcFace embeddings.
        Filters out low-confidence detections and tiny bounding boxes (< MIN_FACE_SIZE).
        """
        img_bgr = load_cv2_image_safe(image_path_or_bytes)
        detected_faces = self.app.get(img_bgr)
        results = []

        for face in detected_faces:
            confidence = float(face.det_score) if hasattr(face, "det_score") else 1.0
            if confidence < settings.MIN_DET_SCORE:
                continue

            bbox = [int(coord) for coord in face.bbox.tolist()] if hasattr(face, "bbox") else []
            if len(bbox) == 4:
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                if w < settings.MIN_FACE_SIZE or h < settings.MIN_FACE_SIZE:
                    continue

            embedding = face.normed_embedding
            if embedding is None or len(embedding) == 0:
                raw_emb = face.embedding
                norm = np.linalg.norm(raw_emb)
                embedding = (raw_emb / norm) if norm > 0 else raw_emb

            embedding = embedding.astype(np.float32)
            embedding_bytes = embedding.tobytes()

            results.append({
                "embedding": embedding_bytes,
                "confidence": confidence,
                "bbox": bbox
            })

        logger.info(f"Extracted {len(results)} valid face(s) after quality & size filters.")
        return results

    def validate_and_extract_selfie(self, image_path_or_bytes) -> np.ndarray:
        """
        Validates user selfie photo for search:
        - Downscales ultra high-res smartphone/camera images to max 1280px for instant detection
        - Must contain exactly 1 clear face.
        Returns normalized 1D NumPy float32 array.
        """
        import cv2
        img_bgr = load_cv2_image_safe(image_path_or_bytes)
        
        # Performance optimization: Resize large smartphone images (e.g. 4000x3000 -> 1280px)
        h, w = img_bgr.shape[:2]
        max_dimension = 1280
        if max(h, w) > max_dimension:
            scale = max_dimension / float(max(h, w))
            new_w = int(w * scale)
            new_h = int(h * scale)
            img_bgr = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)

        detected_faces = self.app.get(img_bgr)

        # Filter out low-confidence noise
        valid_faces = []
        for face in detected_faces:
            conf = float(face.det_score) if hasattr(face, "det_score") else 1.0
            if conf >= 0.45:
                valid_faces.append(face)

        if not valid_faces or len(valid_faces) == 0:
            raise ValueError("No face detected. Please upload a clear front-facing photo.")

        # If multiple faces detected (e.g. bystanders or group selfie), select the largest, most dominant face
        if len(valid_faces) > 1:
            def face_area(f):
                if hasattr(f, "bbox") and len(f.bbox) == 4:
                    return (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1])
                return 0
            valid_faces.sort(key=face_area, reverse=True)

        face = valid_faces[0]
        embedding = face.normed_embedding
        if embedding is None or len(embedding) == 0:
            raw_emb = face.embedding
            norm = np.linalg.norm(raw_emb)
            embedding = (raw_emb / norm) if norm > 0 else raw_emb

        return embedding.astype(np.float32)

def get_face_service() -> FaceService:
    return FaceService.get_instance()
