import sys
import time
from pathlib import Path
from unittest.mock import patch

import cv2
from ultralytics.utils import ASSETS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import Frame, Track
from src.detection import detect_objects, detect_accident


def test_detect_objects_finds_person_and_vehicle_in_bus_jpg():
    image = cv2.imread(str(Path(ASSETS) / "bus.jpg"))
    frame = Frame(camera_id="cam1", timestamp=time.time(), image=image)

    detections = detect_objects(frame)
    classes = {d.class_id for d in detections}

    assert len(detections) > 0
    assert "person" in classes
    assert all(0.0 <= d.confidence <= 1.0 for d in detections)
    assert all(w > 0 and h > 0 for _, _, w, h in (d.bbox for d in detections))


def test_detect_accident_true_on_collision_plus_sudden_deceleration():
    moving = lambda cx: Track(track_id=101, camera_id="camA", bbox=(cx - 20, 0, 40, 40))
    still = Track(track_id=102, camera_id="camA", bbox=(30, 0, 40, 40))

    with patch("src.detection.time.time", side_effect=[0.0, 1.0, 2.0]):
        assert detect_accident([moving(20), still]) is False  # frame 1: chưa đủ history
        assert detect_accident([moving(50), still]) is False  # frame 2: vừa va chạm, chưa có decel
        assert detect_accident([moving(52), still]) is True  # frame 3: va chạm + giảm tốc đột ngột


def test_detect_accident_false_when_no_collision():
    far_apart = [
        Track(track_id=201, camera_id="camB", bbox=(0, 0, 20, 20)),
        Track(track_id=202, camera_id="camB", bbox=(500, 500, 20, 20)),
    ]
    with patch("src.detection.time.time", side_effect=[0.0, 1.0, 2.0]):
        for _ in range(3):
            assert detect_accident(far_apart) is False


if __name__ == "__main__":
    test_detect_objects_finds_person_and_vehicle_in_bus_jpg()
    test_detect_accident_true_on_collision_plus_sudden_deceleration()
    test_detect_accident_false_when_no_collision()
    print("OK")
