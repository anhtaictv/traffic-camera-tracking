import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import camera_registry


def _setup_cameras():
    camera_registry.register_camera("camA", lat=10.0, lng=106.0, facing_deg=0)
    # camB: ~555m thẳng bắc của A, quay mặt về nam (nhìn lại A)
    camera_registry.register_camera("camB", lat=10.005, lng=106.0, facing_deg=180)
    # camC: ~547m thẳng đông của A, quay mặt về bắc (không nhìn lại A)
    camera_registry.register_camera("camC", lat=10.0, lng=106.005, facing_deg=0)
    # camD: ~333m thẳng bắc của A (gần hơn B) nhưng quay mặt về bắc (quay lưng với A)
    camera_registry.register_camera("camD", lat=10.003, lng=106.0, facing_deg=0)


def test_nearby_cameras_by_distance_only():
    _setup_cameras()

    results = camera_registry.nearby_cameras("camA", radius_m=1000)
    ids = [camera_id for camera_id, _ in results]

    assert set(ids) == {"camB", "camC", "camD"}
    # sắp theo khoảng cách tăng dần
    distances = [d for _, d in results]
    assert distances == sorted(distances)


def test_nearby_cameras_with_travel_bearing_filters_by_direction_and_facing():
    _setup_cameras()

    # người đi về hướng Bắc (bearing 0) khi rời camA
    results = camera_registry.nearby_cameras("camA", radius_m=1000, travel_bearing_deg=0)
    ids = [camera_id for camera_id, _ in results]

    # camC bị loại vì lệch hướng (ở hướng Đông); camD bị loại vì quay lưng với camA
    assert ids == ["camB"]


def test_unregistered_camera_raises():
    try:
        camera_registry.nearby_cameras("camera_never_registered", radius_m=1000)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_local_to_latlng_no_offset_returns_camera_position():
    camera_registry.register_camera("camL", lat=10.0, lng=106.0, facing_deg=0)

    lat, lng = camera_registry.local_to_latlng("camL", 0.0, 0.0)

    assert abs(lat - 10.0) < 1e-9
    assert abs(lng - 106.0) < 1e-9


def test_local_to_latlng_matches_haversine_distance():
    camera_registry.register_camera("camL2", lat=10.0, lng=106.0, facing_deg=0)

    lat, lng = camera_registry.local_to_latlng("camL2", world_x=0.0, world_y=1000.0)  # 1000m về Bắc
    distance = camera_registry._haversine_m(10.0, 106.0, lat, lng)

    assert abs(distance - 1000.0) < 1.0
    assert lat > 10.0  # đi về Bắc -> lat tăng


def test_local_to_latlng_unregistered_camera_raises():
    try:
        camera_registry.local_to_latlng("camera_never_registered", 0, 0)
        assert False, "expected ValueError"
    except ValueError:
        pass


if __name__ == "__main__":
    test_nearby_cameras_by_distance_only()
    test_nearby_cameras_with_travel_bearing_filters_by_direction_and_facing()
    test_unregistered_camera_raises()
    test_local_to_latlng_no_offset_returns_camera_position()
    test_local_to_latlng_matches_haversine_distance()
    test_local_to_latlng_unregistered_camera_raises()
    print("OK")
