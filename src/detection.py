import time
from collections import deque

import numpy as np
import supervision as sv
from ultralytics import YOLO

from .models import Frame, Detection, Track

_TARGET_CLASSES = {"person", "car", "motorcycle", "bus", "truck"}
_model: YOLO | None = None

# ponytail: dùng time.time() làm mốc thời gian vì Track không mang timestamp
# của frame nguồn -> chỉ đúng khi detect_accident được gọi gần-real-time ngay
# sau mỗi frame, không đúng khi xử lý lại video đã ghi (batch/offline).
#
# COLLISION_IOU_THRESHOLD tune bằng scripts/tune_accident_thresholds.py trên video
# giao thông thật (đông đúc, góc quay chéo, xác nhận KHÔNG có tai nạn): max IOU quan
# sát được giữa các cặp track chỉ đứng/đi gần nhau bình thường là 0.698 trên 60 frame
# -> 0.1 gây false positive ~60% số cặp; 0.75 loại bỏ hết false positive trên data đó.
# Vẫn chưa có video tai nạn thật để xác nhận ngưỡng này đủ nhạy để bắt tai nạn thật.
_COLLISION_IOU_THRESHOLD = 0.75
_MIN_MOVING_SPEED = 20.0  # px/s, dưới ngưỡng này coi là đã dừng/đứng yên từ đầu
_DECELERATION_RATIO = 0.3  # tốc độ hiện tại < 30% tốc độ trước đó -> giảm tốc đột ngột
_track_history: dict[int, deque[tuple[float, float, float]]] = {}


def _track_center(track: Track) -> tuple[float, float]:
    x, y, w, h = track.bbox
    return (x + w / 2, y + h / 2)


def _speed(history: deque[tuple[float, float, float]]) -> float | None:
    if len(history) < 2:
        return None
    t0, x0, y0 = history[-2]
    t1, x1, y1 = history[-1]
    dt = t1 - t0
    if dt <= 0:
        return None
    return ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 / dt


def _speed_pair(track_id: int) -> tuple[float, float] | None:
    """(prev_speed, cur_speed) px/s nếu track có đủ 3 điểm history, None nếu chưa đủ."""
    history = _track_history.get(track_id)
    if history is None or len(history) < 3:
        return None
    prev_speed = _speed(deque(list(history)[:-1], maxlen=2))
    cur_speed = _speed(history)
    if prev_speed is None or cur_speed is None:
        return None
    return (prev_speed, cur_speed)


def _collision_pairs(tracks: list[Track]) -> list[tuple[int, int, float]]:
    """(track_id_a, track_id_b, iou) cho mọi cặp track có overlap > 0 (chưa áp threshold)."""
    if len(tracks) < 2:
        return []
    xyxy = np.array(
        [[x, y, x + w, y + h] for x, y, w, h in (t.bbox for t in tracks)],
        dtype=np.float32,
    )
    iou = sv.box_iou_batch(xyxy, xyxy)
    np.fill_diagonal(iou, 0.0)
    return [
        (tracks[i].track_id, tracks[j].track_id, float(iou[i, j]))
        for i in range(len(tracks))
        for j in range(i + 1, len(tracks))
        if iou[i, j] > 0
    ]


def _get_model() -> YOLO:
    global _model
    if _model is None:
        _model = YOLO("yolov8n.pt")
    return _model


def detect_objects(frame: Frame) -> list[Detection]:
    """YOLO inference trên 1 frame -> detection thô (xe/người)."""
    model = _get_model()
    result = model.predict(frame.image, verbose=False)[0]

    detections = []
    for box in result.boxes:
        class_name = model.names[int(box.cls[0])]
        if class_name not in _TARGET_CLASSES:
            continue
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        detections.append(
            Detection(
                bbox=(x1, y1, x2 - x1, y2 - y1),
                class_id=class_name,
                confidence=float(box.conf[0]),
            )
        )
    return detections


def accident_metrics(tracks: list[Track]) -> dict:
    """IOU va chạm thô + (prev_speed, cur_speed) từng track, dùng cho detect_accident
    và cho việc tune threshold (xem scripts/tune_accident_thresholds.py)."""
    now = time.time()
    for track in tracks:
        history = _track_history.setdefault(track.track_id, deque(maxlen=3))
        cx, cy = _track_center(track)
        history.append((now, cx, cy))

    return {
        "collisions": _collision_pairs(tracks),
        "speeds": {track.track_id: _speed_pair(track.track_id) for track in tracks},
    }


def detect_accident(tracks: list[Track]) -> bool:
    """True nếu phát hiện va chạm + giảm tốc đột ngột giữa các track."""
    metrics = accident_metrics(tracks)
    if not any(iou > _COLLISION_IOU_THRESHOLD for _, _, iou in metrics["collisions"]):
        return False
    return any(
        speeds is not None
        and speeds[0] > _MIN_MOVING_SPEED
        and speeds[1] < speeds[0] * _DECELERATION_RATIO
        for speeds in metrics["speeds"].values()
    )
