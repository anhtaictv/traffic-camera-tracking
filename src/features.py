from pathlib import Path

import cv2
import numpy as np
import easyocr
import mediapipe as mp
from insightface.app import FaceAnalysis
from mediapipe.tasks.python import vision, BaseOptions

from .models import Track, Frame

_POSE_MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "pose_landmarker_lite.task"

_ocr_reader: easyocr.Reader | None = None
_face_app: FaceAnalysis | None = None
_pose_landmarker: vision.PoseLandmarker | None = None
_pixels_per_cm: dict[str, float] = {}


def _crop(track: Track, frame: Frame) -> np.ndarray:
    x, y, w, h = track.bbox
    x, y = max(int(x), 0), max(int(y), 0)
    return frame.image[y : y + int(h), x : x + int(w)]


def _get_ocr_reader() -> easyocr.Reader:
    global _ocr_reader
    if _ocr_reader is None:
        _ocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _ocr_reader


def extract_plate(track: Track, frame: Frame) -> str | None:
    """OCR biển số từ vùng crop của track."""
    crop = _crop(track, frame)
    if crop.size == 0:
        return None
    results = _get_ocr_reader().readtext(crop)
    if not results:
        return None
    _, text, confidence = max(results, key=lambda r: r[2])
    return text if confidence > 0.3 else None


def _get_face_app() -> FaceAnalysis:
    global _face_app
    if _face_app is None:
        _face_app = FaceAnalysis(name="buffalo_l")
        _face_app.prepare(ctx_id=-1)
    return _face_app


def extract_face_embedding(track: Track, frame: Frame) -> list[float] | None:
    """Embedding khuôn mặt (ArcFace) từ crop, None nếu không thấy mặt."""
    crop = _crop(track, frame)
    if crop.size == 0:
        return None
    faces = _get_face_app().get(crop)
    if not faces:
        return None
    return faces[0].normed_embedding.tolist()


def set_height_calibration(camera_id: str, pixels_per_cm: float) -> None:
    """Đăng ký hệ số quy đổi pixel->cm cho 1 camera (đo bằng vật tham chiếu thực tế)."""
    _pixels_per_cm[camera_id] = pixels_per_cm


def _get_pose_landmarker() -> vision.PoseLandmarker:
    global _pose_landmarker
    if _pose_landmarker is None:
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(_POSE_MODEL_PATH)),
            running_mode=vision.RunningMode.IMAGE,
        )
        _pose_landmarker = vision.PoseLandmarker.create_from_options(options)
    return _pose_landmarker


def extract_pose_height(track: Track, frame: Frame) -> float | None:
    """Ước lượng chiều cao (cm) từ pose landmarks. Cần set_height_calibration(camera_id, ...) trước."""
    # ponytail: quy đổi pixel->cm tuyến tính theo 1 hệ số cố định mỗi camera,
    # không bù phối cảnh theo khoảng cách -> chỉ chính xác gần vị trí đã hiệu chuẩn.
    # Nâng cấp: dùng calibration.pixel_to_world (ground-plane) + chiều cao camera thật.
    scale = _pixels_per_cm.get(track.camera_id)
    if scale is None:
        return None

    crop = _crop(track, frame)
    if crop.size == 0:
        return None

    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = _get_pose_landmarker().detect(mp_image)
    if not result.pose_landmarks:
        return None

    landmarks = result.pose_landmarks[0]
    nose_y = landmarks[vision.PoseLandmark.NOSE.value].y
    foot_y = (
        landmarks[vision.PoseLandmark.LEFT_ANKLE.value].y
        + landmarks[vision.PoseLandmark.RIGHT_ANKLE.value].y
    ) / 2

    height_px = abs(foot_y - nose_y) * crop.shape[0]
    return height_px / scale
