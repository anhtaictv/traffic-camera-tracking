import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import calibration


def test_pixel_to_world_and_back_are_inverses():
    # camera nhìn 1 mảng đường vuông 100x100 px = 10x10 met thực tế (scale 10x)
    pixel_points = [(0, 0), (100, 0), (100, 100), (0, 100)]
    world_points = [(0, 0), (10, 0), (10, 10), (0, 10)]
    calibration.set_calibration("cam1", pixel_points, world_points)

    wx, wy = calibration.pixel_to_world("cam1", 50, 50)
    assert abs(wx - 5.0) < 1e-6 and abs(wy - 5.0) < 1e-6

    px, py = calibration.world_to_pixel("cam1", wx, wy)
    assert abs(px - 50.0) < 1e-6 and abs(py - 50.0) < 1e-6


def test_uncalibrated_camera_raises():
    try:
        calibration.pixel_to_world("cam_never_calibrated", 1, 1)
        assert False, "expected ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    test_pixel_to_world_and_back_are_inverses()
    test_uncalibrated_camera_raises()
    print("OK")
