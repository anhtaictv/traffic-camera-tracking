import math

_EARTH_RADIUS_M = 6371000.0

_cameras: dict[str, dict] = {}


def register_camera(camera_id: str, lat: float, lng: float, facing_deg: float, fov_deg: float = 90.0) -> None:
    """Đăng ký vị trí GIS + góc nhìn của 1 camera (facing_deg: 0=Bắc, 90=Đông, ...)."""
    _cameras[camera_id] = {"lat": lat, "lng": lng, "facing_deg": facing_deg % 360, "fov_deg": fov_deg}


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _bearing_deg(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lng2 - lng1)
    x = math.sin(dlambda) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def local_to_latlng(camera_id: str, world_x: float, world_y: float) -> tuple[float, float]:
    """Quy đổi tọa độ local (world_x=Đông, world_y=Bắc, mét) từ calibration.pixel_to_world
    sang lat/lng thật -> gốc tọa độ local (0,0) được coi là trùng vị trí GIS của camera."""
    camera = _cameras.get(camera_id)
    if camera is None:
        raise ValueError(f"Camera {camera_id} chưa được đăng ký, gọi register_camera trước")

    dlat = math.degrees(world_y / _EARTH_RADIUS_M)
    dlng = math.degrees(world_x / (_EARTH_RADIUS_M * math.cos(math.radians(camera["lat"]))))
    return (camera["lat"] + dlat, camera["lng"] + dlng)


def nearby_cameras(
    camera_id: str, radius_m: float, travel_bearing_deg: float | None = None
) -> list[tuple[str, float]]:
    """Camera khác trong bán kính radius_m quanh camera_id, sắp theo khoảng cách gần nhất.
    Nếu có travel_bearing_deg (hướng người đang di chuyển khi rời camera_id): chỉ giữ
    camera lệch không quá 45° so với hướng đó, và có góc nhìn (facing_deg ± fov_deg/2)
    bao phủ đường quay lại camera_id (tức có khả năng nhìn thấy người đi tới)."""
    origin = _cameras.get(camera_id)
    if origin is None:
        raise ValueError(f"Camera {camera_id} chưa được đăng ký, gọi register_camera trước")

    results = []
    for other_id, other in _cameras.items():
        if other_id == camera_id:
            continue
        distance = _haversine_m(origin["lat"], origin["lng"], other["lat"], other["lng"])
        if distance > radius_m:
            continue

        if travel_bearing_deg is not None:
            bearing_to_other = _bearing_deg(origin["lat"], origin["lng"], other["lat"], other["lng"])
            if _angle_diff(bearing_to_other, travel_bearing_deg) > 45:
                continue
            bearing_back_to_origin = (bearing_to_other + 180) % 360
            if _angle_diff(other["facing_deg"], bearing_back_to_origin) > other["fov_deg"] / 2:
                continue

        results.append((other_id, distance))

    results.sort(key=lambda r: r[1])
    return results
