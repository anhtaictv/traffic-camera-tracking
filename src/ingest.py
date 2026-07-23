import time

import cv2

from .models import Frame

_captures: dict[str, cv2.VideoCapture] = {}
_sources: dict[str, str] = {}


def register_camera_source(camera_id: str, source: str) -> None:
    """Đăng ký nguồn video cho 1 camera (đường dẫn file hoặc RTSP URL)."""
    _sources[camera_id] = source


def reset_camera(camera_id: str) -> None:
    """Đóng capture hiện tại của 1 camera để read_frame mở lại từ đầu (lặp video)."""
    capture = _captures.pop(camera_id, None)
    if capture is not None:
        capture.release()


def read_frame(camera_id: str) -> Frame | None:
    """Lấy frame kế tiếp từ camera. None nếu stream kết thúc."""
    if camera_id not in _captures:
        source = _sources.get(camera_id)
        if source is None:
            raise ValueError(f"Camera {camera_id} chưa được đăng ký, gọi register_camera_source trước")
        _captures[camera_id] = cv2.VideoCapture(source)

    ok, image = _captures[camera_id].read()
    if not ok:
        return None
    return Frame(camera_id=camera_id, timestamp=time.time(), image=image)
