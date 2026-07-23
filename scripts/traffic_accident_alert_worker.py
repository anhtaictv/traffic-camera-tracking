"""Cảnh báo tai nạn giao thông cho app cán bộ Báo Tin — CHỈ dùng detection.py (YOLO
person/car/... + rule va chạm/giảm tốc) và features.extract_plate (OCR biển số).

KHÔNG import cross_camera/reid/person_search hay features.extract_face_embedding —
phần nhận diện/theo dõi người xuyên camera của dự án này cố ý không đưa vào Báo Tin
(quyết định 2026-07-23, xem CLAUDE.md của Báo Tin và roadmap.md mục "Rung chuông pháp lý").

Cách chạy (demo, dùng video mẫu có sẵn thay vì RTSP thật):
    python scripts/traffic_accident_alert_worker.py <camera-id-thật-trong-bang-cameras> \
        --video video.mp4 --backend-url https://baotin.work.gd/api --api-key <TRAFFIC_DETECTOR_API_KEY>
"""

import argparse
import sys
import time

import cv2
import requests

sys.path.insert(0, ".")
from src import ingest, detection, tracking, features  # noqa: E402
from src.models import Track, Frame  # noqa: E402

_VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck"}
# Không gửi lại cảnh báo cho cùng 1 vụ va chạm đang diễn ra mỗi frame — 1 vụ thật kéo dài
# vài giây, nếu không có cooldown thì mỗi frame detect_accident()=True lại tạo 1 alert mới.
_ALERT_COOLDOWN_SECONDS = 30.0


def _extract_plates(tracks: list[Track], frame: Frame) -> list[str]:
    plates = []
    for track in tracks:
        if track.class_id not in _VEHICLE_CLASSES:
            continue
        plate = features.extract_plate(track, frame)
        if plate:
            plates.append(plate)
    return plates


def _post_alert(backend_url: str, api_key: str, camera_id: str, frame: Frame, plates: list[str]) -> None:
    ok, jpeg = cv2.imencode(".jpg", frame.image)
    if not ok:
        print("[traffic-accident-alert] không encode được frame, bỏ qua thumbnail")
        return
    try:
        response = requests.post(
            f"{backend_url}/detections/traffic-accidents",
            headers={"X-Detector-Api-Key": api_key},
            data={"cameraId": camera_id, "plateNumbers": ", ".join(plates)},
            files={"thumbnail": ("frame.jpg", jpeg.tobytes(), "image/jpeg")},
            timeout=10,
        )
        response.raise_for_status()
        print(f"[traffic-accident-alert] đã gửi cảnh báo, biển số phát hiện: {plates or 'không đọc được'}")
    except requests.RequestException as exc:
        print(f"[traffic-accident-alert] gửi cảnh báo thất bại: {exc}")


def run(camera_id: str, video_source: str, backend_url: str, api_key: str) -> None:
    ingest.register_camera_source(camera_id, video_source)
    last_alert_at = 0.0

    while True:
        frame = ingest.read_frame(camera_id)
        if frame is None:
            ingest.reset_camera(camera_id)  # video mẫu demo: lặp lại từ đầu khi hết
            continue

        detections = detection.detect_objects(frame)
        tracks = tracking.update_tracks(camera_id, detections)

        now = time.time()
        if now - last_alert_at > _ALERT_COOLDOWN_SECONDS and detection.detect_accident(tracks):
            plates = _extract_plates(tracks, frame)
            _post_alert(backend_url, api_key, camera_id, frame, plates)
            last_alert_at = now

        time.sleep(0.05)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("camera_id", help="id thật của camera trong bảng cameras (Báo Tin backend)")
    parser.add_argument("--video", default="video.mp4", help="đường dẫn video mẫu (demo) hoặc RTSP URL")
    parser.add_argument("--backend-url", default="http://localhost:3000", help="base URL backend Báo Tin, KHÔNG có dấu / cuối")
    parser.add_argument("--api-key", required=True, help="giá trị TRAFFIC_DETECTOR_API_KEY của backend")
    args = parser.parse_args()

    run(args.camera_id, args.video, args.backend_url.rstrip("/"), args.api_key)
