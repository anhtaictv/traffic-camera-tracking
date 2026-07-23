import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import run_camera, _handle_departure
from src.models import Frame, Track


def test_run_camera_extracts_and_saves_event_on_accident():
    frame = Frame(camera_id="cam1", timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    vehicle_track = Track(track_id=1, camera_id="cam1", bbox=(0, 0, 10, 10), class_id="car")
    person_track = Track(track_id=2, camera_id="cam1", bbox=(0, 0, 10, 10), class_id="person")

    with (
        patch("src.main.ingest.register_camera_source"),
        patch("src.main.ingest.read_frame", side_effect=[frame, None]),
        patch("src.main.detection.detect_objects", return_value=[]),
        patch("src.main.tracking.update_tracks", return_value=[vehicle_track, person_track]),
        patch("src.main.detection.detect_accident", return_value=True),
        patch("src.main.features.extract_plate", return_value="51F12345") as mock_plate,
        patch("src.main.features.extract_pose_height", return_value=170.0) as mock_height,
        patch("src.main.features.extract_face_embedding", return_value=[0.1, 0.2]) as mock_face,
        patch("src.main.storage.save_track") as mock_save_track,
        patch("src.main.storage.save_event") as mock_save_event,
    ):
        run_camera("cam1", "dummy_source")

        mock_plate.assert_called_once_with(vehicle_track, frame)
        mock_height.assert_called_once_with(person_track, frame)
        mock_face.assert_called_once_with(person_track, frame)
        assert mock_save_track.call_count == 2

        mock_save_event.assert_called_once()
        event, vehicle, driver = mock_save_event.call_args[0]
        assert event.track_ids == [1, 2]
        assert vehicle.plate == "51F12345" and vehicle.vehicle_type == "car"
        assert driver.height_cm == 170.0 and driver.face_embedding == [0.1, 0.2]


def test_run_camera_skips_feature_extraction_without_accident():
    camera_id = "cam1_no_accident"
    frame = Frame(camera_id=camera_id, timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    track = Track(track_id=1, camera_id=camera_id, bbox=(0, 0, 10, 10), class_id="car")

    with (
        patch("src.main.ingest.register_camera_source"),
        patch("src.main.ingest.read_frame", side_effect=[frame, None]),
        patch("src.main.detection.detect_objects", return_value=[]),
        patch("src.main.tracking.update_tracks", return_value=[track]),
        patch("src.main.detection.detect_accident", return_value=False),
        patch("src.main.features.extract_plate") as mock_plate,
        patch("src.main.storage.save_track"),
        patch("src.main.storage.save_event") as mock_save_event,
    ):
        run_camera(camera_id, "dummy_source")

        mock_plate.assert_not_called()
        mock_save_event.assert_not_called()


def test_handle_departure_calls_person_search_with_departed_track():
    departed = Track(track_id=1, camera_id="camA", bbox=(0, 0, 10, 10), class_id="person", person_id=7)

    with patch(
        "src.main.person_search.search_departed_person", return_value=[{"camera_id": "camB"}]
    ) as mock_search:
        _handle_departure(departed)

    mock_search.assert_called_once_with(departed)


def test_run_camera_searches_nearby_cameras_when_departed_track_already_has_person_id():
    """resolve_global_identity giờ chỉ chạy trong _handle_accident (không còn mỗi frame)
    -> person_search khi rời khung hình chỉ hoạt động cho track đã có person_id sẵn
    (vd: đã từng dính tai nạn trước đó). _DETECT_INTERVAL=2 -> cần 3 frame (frame_count
    0,1,2) để có đủ 2 lần detect thật (0 và 2), departed_tracks chỉ được check ở frame detect."""
    frames = [
        Frame(camera_id="cam_depart_test", timestamp=float(i), image=np.zeros((10, 10, 3), dtype=np.uint8))
        for i in range(3)
    ]
    person_track = Track(
        track_id=1, camera_id="cam_depart_test", bbox=(0, 0, 10, 10), class_id="person", person_id=55
    )

    with (
        patch("src.main.ingest.register_camera_source"),
        patch("src.main.ingest.read_frame", side_effect=[*frames, None]),
        patch("src.main.detection.detect_objects", return_value=[]),
        patch("src.main.tracking.update_tracks", side_effect=[[person_track], []]),
        patch("src.main.detection.detect_accident", return_value=False),
        patch("src.main.storage.save_track"),
        patch("src.main.person_search.search_departed_person", return_value=[]) as mock_search,
    ):
        run_camera("cam_depart_test", "dummy_source")

    mock_search.assert_called_once_with(person_track)


def test_run_camera_does_not_search_when_person_never_resolved():
    """Không tai nạn -> resolve_global_identity không chạy -> person_id vẫn None khi
    track rời khung hình -> không gọi person_search. 3 frame để có đủ 2 lần detect thật
    (frame_count 0 và 2, xem test phía trên)."""
    frames = [
        Frame(camera_id="cam_no_resolve", timestamp=float(i), image=np.zeros((10, 10, 3), dtype=np.uint8))
        for i in range(3)
    ]
    person_track = Track(track_id=1, camera_id="cam_no_resolve", bbox=(0, 0, 10, 10), class_id="person")

    with (
        patch("src.main.ingest.register_camera_source"),
        patch("src.main.ingest.read_frame", side_effect=[*frames, None]),
        patch("src.main.detection.detect_objects", return_value=[]),
        patch("src.main.tracking.update_tracks", side_effect=[[person_track], []]),
        patch("src.main.detection.detect_accident", return_value=False),
        patch("src.main.storage.save_track"),
        patch("src.main.person_search.search_departed_person", return_value=[]) as mock_search,
    ):
        run_camera("cam_no_resolve", "dummy_source")

    mock_search.assert_not_called()


def test_run_camera_skips_detect_and_extrapolates_bbox_using_kalman_velocity():
    """_DETECT_INTERVAL=2 -> detect_objects chỉ gọi ở frame_count=0 (detect thật),
    frame_count=1 bị skip và dùng tracking.predicted_velocity để dịch bbox thay vì detect lại."""
    frames = [
        Frame(camera_id="cam_skip_test", timestamp=float(i), image=np.zeros((10, 10, 3), dtype=np.uint8))
        for i in range(2)
    ]
    track = Track(track_id=1, camera_id="cam_skip_test", bbox=(100.0, 100.0, 20, 20), class_id="car")

    with (
        patch("src.main.ingest.register_camera_source"),
        patch("src.main.ingest.read_frame", side_effect=[*frames, None]),
        patch("src.main.detection.detect_objects", return_value=[]) as mock_detect,
        patch("src.main.tracking.update_tracks", return_value=[track]) as mock_update,
        patch("src.main.tracking.predicted_velocity", return_value=(10.0, 0.0)),
        patch("src.main.detection.detect_accident", return_value=False),
        patch("src.main.storage.save_track") as mock_save,
    ):
        run_camera("cam_skip_test", "dummy_source")

    mock_detect.assert_called_once()
    mock_update.assert_called_once()
    saved_bboxes = [call.args[0].bbox for call in mock_save.call_args_list]
    assert saved_bboxes[0] == (100.0, 100.0, 20, 20)  # frame detect thật
    assert saved_bboxes[1] == (105.0, 100.0, 20, 20)  # frame ngoại suy: step_fraction=0.5, vx=10 -> +5


if __name__ == "__main__":
    test_run_camera_extracts_and_saves_event_on_accident()
    test_run_camera_skips_feature_extraction_without_accident()
    test_handle_departure_calls_person_search_with_departed_track()
    test_run_camera_searches_nearby_cameras_when_departed_track_already_has_person_id()
    test_run_camera_does_not_search_when_person_never_resolved()
    test_run_camera_skips_detect_and_extrapolates_bbox_using_kalman_velocity()
    print("OK")
