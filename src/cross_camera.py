import math
from collections import deque

from . import features, calibration, reid, tracking
from .models import Track, Frame

# ponytail: world_pos giả định trục x=Đông, y=Bắc (mét) -> bearing tính từ đây so
# sánh trực tiếp được với facing_deg/bearing của camera_registry (0=Bắc, 90=Đông).
# Khi calibration.set_calibration, world_points phải theo đúng quy ước này.
_position_history: dict[tuple[str, int], deque[tuple[float, float]]] = {}


def _track_center(track: Track) -> tuple[float, float]:
    x, y, w, h = track.bbox
    return (x + w / 2, y + h / 2)


def _record_position(track: Track) -> None:
    key = (track.camera_id, track.track_id)
    _position_history.setdefault(key, deque(maxlen=5)).append(track.world_pos)


def _bearing_from_history(track: Track) -> float | None:
    """Hướng đi thô từ 2 điểm world_pos gần nhất -> nhạy nhiễu, dùng khi Kalman chưa có."""
    history = _position_history.get((track.camera_id, track.track_id))
    if history is None or len(history) < 2:
        return None
    (x0, y0), (x1, y1) = history[-2], history[-1]
    dx, dy = x1 - x0, y1 - y0
    if dx == 0 and dy == 0:
        return None
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def _bearing_from_kalman(track: Track) -> float | None:
    """Hướng đi từ vận tốc Kalman filter nội bộ của ByteTrack (mượt hơn history thô)."""
    velocity = tracking.predicted_velocity(track.camera_id, track.track_id)
    if velocity is None:
        return None
    vx, vy = velocity
    if vx == 0 and vy == 0:
        return None

    cx, cy = _track_center(track)
    next_world = calibration.pixel_to_world(track.camera_id, cx + vx, cy + vy)
    dx, dy = next_world[0] - track.world_pos[0], next_world[1] - track.world_pos[1]
    if dx == 0 and dy == 0:
        return None
    return (math.degrees(math.atan2(dx, dy)) + 360) % 360


def resolve_global_identity(track: Track, frame: Frame) -> int | None:
    """Ghép 1 track người với global person_id xuyên camera (face embedding), kèm
    world_pos + travel_bearing_deg (ưu tiên Kalman, fallback history thô) nếu camera
    đã calibrate."""
    embedding = features.extract_face_embedding(track, frame)
    if embedding is None:
        return None
    track.embedding = embedding  # tránh gọi extract_face_embedding lại lần 2 ở nơi khác

    person_id = reid.match_person(embedding)
    if person_id is None:
        person_id = reid.register_person(embedding)

    try:
        track.world_pos = calibration.pixel_to_world(track.camera_id, *_track_center(track))
        _record_position(track)
        kalman_bearing = _bearing_from_kalman(track)
        # không dùng "or": bearing 0.0 (hướng Bắc chính xác) là giá trị hợp lệ, không phải falsy-None
        track.travel_bearing_deg = kalman_bearing if kalman_bearing is not None else _bearing_from_history(track)
    except ValueError:
        pass  # camera chưa calibrate -> vẫn trả về person_id, chỉ thiếu world_pos

    track.person_id = person_id
    return person_id
