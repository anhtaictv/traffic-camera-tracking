import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import Detection, Track
from src.tracking import update_tracks, departed_tracks, predicted_velocity


def test_same_object_keeps_track_id_across_frames():
    d1 = [Detection(bbox=(10, 10, 40, 40), class_id="car", confidence=0.9)]
    d2 = [Detection(bbox=(12, 12, 40, 40), class_id="car", confidence=0.9)]

    t1 = update_tracks("cam1", d1)
    t2 = update_tracks("cam1", d2)

    assert len(t1) == 1 and len(t2) == 1
    assert t1[0].track_id == t2[0].track_id
    assert t1[0].class_id == "car" and t2[0].class_id == "car"


def test_empty_detections_returns_empty_list():
    assert update_tracks("cam2", []) == []


def test_departed_tracks_reports_tracks_missing_from_previous_call():
    t1 = Track(track_id=1, camera_id="cam_dep", bbox=(0, 0, 10, 10), person_id=7)
    t2 = Track(track_id=2, camera_id="cam_dep", bbox=(0, 0, 10, 10), person_id=8)

    first = departed_tracks("cam_dep", [t1, t2])
    assert first == []

    second = departed_tracks("cam_dep", [t2])  # t1 đã biến mất

    assert len(second) == 1
    assert second[0].track_id == 1
    assert second[0].person_id == 7


def test_predicted_velocity_reflects_movement_direction():
    d1 = [Detection(bbox=(10, 10, 40, 40), class_id="car", confidence=0.9)]
    d2 = [Detection(bbox=(20, 10, 40, 40), class_id="car", confidence=0.9)]  # dịch sang phải 10px

    t1 = update_tracks("cam_velocity", d1)
    update_tracks("cam_velocity", d2)

    velocity = predicted_velocity("cam_velocity", t1[0].track_id)

    assert velocity is not None
    vx, vy = velocity
    assert vx > 0  # đang di chuyển sang phải (x tăng)
    assert abs(vy) < 1e-6  # không di chuyển theo trục y


def test_predicted_velocity_unknown_camera_or_track_returns_none():
    assert predicted_velocity("cam_never_seen", 1) is None
    update_tracks("cam_velocity", [Detection(bbox=(0, 0, 10, 10), class_id="car", confidence=0.9)])
    assert predicted_velocity("cam_velocity", 9999) is None


if __name__ == "__main__":
    test_same_object_keeps_track_id_across_frames()
    test_empty_detections_returns_empty_list()
    test_departed_tracks_reports_tracks_missing_from_previous_call()
    test_predicted_velocity_reflects_movement_direction()
    test_predicted_velocity_unknown_camera_or_track_returns_none()
    print("OK")
