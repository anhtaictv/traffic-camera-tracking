import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import calibration
from src.cross_camera import resolve_global_identity
from src.models import Frame, Track


def _dummy_frame(camera_id: str) -> Frame:
    return Frame(camera_id=camera_id, timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))


def test_same_person_across_cameras_gets_same_global_id():
    embedding = [1.0, 0.0, 0.0]
    track_cam1 = Track(track_id=1, camera_id="camA", bbox=(0, 0, 10, 10), class_id="person")
    track_cam2 = Track(track_id=5, camera_id="camB", bbox=(0, 0, 10, 10), class_id="person")

    with patch("src.cross_camera.features.extract_face_embedding", return_value=embedding):
        id1 = resolve_global_identity(track_cam1, _dummy_frame("camA"))
        id2 = resolve_global_identity(track_cam2, _dummy_frame("camB"))

    assert id1 is not None
    assert id1 == id2
    assert track_cam1.person_id == id1 and track_cam2.person_id == id2


def test_no_face_returns_none():
    track = Track(track_id=1, camera_id="camA", bbox=(0, 0, 10, 10), class_id="person")
    with patch("src.cross_camera.features.extract_face_embedding", return_value=None):
        assert resolve_global_identity(track, _dummy_frame("camA")) is None


def test_world_pos_set_only_when_camera_calibrated():
    calibration.set_calibration(
        "camC", [(0, 0), (100, 0), (100, 100), (0, 100)], [(0, 0), (10, 0), (10, 10), (0, 10)]
    )
    calibrated_track = Track(track_id=1, camera_id="camC", bbox=(45, 45, 10, 10), class_id="person")
    uncalibrated_track = Track(track_id=2, camera_id="camD", bbox=(45, 45, 10, 10), class_id="person")

    with patch("src.cross_camera.features.extract_face_embedding", return_value=[0.0, 1.0, 0.0]):
        resolve_global_identity(calibrated_track, _dummy_frame("camC"))
        resolve_global_identity(uncalibrated_track, _dummy_frame("camD"))

    assert calibrated_track.world_pos is not None
    assert uncalibrated_track.world_pos is None


def test_travel_bearing_computed_from_consecutive_positions():
    calibration.set_calibration(
        "camC", [(0, 0), (100, 0), (100, 100), (0, 100)], [(0, 0), (10, 0), (10, 10), (0, 10)]
    )
    # cùng track_id/camera_id, di chuyển thẳng sang phải (world x tăng, y giữ nguyên) -> bearing ~90 (Đông)
    track_frame1 = Track(track_id=99, camera_id="camC", bbox=(0, 0, 20, 20), class_id="person")
    track_frame2 = Track(track_id=99, camera_id="camC", bbox=(100, 0, 20, 20), class_id="person")

    with patch("src.cross_camera.features.extract_face_embedding", return_value=[0.0, 0.0, 1.0]):
        resolve_global_identity(track_frame1, _dummy_frame("camC"))
        resolve_global_identity(track_frame2, _dummy_frame("camC"))

    assert track_frame1.travel_bearing_deg is None  # mới có 1 điểm, chưa tính được hướng
    assert abs(track_frame2.travel_bearing_deg - 90.0) < 1e-6


def test_travel_bearing_prefers_kalman_velocity_over_history():
    calibration.set_calibration(
        "camK", [(0, 0), (100, 0), (100, 100), (0, 100)], [(0, 0), (10, 0), (10, 10), (0, 10)]
    )
    # center pixel (10,10) -> world (1,1); Kalman báo vận tốc (0, 100) px/frame (đi thẳng
    # xuống trong ảnh = world y tăng = hướng Bắc) -> bearing kỳ vọng ~0, dù chưa đủ
    # history (chỉ 1 điểm) để tính theo cách cũ.
    track = Track(track_id=77, camera_id="camK", bbox=(0, 0, 20, 20), class_id="person")

    with (
        patch("src.cross_camera.features.extract_face_embedding", return_value=[0.5, 0.5, 0.5]),
        patch("src.cross_camera.tracking.predicted_velocity", return_value=(0.0, 100.0)),
    ):
        resolve_global_identity(track, _dummy_frame("camK"))

    assert track.travel_bearing_deg is not None
    assert abs(track.travel_bearing_deg - 0.0) < 1e-6


if __name__ == "__main__":
    test_same_person_across_cameras_gets_same_global_id()
    test_no_face_returns_none()
    test_world_pos_set_only_when_camera_calibrated()
    test_travel_bearing_computed_from_consecutive_positions()
    test_travel_bearing_prefers_kalman_velocity_over_history()
    print("OK")
