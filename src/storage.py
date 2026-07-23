import json
import sqlite3
from pathlib import Path

from .models import Track, VehicleInfo, DriverInfo, AccidentEvent

# ponytail: sqlite tạm thay Postgres/PostGIS thật (chưa có hạ tầng DB ở Phase 0)
# -> nâng cấp lên Postgres khi có server, giữ nguyên schema 2 bảng dưới.
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tracking.db"


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, coltype: str) -> None:
    """Thêm cột nếu chưa có -> DB cũ tạo trước khi thêm cột này vẫn tự khớp schema mới
    (sqlite không tự migrate qua CREATE TABLE IF NOT EXISTS)."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")


def _get_connection() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS suspect_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER NOT NULL,
            camera_id TEXT NOT NULL,
            world_x REAL,
            world_y REAL
        )"""
    )
    _ensure_column(conn, "suspect_tracks", "person_id", "INTEGER")
    _ensure_column(conn, "suspect_tracks", "timestamp", "REAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS accident_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            track_ids TEXT NOT NULL,
            vehicle_plate TEXT,
            vehicle_color TEXT,
            vehicle_type TEXT,
            driver_height_cm REAL,
            driver_face_embedding TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS cameras (
            camera_id TEXT PRIMARY KEY,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            facing_deg REAL NOT NULL,
            fov_deg REAL NOT NULL
        )"""
    )
    conn.commit()
    return conn


def save_camera(camera_id: str, lat: float, lng: float, facing_deg: float, fov_deg: float) -> None:
    """Lưu/update vị trí GIS + góc nhìn 1 camera (bảng cameras)."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO cameras (camera_id, lat, lng, facing_deg, fov_deg) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(camera_id) DO UPDATE SET
                   lat=excluded.lat, lng=excluded.lng, facing_deg=excluded.facing_deg, fov_deg=excluded.fov_deg""",
            (camera_id, lat, lng, facing_deg, fov_deg),
        )
        conn.commit()
    finally:
        conn.close()


def list_cameras() -> list[dict]:
    """Danh sách camera đã đăng ký (vị trí GIS + góc nhìn)."""
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT camera_id, lat, lng, facing_deg, fov_deg FROM cameras").fetchall()
    finally:
        conn.close()
    return [
        {"camera_id": r[0], "lat": r[1], "lng": r[2], "facing_deg": r[3], "fov_deg": r[4]} for r in rows
    ]


def save_track(track: Track) -> None:
    """Ghi/update track vào DB (bảng suspect_tracks)."""
    wx, wy = track.world_pos if track.world_pos else (None, None)
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO suspect_tracks (track_id, camera_id, world_x, world_y, person_id, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (track.track_id, track.camera_id, wx, wy, track.person_id, track.timestamp),
        )
        conn.commit()
    finally:
        conn.close()


def find_person_sightings(person_id: int, camera_ids: list[str], since_timestamp: float) -> list[dict]:
    """Track của 1 person_id đã lưu ở các camera chỉ định, từ since_timestamp trở đi."""
    if not camera_ids:
        return []
    placeholders = ",".join("?" * len(camera_ids))
    conn = _get_connection()
    try:
        rows = conn.execute(
            f"""SELECT track_id, camera_id, world_x, world_y, timestamp FROM suspect_tracks
                WHERE person_id = ? AND camera_id IN ({placeholders}) AND timestamp >= ?
                ORDER BY timestamp""",
            (person_id, *camera_ids, since_timestamp),
        ).fetchall()
    finally:
        conn.close()
    return [
        {"track_id": r[0], "camera_id": r[1], "world_x": r[2], "world_y": r[3], "timestamp": r[4]}
        for r in rows
    ]


def find_person_track_history(person_id: int) -> list[dict]:
    """Toàn bộ track của 1 person_id, mọi camera, sắp theo thời gian (dùng để vẽ lộ trình)."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            """SELECT track_id, camera_id, world_x, world_y, timestamp FROM suspect_tracks
               WHERE person_id = ? ORDER BY timestamp""",
            (person_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {"track_id": r[0], "camera_id": r[1], "world_x": r[2], "world_y": r[3], "timestamp": r[4]}
        for r in rows
    ]


def save_event(event: AccidentEvent, vehicle: VehicleInfo, driver: DriverInfo) -> None:
    """Ghi sự kiện tai nạn + đặc điểm xe/người vào DB."""
    conn = _get_connection()
    try:
        conn.execute(
            """INSERT INTO accident_events
               (camera_id, timestamp, track_ids, vehicle_plate, vehicle_color, vehicle_type,
                driver_height_cm, driver_face_embedding)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.camera_id,
                event.timestamp,
                json.dumps(event.track_ids),
                vehicle.plate,
                vehicle.color,
                vehicle.vehicle_type,
                driver.height_cm,
                json.dumps(driver.face_embedding) if driver.face_embedding else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()
