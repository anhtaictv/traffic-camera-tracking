import sys
import csv
import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from src.models import Frame, Track
from tune_accident_thresholds import tune


def test_tune_writes_collision_and_speed_rows_to_csv():
    output_csv = str(Path(tempfile.mkdtemp()) / "out.csv")

    frame = Frame(camera_id="tune_cam", timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))
    moving = lambda cx: Track(track_id=1, camera_id="tune_cam", bbox=(cx - 20, 0, 40, 40))
    still = Track(track_id=2, camera_id="tune_cam", bbox=(30, 0, 40, 40))
    tracks_per_frame = [[moving(20), still], [moving(50), still], [moving(52), still]]

    with (
        patch("tune_accident_thresholds.ingest.register_camera_source"),
        patch("tune_accident_thresholds.ingest.read_frame", side_effect=[frame, frame, frame, None]),
        patch("tune_accident_thresholds.detection.detect_objects", return_value=[]),
        patch("tune_accident_thresholds.tracking.update_tracks", side_effect=tracks_per_frame),
        patch("src.detection.time.time", side_effect=[0.0, 1.0, 2.0]),
    ):
        frame_count = tune("dummy.mp4", "tune_cam", output_csv)

    assert frame_count == 3

    with open(output_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    assert rows[0] == ["frame", "kind", "track_a", "track_b", "iou", "prev_speed", "cur_speed", "decel_ratio"]
    kinds = [r[1] for r in rows[1:]]
    assert "collision" in kinds
    assert "speed" in kinds


def test_tune_stops_early_at_max_frames():
    output_csv = str(Path(tempfile.mkdtemp()) / "out.csv")
    frame = Frame(camera_id="tune_cam", timestamp=1.0, image=np.zeros((10, 10, 3), dtype=np.uint8))

    with (
        patch("tune_accident_thresholds.ingest.register_camera_source"),
        patch("tune_accident_thresholds.ingest.read_frame", return_value=frame),
        patch("tune_accident_thresholds.detection.detect_objects", return_value=[]),
        patch("tune_accident_thresholds.tracking.update_tracks", return_value=[]),
    ):
        frame_count = tune("dummy.mp4", "tune_cam", output_csv, max_frames=2)

    assert frame_count == 2  # dừng ở max_frames dù read_frame vẫn còn trả frame


if __name__ == "__main__":
    test_tune_writes_collision_and_speed_rows_to_csv()
    test_tune_stops_early_at_max_frames()
    print("OK")
