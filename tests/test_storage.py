import sys
import json
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import storage
from src.models import Track, VehicleInfo, DriverInfo, AccidentEvent


def test_save_track_and_save_event_persist_rows():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test.db"

    track = Track(track_id=1, camera_id="cam1", bbox=(0, 0, 10, 10), world_pos=(1.5, 2.5))
    storage.save_track(track)

    event = AccidentEvent(camera_id="cam1", timestamp=123.0, track_ids=[1, 2])
    vehicle = VehicleInfo(track_id=1, plate="51F12345", color="red", vehicle_type="car")
    driver = DriverInfo(track_id=1, height_cm=170.0, face_embedding=[0.1, 0.2])
    storage.save_event(event, vehicle, driver)

    conn = sqlite3.connect(storage._DB_PATH)
    tracks = conn.execute("SELECT track_id, camera_id, world_x, world_y FROM suspect_tracks").fetchall()
    events = conn.execute("SELECT camera_id, track_ids, vehicle_plate FROM accident_events").fetchall()
    conn.close()

    assert tracks == [(1, "cam1", 1.5, 2.5)]
    assert events[0][0] == "cam1"
    assert json.loads(events[0][1]) == [1, 2]
    assert events[0][2] == "51F12345"


def test_find_person_sightings_filters_by_person_camera_and_time():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test_sightings.db"

    storage.save_track(Track(track_id=1, camera_id="camA", bbox=(0, 0, 10, 10), person_id=42, timestamp=10.0))
    storage.save_track(Track(track_id=2, camera_id="camB", bbox=(0, 0, 10, 10), person_id=42, timestamp=20.0))
    storage.save_track(Track(track_id=3, camera_id="camB", bbox=(0, 0, 10, 10), person_id=42, timestamp=5.0))
    storage.save_track(Track(track_id=4, camera_id="camB", bbox=(0, 0, 10, 10), person_id=99, timestamp=20.0))
    storage.save_track(Track(track_id=5, camera_id="camC", bbox=(0, 0, 10, 10), person_id=42, timestamp=20.0))

    sightings = storage.find_person_sightings(42, ["camB", "camC"], since_timestamp=15.0)

    assert [s["track_id"] for s in sightings] == [2, 5]


def test_save_camera_and_list_cameras_upserts():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test_cameras.db"

    storage.save_camera("camA", lat=10.0, lng=106.0, facing_deg=0, fov_deg=90)
    storage.save_camera("camA", lat=10.1, lng=106.1, facing_deg=180, fov_deg=60)  # update cùng id

    cameras = storage.list_cameras()

    assert cameras == [{"camera_id": "camA", "lat": 10.1, "lng": 106.1, "facing_deg": 180, "fov_deg": 60}]


def test_get_connection_migrates_old_schema_missing_columns():
    # giả lập DB cũ tạo trước khi có cột person_id/timestamp (đúng bug thật gặp phải
    # khi chạy scripts/draw_person_path.py trên data/tracking.db có sẵn)
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "old_schema.db"
    conn = sqlite3.connect(storage._DB_PATH)
    conn.execute(
        """CREATE TABLE suspect_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER NOT NULL,
            camera_id TEXT NOT NULL,
            world_x REAL,
            world_y REAL
        )"""
    )
    conn.commit()
    conn.close()

    storage.save_track(Track(track_id=1, camera_id="cam1", bbox=(0, 0, 10, 10), person_id=7, timestamp=5.0))

    conn = sqlite3.connect(storage._DB_PATH)
    row = conn.execute("SELECT track_id, person_id, timestamp FROM suspect_tracks").fetchone()
    conn.close()

    assert row == (1, 7, 5.0)


def test_find_person_track_history_returns_all_cameras_ordered_by_time():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test_history.db"

    storage.save_track(Track(track_id=1, camera_id="camA", bbox=(0, 0, 10, 10), person_id=5, timestamp=20.0))
    storage.save_track(Track(track_id=2, camera_id="camB", bbox=(0, 0, 10, 10), person_id=5, timestamp=10.0))
    storage.save_track(Track(track_id=3, camera_id="camA", bbox=(0, 0, 10, 10), person_id=99, timestamp=15.0))

    history = storage.find_person_track_history(5)

    assert [h["track_id"] for h in history] == [2, 1]  # sắp theo timestamp, chỉ đúng person_id


if __name__ == "__main__":
    test_save_track_and_save_event_persist_rows()
    test_find_person_sightings_filters_by_person_camera_and_time()
    test_save_camera_and_list_cameras_upserts()
    test_get_connection_migrates_old_schema_missing_columns()
    test_find_person_track_history_returns_all_cameras_ordered_by_time()
    print("OK")
