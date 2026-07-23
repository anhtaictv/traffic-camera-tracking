import numpy as np
import cv2

_homographies: dict[str, np.ndarray] = {}


def set_calibration(
    camera_id: str,
    pixel_points: list[tuple[float, float]],
    world_points: list[tuple[float, float]],
) -> None:
    """Tính & lưu homography camera từ >=4 cặp điểm pixel<->world (mặt phẳng đường)."""
    H, _ = cv2.findHomography(
        np.array(pixel_points, dtype=np.float32), np.array(world_points, dtype=np.float32)
    )
    if H is None:
        raise ValueError(f"Không tính được homography cho camera {camera_id}")
    _homographies[camera_id] = H


def _get_homography(camera_id: str) -> np.ndarray:
    H = _homographies.get(camera_id)
    if H is None:
        raise ValueError(f"Camera {camera_id} chưa được calibrate, gọi set_calibration trước")
    return H


def pixel_to_world(camera_id: str, x: float, y: float) -> tuple[float, float]:
    """Pixel (mặt phẳng ground) -> tọa độ world (mét), dùng calibration đã lưu."""
    point = _get_homography(camera_id) @ np.array([x, y, 1.0])
    return (point[0] / point[2], point[1] / point[2])


def world_to_pixel(camera_id: str, wx: float, wy: float) -> tuple[float, float]:
    """World -> pixel, nghịch đảo của pixel_to_world."""
    point = np.linalg.inv(_get_homography(camera_id)) @ np.array([wx, wy, 1.0])
    return (point[0] / point[2], point[1] / point[2])
