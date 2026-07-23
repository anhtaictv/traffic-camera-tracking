from . import ingest, detection, tracking, features, storage, cross_camera, person_search
from .models import Frame, Track, VehicleInfo, DriverInfo, AccidentEvent

_VEHICLE_CLASSES = {"car", "motorcycle", "bus", "truck"}


def run_camera(camera_id: str, source: str) -> None:
    """Vòng lặp 1 camera: detect -> track -> ghép person_id -> lưu track ->
    (nếu tai nạn) trích đặc điểm + lưu event -> (nếu person rời khung hình)
    tìm người đó ở camera GIS gần đó."""
    ingest.register_camera_source(camera_id, source)

    while True:
        frame = ingest.read_frame(camera_id)
        if frame is None:
            break

        tracks = tracking.update_tracks(camera_id, detection.detect_objects(frame))
        for track in tracks:
            track.timestamp = frame.timestamp
            if track.class_id == "person":
                cross_camera.resolve_global_identity(track, frame)
            storage.save_track(track)

        if detection.detect_accident(tracks):
            _handle_accident(camera_id, frame, tracks)

        for departed in tracking.departed_tracks(camera_id, tracks):
            if departed.class_id == "person" and departed.person_id is not None:
                _handle_departure(departed)


def _handle_accident(camera_id: str, frame: Frame, tracks: list[Track]) -> None:
    """Trích đặc điểm xe (biển số) + người lái (mặt, chiều cao) rồi lưu 1 accident event."""
    vehicle_track = next((t for t in tracks if t.class_id in _VEHICLE_CLASSES), None)
    person_track = next((t for t in tracks if t.class_id == "person"), None)

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
