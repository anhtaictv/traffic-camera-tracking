from . import camera_registry, storage
from .models import Track

_DEFAULT_RADIUS_M = 500.0


def search_departed_person(track: Track, radius_m: float = _DEFAULT_RADIUS_M) -> list[dict]:
    """Sau khi 1 person track biến mất khỏi track.camera_id: tìm track cùng person_id
    đã được lưu ở các camera GIS gần đó (bán kính radius_m), từ lúc track biến mất trở đi.
    Trả về [] nếu track chưa có person_id hoặc chưa tìm thấy gì."""
    if track.person_id is None:
        return []

    nearby = camera_registry.nearby_cameras(track.camera_id, radius_m, track.travel_bearing_deg)
    camera_ids = [camera_id for camera_id, _ in nearby]
    return storage.find_person_sightings(
        track.person_id, camera_ids, since_timestamp=track.timestamp or 0.0
    )
