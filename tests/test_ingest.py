import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest import register_camera_source, read_frame, reset_camera


def _make_test_video(num_frames: int) -> str:
    path = str(Path(tempfile.mkdtemp()) / "test.mp4")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10, (32, 32))
    for _ in range(num_frames):
        writer.write(np.zeros((32, 32, 3), dtype=np.uint8))
    writer.release()
    return path


def test_read_frame_returns_frames_then_none_at_end():
    video_path = _make_test_video(3)
    register_camera_source("cam_test", video_path)

    frames = [read_frame("cam_test") for _ in range(3)]
    end = read_frame("cam_test")

    assert all(f is not None for f in frames)
    assert all(f.camera_id == "cam_test" for f in frames)
    assert end is None


def test_read_frame_unregistered_camera_raises():
    try:
        read_frame("cam_never_registered")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_reset_camera_loops_video_back_to_start():
    video_path = _make_test_video(2)
    register_camera_source("cam_loop", video_path)

    assert read_frame("cam_loop") is not None
    assert read_frame("cam_loop") is not None
    assert read_frame("cam_loop") is None  # hết video

    reset_camera("cam_loop")

    assert read_frame("cam_loop") is not None  # đã mở lại từ đầu, không còn None mãi


if __name__ == "__main__":
    test_read_frame_returns_frames_then_none_at_end()
    test_read_frame_unregistered_camera_raises()
    test_reset_camera_loops_video_back_to_start()
    print("OK")
