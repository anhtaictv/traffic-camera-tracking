import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import storage, camera_registry
from src.models import Track
from src.person_search import search_departed_person


def test_search_departed_person_finds_sighting_at_nearby_camera():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
    camera_registry.register_camera("camA", lat=10.0, lng=106.0, facing_deg=0)
    camera_registry.register_camera("camB", lat=10.003, lng=106.0, facing_deg=180)  # ~333m bắc, gần

    storage.save_track(Track(track_id=9, camera_id="camB", bbox=(0, 0, 10, 10), person_id=42, timestamp=20.0))

    departed = Track(track_id=1, camera_id="camA", bbox=(0, 0, 10, 10), person_id=42, timestamp=10.0)
    results = search_departed_person(departed, radius_m=1000)

    assert len(results) == 1
    assert results[0]["camera_id"] == "camB"
    assert results[0]["track_id"] == 9


def test_search_departed_person_without_person_id_returns_empty():
    departed = Track(track_id=1, camera_id="camA", bbox=(0, 0, 10, 10), person_id=None)
    assert search_departed_person(departed) == []


def test_travel_bearing_narrows_search_to_cameras_in_that_direction():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test_bearing.db"
    camera_registry.register_camera("origin", lat=10.0, lng=106.0, facing_deg=0)
    # camNorth: ~555m bắc, quay mặt về nam (nhìn lại origin) -> khớp khi travel_bearing=0
    camera_registry.register_camera("camNorth", lat=10.005, lng=106.0, facing_deg=180)
    # camEast: ~547m đông, quay mặt về bắc -> lệch hướng khi travel_bearing=0 (đi về Bắc)
    camera_registry.register_camera("camEast", lat=10.0, lng=106.005, facing_deg=0)

    storage.save_track(Track(track_id=1, camera_id="camNorth", bbox=(0, 0, 10, 10), person_id=77, timestamp=20.0))
    storage.save_track(Track(track_id=2, camera_id="camEast", bbox=(0, 0, 10, 10), person_id=77, timestamp=20.0))

    no_bearing = Track(track_id=9, camera_id="origin", bbox=(0, 0, 10, 10), person_id=77, timestamp=10.0)
    with_bearing = Track(
        track_id=9, camera_id="origin", bbox=(0, 0, 10, 10), person_id=77, timestamp=10.0, travel_bearing_deg=0.0
    )

    results_no_bearing = search_departed_person(no_bearing, radius_m=1000)
    results_with_bearing = search_departed_person(with_bearing, radius_m=1000)

    assert {r["camera_id"] for r in results_no_bearing} == {"camNorth", "camEast"}
    assert {r["camera_id"] for r in results_with_bearing} == {"camNorth"}


if __name__ == "__main__":
    test_search_departed_person_finds_sighting_at_nearby_camera()
    test_search_departed_person_without_person_id_returns_empty()
    test_travel_bearing_narrows_search_to_cameras_in_that_direction()
    print("OK")
