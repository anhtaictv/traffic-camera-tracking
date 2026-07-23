import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import cv2
from ultralytics.utils import ASSETS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import Frame, Track
from src.detection import detect_objects, detect_accident
import src.detection as detection_module


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


def test_select_device_cpu_when_no_cuda():
    detection_module._device = None
    with patch("src.detection.torch.cuda.is_available", return_value=False):
        assert detection_module._select_device() == "cpu"
    detection_module._device = None


def test_select_device_falls_back_to_cpu_when_cuda_kernel_unsupported():
    # mô phỏng đúng bug thật đã gặp: torch.cuda.is_available() True nhưng build torch
    # không có kernel cho compute capability của GPU (vd cu130 bỏ hỗ trợ GTX 1080 Pascal)
    # -> chạy op thật trên "cuda" raise RuntimeError thay vì báo trước qua is_available().
    detection_module._device = None
    with (
        patch("src.detection.torch.cuda.is_available", return_value=True),
        patch("src.detection.torch.zeros", side_effect=RuntimeError("no kernel image")),
    ):
        assert detection_module._select_device() == "cpu"
    detection_module._device = None


def test_select_device_uses_cuda_when_available_and_working():
    detection_module._device = None
    with (
        patch("src.detection.torch.cuda.is_available", return_value=True),
        patch("src.detection.torch.zeros", return_value=MagicMock()),
    ):
        assert detection_module._select_device() == "cuda"
    detection_module._device = None


def test_select_device_caches_result_across_calls():
    detection_module._device = None
    with patch("src.detection.torch.cuda.is_available", return_value=False) as mock_available:
        detection_module._select_device()
        detection_module._select_device()
    mock_available.assert_called_once()  # chỉ check thật lần đầu, các lần sau dùng cache
    detection_module._device = None


if __name__ == "__main__":
    test_detect_objects_finds_person_and_vehicle_in_bus_jpg()
    test_detect_accident_true_on_collision_plus_sudden_deceleration()
    test_detect_accident_false_when_no_collision()
    test_select_device_cpu_when_no_cuda()
    test_select_device_falls_back_to_cpu_when_cuda_kernel_unsupported()
    test_select_device_uses_cuda_when_available_and_working()
    test_select_device_caches_result_across_calls()
    print("OK")
