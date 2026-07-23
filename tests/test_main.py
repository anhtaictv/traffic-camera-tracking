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


def test_run_camera_searches_nearby_cameras_when_person_departs():
    frame1 = Frame(camera_id="cam_depart_test", timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    frame2 = Frame(camera_id="cam_depart_test", timestamp=2.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    person_track = Track(track_id=1, camera_id="cam_depart_test", bbox=(0, 0, 10, 10), class_id="person")

    with (
        patch("src.main.ingest.register_camera_source"),
        patch("src.main.ingest.read_frame", side_effect=[frame1, frame2, None]),
        patch("src.main.detection.detect_objects", return_value=[]),
        patch("src.main.tracking.update_tracks", side_effect=[[person_track], []]),
        patch("src.main.detection.detect_accident", return_value=False),
        patch(
            "src.main.cross_camera.resolve_global_identity",
            side_effect=lambda t, f: setattr(t, "person_id", 55),
        ),
        patch("src.main.storage.save_track"),
        patch("src.main.person_search.search_departed_person", return_value=[]) as mock_search,
    ):
        run_camera("cam_depart_test", "dummy_source")

    mock_search.assert_called_once_with(person_track)


if __name__ == "__main__":
    test_run_camera_extracts_and_saves_event_on_accident()
    test_run_camera_skips_feature_extraction_without_accident()
    test_handle_departure_calls_person_search_with_departed_track()
    test_run_camera_searches_nearby_cameras_when_person_departs()
    print("OK")
