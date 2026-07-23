import numpy as np
import supervision as sv

from .models import Detection, Track

# ponytail: sv.ByteTrack deprecated since supervision 0.28, removed in 0.30 -> pin
# supervision<0.30 or swap to its replacement when upgrading past that version.
_trackers: dict[str, sv.ByteTrack] = {}

_class_ids: dict[str, int] = {}
_class_names: dict[int, str] = {}


def _class_to_int(class_id: str) -> int:
    if class_id not in _class_ids:
        idx = len(_class_ids)
        _class_ids[class_id] = idx
        _class_names[idx] = class_id
    return _class_ids[class_id]


def update_tracks(camera_id: str, detections: list[Detection]) -> list[Track]:
    """Bước tracker 1-camera (ByteTrack). Trả về track đang active sau khi update."""
    tracker = _trackers.setdefault(camera_id, sv.ByteTrack())

    if detections:
        xyxy = np.array(
            [[x, y, x + w, y + h] for x, y, w, h in (d.bbox for d in detections)],
            dtype=np.float32,
        )
        confidence = np.array([d.confidence for d in detections], dtype=np.float32)
        class_id = np.array([_class_to_int(d.class_id) for d in detections], dtype=int)
        sv_detections = sv.Detections(xyxy=xyxy, confidence=confidence, class_id=class_id)
    else:
        sv_detections = sv.Detections.empty()

    tracked = tracker.update_with_detections(sv_detections)

    return [
        Track(
            track_id=int(track_id),
            camera_id=camera_id,
            bbox=(float(x1), float(y1), float(x2 - x1), float(y2 - y1)),
            class_id=_class_names.get(int(cls_id)),
        )
        for (x1, y1, x2, y2), track_id, cls_id in zip(
            tracked.xyxy, tracked.tracker_id, tracked.class_id
        )
    ]


def predicted_velocity(camera_id: str, track_id: int) -> tuple[float, float] | None:
    """(vx, vy) pixel/frame từ Kalman filter nội bộ của ByteTrack cho 1 track đang
    active, None nếu camera/track không tồn tại hoặc Kalman chưa có state."""
    tracker = _trackers.get(camera_id)
    if tracker is None:
        return None
    for strack in tracker.tracked_tracks:
        if strack.external_track_id == track_id and strack.mean is not None:
            return (float(strack.mean[4]), float(strack.mean[5]))
    return None


_last_tracks: dict[str, dict[int, Track]] = {}


def departed_tracks(camera_id: str, current_tracks: list[Track]) -> list[Track]:
    """Track (kèm state đã gán trước đó: person_id, world_pos...) có ở lần update_tracks
    trước của camera này nhưng biến mất ở lần này -> ứng viên để tìm ở camera gần đó.
    Gọi 1 lần/frame, ngay sau update_tracks, với đúng list current_tracks đã xử lý xong."""
    previous = _last_tracks.get(camera_id, {})
    current_ids = {t.track_id for t in current_tracks}
    departed = [track for track_id, track in previous.items() if track_id not in current_ids]

    _last_tracks[camera_id] = {t.track_id: t for t in current_tracks}
    return departed
