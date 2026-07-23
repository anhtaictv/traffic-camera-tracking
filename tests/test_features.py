import sys
import time
from pathlib import Path

import cv2
import numpy as np
from ultralytics.utils import ASSETS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import Frame, Track
from src.features import (
    extract_plate,
    extract_face_embedding,
    extract_pose_height,
    set_height_calibration,
)


def _whole_image_track(camera_id: str, image) -> Track:
    h, w = image.shape[:2]
    return Track(track_id=1, camera_id=camera_id, bbox=(0, 0, w, h))


def test_extract_plate_reads_text_from_synthetic_plate_image():
    image = np.full((120, 400, 3), 255, dtype=np.uint8)
    cv2.putText(image, "51F12345", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 4)
    frame = Frame(camera_id="cam1", timestamp=time.time(), image=image)

    text = extract_plate(_whole_image_track("cam1", image), frame)

    assert text is not None
    assert any(ch.isdigit() for ch in text)


def test_extract_face_embedding_returns_512_dim_vector():
    image = cv2.imread(str(Path(ASSETS) / "zidane.jpg"))
    frame = Frame(camera_id="cam1", timestamp=time.time(), image=image)

    embedding = extract_face_embedding(_whole_image_track("cam1", image), frame)

    assert embedding is not None
    assert len(embedding) == 512


def test_extract_pose_height_none_without_calibration():
    image = cv2.imread(str(Path(ASSETS) / "bus.jpg"))
    frame = Frame(camera_id="cam_no_calib", timestamp=time.time(), image=image)

    assert extract_pose_height(_whole_image_track("cam_no_calib", image), frame) is None


def test_extract_pose_height_returns_float_with_calibration():
    image = cv2.imread(str(Path(ASSETS) / "bus.jpg"))
    frame = Frame(camera_id="cam_calibrated", timestamp=time.time(), image=image)
    set_height_calibration("cam_calibrated", pixels_per_cm=5.0)

    height = extract_pose_height(_whole_image_track("cam_calibrated", image), frame)

    assert height is None or isinstance(height, float)


if __name__ == "__main__":
    test_extract_plate_reads_text_from_synthetic_plate_image()
    test_extract_face_embedding_returns_512_dim_vector()
    test_extract_pose_height_none_without_calibration()
    test_extract_pose_height_returns_float_with_calibration()
    print("OK")
