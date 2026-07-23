import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import storage
from src.models import Track, VehicleInfo, DriverInfo, AccidentEvent
from src.api import app


def test_list_tracks_and_events_return_seeded_rows():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
    storage.save_track(Track(track_id=1, camera_id="cam1", bbox=(0, 0, 10, 10), world_pos=(1.0, 2.0)))
    storage.save_event(
        AccidentEvent(camera_id="cam1", timestamp=100.0, track_ids=[1]),
        VehicleInfo(track_id=1, plate="51F12345", vehicle_type="car"),
        DriverInfo(track_id=1, height_cm=170.0),
    )

    client = TestClient(app)
    tracks = client.get("/api/tracks").json()
    events = client.get("/api/events").json()

    assert tracks == [{"track_id": 1, "camera_id": "cam1", "world_x": 1.0, "world_y": 2.0}]
    assert events[0]["vehicle_plate"] == "51F12345"
    assert events[0]["track_ids"] == [1]


def test_websocket_pushes_new_event():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test_ws.db"

    client = TestClient(app)
    with client.websocket_connect("/ws/events") as ws:
        storage.save_event(
            AccidentEvent(camera_id="camX", timestamp=200.0, track_ids=[9]),
            VehicleInfo(track_id=9, plate="30A99999"),
            DriverInfo(track_id=9),
        )
        message = ws.receive_json()

    assert message["camera_id"] == "camX"
    assert message["vehicle_plate"] == "30A99999"


def test_upsert_camera_persists_and_lists():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test_cameras.db"

    client = TestClient(app)
    resp = client.post(
        "/api/cameras", json={"camera_id": "camA", "lat": 10.0, "lng": 106.0, "facing_deg": 90, "fov_deg": 60}
    )
    assert resp.status_code == 200

    cameras = client.get("/api/cameras").json()
    assert cameras == [{"camera_id": "camA", "lat": 10.0, "lng": 106.0, "facing_deg": 90, "fov_deg": 60}]


def test_person_sightings_falls_back_to_same_camera_when_not_gis_registered():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test_sightings.db"
    storage.save_track(Track(track_id=1, camera_id="cam_no_gis", bbox=(0, 0, 10, 10), person_id=5, timestamp=1.0))

    client = TestClient(app)
    resp = client.get("/api/persons/5/sightings", params={"camera_id": "cam_no_gis"})

    assert resp.status_code == 200
    assert resp.json()[0]["track_id"] == 1


if __name__ == "__main__":
    test_list_tracks_and_events_return_seeded_rows()
    test_websocket_pushes_new_event()
    test_upsert_camera_persists_and_lists()
    test_person_sightings_falls_back_to_same_camera_when_not_gis_registered()
    print("OK")
