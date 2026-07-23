import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from src import storage, camera_registry
from src.models import Track
from draw_person_path import build_path_points, render_html


def test_build_path_points_converts_world_pos_to_latlng():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test.db"
    camera_registry.register_camera("camPath", lat=10.0, lng=106.0, facing_deg=0)

    storage.save_track(
        Track(track_id=1, camera_id="camPath", bbox=(0, 0, 10, 10), person_id=5, world_pos=(0.0, 0.0), timestamp=1.0)
    )
    storage.save_track(
        Track(
            track_id=2, camera_id="camPath", bbox=(0, 0, 10, 10), person_id=5, world_pos=(0.0, 100.0), timestamp=2.0
        )
    )

    points = build_path_points(5)

    assert len(points) == 2
    assert abs(points[0]["lat"] - 10.0) < 1e-9
    assert points[1]["lat"] > points[0]["lat"]  # đi về hướng Bắc -> lat tăng


def test_build_path_points_skips_camera_without_gis():
    storage._DB_PATH = Path(tempfile.mkdtemp()) / "test2.db"
    storage.save_track(
        Track(
            track_id=1,
            camera_id="cam_no_gis_path",
            bbox=(0, 0, 10, 10),
            person_id=9,
            world_pos=(0.0, 0.0),
            timestamp=1.0,
        )
    )

    assert build_path_points(9) == []


def test_render_html_embeds_points_and_bearing():
    points = [
        {"track_id": 1, "camera_id": "camPath", "world_x": 0.0, "world_y": 0.0, "timestamp": 1.0, "lat": 10.0, "lng": 106.0},
        {"track_id": 2, "camera_id": "camPath", "world_x": 0.0, "world_y": 100.0, "timestamp": 2.0, "lat": 10.0009, "lng": 106.0},
    ]

    html = render_html(5, points)

    assert "camPath" in html
    assert "L.polyline" in html
    assert "arrow-icon" in html
    assert "null" not in html.split("const bearing = ")[1].split(";")[0]


if __name__ == "__main__":
    test_build_path_points_converts_world_pos_to_latlng()
    test_build_path_points_skips_camera_without_gis()
    test_render_html_embeds_points_and_bearing()
    print("OK")
