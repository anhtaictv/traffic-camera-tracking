from dataclasses import dataclass
from typing import Optional

@dataclass
class Frame:
    camera_id: str
    timestamp: float
    image: "np.ndarray"

@dataclass
class Detection:
    bbox: tuple[float, float, float, float]  # x, y, w, h
    class_id: str
    confidence: float

@dataclass
class Track:
    track_id: int
    camera_id: str
    bbox: tuple[float, float, float, float]
    class_id: Optional[str] = None
    embedding: Optional[list[float]] = None
    world_pos: Optional[tuple[float, float]] = None
    person_id: Optional[int] = None
    timestamp: Optional[float] = None
    travel_bearing_deg: Optional[float] = None

@dataclass
class VehicleInfo:
    track_id: int
    plate: Optional[str] = None
    color: Optional[str] = None
    vehicle_type: Optional[str] = None

@dataclass
class DriverInfo:
    track_id: int
    height_cm: Optional[float] = None
    face_embedding: Optional[list[float]] = None

@dataclass
class AccidentEvent:
    camera_id: str
    timestamp: float
    track_ids: list[int]
