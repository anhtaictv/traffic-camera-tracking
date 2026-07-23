import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from traffic_accident_alert_worker import _extract_plates, _post_alert
from src.models import Frame, Track


def test_extract_plates_only_reads_vehicle_tracks_and_skips_no_plate():
    frame = Frame(camera_id="cam1", timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    car = Track(track_id=1, camera_id="cam1", bbox=(0, 0, 10, 10), class_id="car")
    person = Track(track_id=2, camera_id="cam1", bbox=(0, 0, 10, 10), class_id="person")
    truck_no_plate = Track(track_id=3, camera_id="cam1", bbox=(0, 0, 10, 10), class_id="truck")

    with patch(
        "traffic_accident_alert_worker.features.extract_plate",
        side_effect=lambda track, _frame: "51F12345" if track.track_id == 1 else None,
    ) as mock_plate:
        plates = _extract_plates([car, person, truck_no_plate], frame)

    assert plates == ["51F12345"]
    # person track never gets OCR'd — extract_plate is only called for vehicle-class tracks.
    assert mock_plate.call_count == 2


def test_post_alert_sends_camera_id_plates_and_thumbnail():
    frame = Frame(camera_id="cam1", timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    mock_response = MagicMock()

    with patch("traffic_accident_alert_worker.requests.post", return_value=mock_response) as mock_post:
        _post_alert("https://baotin.example/api", "secret-key", "cam-uuid", frame, ["51F12345"])

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://baotin.example/api/detections/traffic-accidents"
    assert kwargs["headers"] == {"X-Detector-Api-Key": "secret-key"}
    assert kwargs["data"] == {"cameraId": "cam-uuid", "plateNumbers": "51F12345"}
    assert "thumbnail" in kwargs["files"]
    mock_response.raise_for_status.assert_called_once()


def test_post_alert_does_not_raise_when_backend_unreachable():
    import requests

    frame = Frame(camera_id="cam1", timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    with patch(
        "traffic_accident_alert_worker.requests.post",
        side_effect=requests.ConnectionError("no route"),
    ):
        _post_alert("https://baotin.example/api", "secret-key", "cam-uuid", frame, [])  # must not raise


if __name__ == "__main__":
    test_extract_plates_only_reads_vehicle_tracks_and_skips_no_plate()
    test_post_alert_sends_camera_id_plates_and_thumbnail()
    test_post_alert_does_not_raise_when_backend_unreachable()
    print("OK")
