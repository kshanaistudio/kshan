import time
import secrets
import string
import logging
import threading
from django.conf import settings

logger = logging.getLogger("kshan.faceshare.room_service")

class FaceShareRoomService:
    """
    Ephemeral, thread-safe in-memory room service for FaceShare.
    Guarantees:
    - Zero persistence of photos, selfies, or face embeddings.
    - Automatic TTL cleanup for expired rooms.
    - Rate-limiting on join attempts and participant counts.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._rooms = {}  # room_code -> room_dict
        self._host_map = {}  # host_token -> room_code
        self._peer_map = {}  # peer_id -> room_code
        self._join_attempts = {}  # ip/identifier -> list of timestamps
        self.ttl_seconds = int(getattr(settings, 'FACESHARE_ROOM_TTL_MINUTES', 60)) * 60
        self.max_photos = int(getattr(settings, 'FACESHARE_MAX_PHOTOS', 300))
        self.max_participants = int(getattr(settings, 'FACESHARE_MAX_PARTICIPANTS', 15))

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _generate_room_code(self, length=6) -> str:
        chars = string.ascii_uppercase + string.digits
        # Exclude easily confused characters: 0, O, 1, I
        clean_chars = [c for c in chars if c not in ('0', 'O', '1', 'I')]
        for _ in range(20):
            code = ''.join(secrets.choice(clean_chars) for _ in range(length))
            if code not in self._rooms:
                return code
        return secrets.token_hex(3).upper()

    def cleanup_expired_rooms(self):
        now = time.time()
        with self._lock:
            expired_codes = [
                code for code, room in self._rooms.items()
                if room.get('expires_at', 0) <= now
            ]
            for code in expired_codes:
                self._destroy_room_unsafe(code)

    def create_room(self, host_name="Host", client_ip=None) -> dict:
        self.cleanup_expired_rooms()
        room_code = self._generate_room_code()
        host_token = secrets.token_urlsafe(24)
        now = time.time()
        expires_at = now + self.ttl_seconds

        room = {
            "room_code": room_code,
            "host_token": host_token,
            "host_name": host_name[:30],
            "host_connected": True,
            "host_channel": None,
            "created_at": now,
            "expires_at": expires_at,
            "participants": {},  # peer_id -> { peer_id, name, approved, channel, connected_at, status }
            "photo_count": 0,
            "client_ip": client_ip,
        }

        with self._lock:
            self._rooms[room_code] = room
            self._host_map[host_token] = room_code

        logger.info(f"FaceShare room created: {room_code} (Expires in {self.ttl_seconds // 60}m)")
        return {
            "room_code": room_code,
            "host_token": host_token,
            "expires_at": expires_at,
            "max_photos": self.max_photos,
            "max_participants": self.max_participants,
        }

    def get_room(self, room_code: str) -> dict | None:
        if not room_code:
            return None
        self.cleanup_expired_rooms()
        room_code = room_code.strip().upper()
        with self._lock:
            room = self._rooms.get(room_code)
            if not room:
                return None
            if room.get("expires_at", 0) <= time.time():
                self._destroy_room_unsafe(room_code)
                return None
            # Return safe copy
            return {
                "room_code": room["room_code"],
                "host_name": room["host_name"],
                "host_connected": room["host_connected"],
                "created_at": room["created_at"],
                "expires_at": room["expires_at"],
                "participant_count": len(room["participants"]),
                "photo_count": room["photo_count"],
            }

    def verify_host(self, room_code: str, host_token: str) -> bool:
        if not room_code or not host_token:
            return False
        room_code = room_code.strip().upper()
        with self._lock:
            room = self._rooms.get(room_code)
            if not room:
                return False
            return room.get("host_token") == host_token

    def join_request(self, room_code: str, display_name: str, client_ip=None) -> dict:
        self.cleanup_expired_rooms()
        room_code = room_code.strip().upper()
        
        # Rate limit check per IP (max 15 join requests per minute)
        now = time.time()
        if client_ip:
            with self._lock:
                attempts = [t for t in self._join_attempts.get(client_ip, []) if now - t < 60]
                if len(attempts) >= 15:
                    return {"success": False, "error": "Too many requests. Please wait a moment."}
                attempts.append(now)
                self._join_attempts[client_ip] = attempts

        with self._lock:
            room = self._rooms.get(room_code)
            if not room:
                return {"success": False, "error": "Room not found or expired."}
            if room.get("expires_at", 0) <= now:
                self._destroy_room_unsafe(room_code)
                return {"success": False, "error": "Room has expired."}
            if len(room["participants"]) >= self.max_participants:
                return {"success": False, "error": "Room is full (maximum participants reached)."}

            peer_id = "p_" + secrets.token_hex(6)
            participant = {
                "peer_id": peer_id,
                "display_name": (display_name or "Guest")[:25],
                "approved": False,
                "connected": False,
                "channel_name": None,
                "joined_at": now,
                "status": "pending_approval",  # pending_approval, approved, rejected, connected
            }
            room["participants"][peer_id] = participant
            self._peer_map[peer_id] = room_code

        logger.info(f"Participant {participant['display_name']} ({peer_id}) requested to join room {room_code}")
        return {
            "success": True,
            "peer_id": peer_id,
            "room_code": room_code,
            "display_name": participant["display_name"],
            "status": "pending_approval",
        }

    def set_approval(self, room_code: str, host_token: str, peer_id: str, approved: bool) -> dict:
        room_code = room_code.strip().upper()
        with self._lock:
            room = self._rooms.get(room_code)
            if not room or room.get("host_token") != host_token:
                return {"success": False, "error": "Unauthorized."}
            participant = room["participants"].get(peer_id)
            if not participant:
                return {"success": False, "error": "Participant not found."}

            participant["approved"] = approved
            participant["status"] = "approved" if approved else "rejected"

        logger.info(f"Host {'approved' if approved else 'rejected'} participant {peer_id} in {room_code}")
        return {
            "success": True,
            "peer_id": peer_id,
            "approved": approved,
            "display_name": participant["display_name"],
        }

    def update_photo_count(self, room_code: str, host_token: str, count: int) -> bool:
        room_code = room_code.strip().upper()
        with self._lock:
            room = self._rooms.get(room_code)
            if not room or room.get("host_token") != host_token:
                return False
            room["photo_count"] = min(int(count), self.max_photos)
            return True

    def get_participants_status(self, room_code: str, host_token: str) -> list | None:
        room_code = room_code.strip().upper()
        with self._lock:
            room = self._rooms.get(room_code)
            if not room or room.get("host_token") != host_token:
                return None
            return [
                {
                    "peer_id": p["peer_id"],
                    "display_name": p["display_name"],
                    "approved": p["approved"],
                    "status": p["status"],
                    "joined_at": p["joined_at"],
                }
                for p in room["participants"].values()
            ]

    def remove_participant(self, peer_id: str):
        with self._lock:
            room_code = self._peer_map.pop(peer_id, None)
            if room_code and room_code in self._rooms:
                self._rooms[room_code]["participants"].pop(peer_id, None)

    def destroy_room(self, room_code: str, host_token: str) -> bool:
        room_code = room_code.strip().upper()
        with self._lock:
            room = self._rooms.get(room_code)
            if not room or room.get("host_token") != host_token:
                return False
            self._destroy_room_unsafe(room_code)
            return True

    def _destroy_room_unsafe(self, room_code: str):
        room = self._rooms.pop(room_code, None)
        if room:
            host_tok = room.get("host_token")
            if host_tok:
                self._host_map.pop(host_tok, None)
            for peer_id in room.get("participants", {}):
                self._peer_map.pop(peer_id, None)
            logger.info(f"FaceShare room destroyed and cleared: {room_code}")

room_service = FaceShareRoomService.get_instance()
