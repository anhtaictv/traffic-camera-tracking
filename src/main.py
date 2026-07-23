from dataclasses import replace

from . import ingest, detection, tracking, features, storage, cross_camera, person_search
from .models import Frame, Track, VehicleInfo, DriverInfo, AccidentEvent

_VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck"}

# detect_objects (YOLO) là bước tốn nhất còn lại (~57ms/frame đo thực tế trên GPU) -> chỉ
# chạy thật mỗi N frame, các frame giữa ngoại suy bbox từ vận tốc Kalman của ByteTrack
# (tracking.predicted_velocity, đã có sẵn) thay vì detect lại. Đổi lại: vị trí ở frame
# ngoại suy là ước lượng tuyến tính, không phải detect thật -> sai số tăng dần nếu vật
# thể đổi hướng đột ngột giữa 2 lần detect thật.
_DETECT_INTERVAL = 2


def run_camera(camera_id: str, source: str) -> None:
    """Vòng lặp 1 camera: detect (mỗi N frame, xem _DETECT_INTERVAL) -> track -> ghép
    person_id -> lưu track -> (nếu tai nạn) trích đặc điểm + lưu event -> (nếu person rời
    khung hình) tìm người đó ở camera GIS gần đó."""
    ingest.register_camera_source(camera_id, source)
    frame_count = 0
    last_real_tracks: list[Track] = []

    while True:
        frame = ingest.read_frame(camera_id)
        if frame is None:
            break

        remainder = frame_count % _DETECT_INTERVAL
        is_detect_frame = remainder == 0
        if is_detect_frame:
            tracks = tracking.update_tracks(camera_id, detection.detect_objects(frame))
            last_real_tracks = tracks
        else:
            tracks = _extrapolate_tracks(camera_id, last_real_tracks, remainder / _DETECT_INTERVAL)
        frame_count += 1

        for track in tracks:
            track.timestamp = frame.timestamp
            storage.save_track(track)

        if detection.detect_accident(tracks):
            _handle_accident(camera_id, frame, tracks)

        if is_detect_frame:
            for departed in tracking.departed_tracks(camera_id, tracks):
                if departed.class_id == "person" and departed.person_id is not None:
                    _handle_departure(departed)


def _extrapolate_tracks(camera_id: str, tracks: list[Track], step_fraction: float) -> list[Track]:
    """Ngoại suy bbox của track từ lần detect thật gần nhất, dùng vận tốc Kalman
    (tracking.predicted_velocity) -> tránh phải detect lại mỗi frame."""
    predicted = []
    for track in tracks:
        velocity = tracking.predicted_velocity(camera_id, track.track_id)
        if velocity is None:
            predicted.append(track)
            continue
        vx, vy = velocity
        x, y, w, h = track.bbox
        predicted.append(replace(track, bbox=(x + vx * step_fraction, y + vy * step_fraction, w, h)))
    return predicted


def _handle_accident(camera_id: str, frame: Frame, tracks: list[Track]) -> None:
    """Trích đặc điểm xe (biển số) + người lái (mặt, chiều cao) rồi lưu 1 accident event."""
    vehicle_track = next((t for t in tracks if t.class_id in _VEHICLE_CLASSES), None)
    person_track = next((t for t in tracks if t.class_id == "person"), None)
    if person_track is not None:
        cross_camera.resolve_global_identity(person_track, frame)

    plate = features.extract_plate(vehicle_track, frame) if vehicle_track else None
    height = features.extract_pose_height(person_track, frame) if person_track else None
    # embedding đã được resolve_global_identity tính trong vòng lặp chính -> tái dùng,
    # không gọi lại extract_face_embedding (tốn 1 lần inference InsightFace nữa).
    face = person_track.embedding if person_track else None

    event = AccidentEvent(
        camera_id=camera_id,
        timestamp=frame.timestamp,
        track_ids=[t.track_id for t in tracks],
    )
    vehicle = VehicleInfo(
        track_id=vehicle_track.track_id if vehicle_track else -1,
        plate=plate,
        vehicle_type=vehicle_track.class_id if vehicle_track else None,
    )
    driver = DriverInfo(
        track_id=person_track.track_id if person_track else -1,
        height_cm=height,
        face_embedding=face,
    )
    storage.save_event(event, vehicle, driver)


def _handle_departure(departed_track: Track) -> None:
    """Log nơi 1 người vừa xuất hiện ở camera GIS gần đó sau khi rời khỏi track hiện tại."""
    sightings = person_search.search_departed_person(departed_track)
    if sightings:
        print(
            f"[person_search] person {departed_track.person_id} rời {departed_track.camera_id}, "
            f"tìm thấy ở: {sightings}"
        )


if __name__ == "__main__":
    import sys

    run_camera(sys.argv[1], sys.argv[2])
