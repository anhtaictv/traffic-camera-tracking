import argparse
import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":  # console Windows mặc định cp1252, không in được tiếng Việt
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import storage, camera_registry

_HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Lo trinh person __PERSON_ID__</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body, #map { height: 100%; margin: 0; }
  .arrow-icon { font-size: 28px; color: #e11; transform-origin: center; }
</style>
</head>
<body>
<div id="map"></div>
<script>
  const points = __POINTS_JSON__;
  const bearing = __BEARING_JSON__;
  const map = L.map('map').setView([__CENTER_LAT__, __CENTER_LNG__], 16);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap'
  }).addTo(map);

  const latlngs = points.map(function (p) { return [p.lat, p.lng]; });
  if (latlngs.length > 1) {
    L.polyline(latlngs, { color: '#3388ff', weight: 3 }).addTo(map);
  }

  points.forEach(function (p, i) {
    const color = i === 0 ? '#2ecc71' : (i === points.length - 1 ? '#e74c3c' : '#3388ff');
    L.circleMarker([p.lat, p.lng], { radius: 8, color: color, fillColor: color, fillOpacity: 1 })
      .bindPopup('#' + (i + 1) + ' - camera ' + p.camera_id + '<br>' + new Date(p.timestamp * 1000).toLocaleString())
      .addTo(map);
  });

  if (bearing !== null && points.length) {
    const last = points[points.length - 1];
    L.marker([last.lat, last.lng], {
      icon: L.divIcon({
        className: '',
        html: '<div class="arrow-icon" style="transform: rotate(' + bearing + 'deg)">&#8593;</div>'
      })
    }).addTo(map);
  }

  if (latlngs.length) {
    map.fitBounds(latlngs, { padding: [50, 50] });
  }
</script>
</body>
</html>
"""


def _hydrate_camera_registry() -> None:
    """Nạp camera đã đăng ký GIS từ DB vào camera_registry — module này chạy độc lập,
    không qua api.py nên phải tự hydrate."""
    for cam in storage.list_cameras():
        camera_registry.register_camera(
            cam["camera_id"], cam["lat"], cam["lng"], cam["facing_deg"], cam["fov_deg"]
        )


def build_path_points(person_id: int) -> list[dict]:
    """Lịch sử track của person_id, quy đổi world_pos cục bộ -> lat/lng thật. Bỏ qua
    điểm ở camera chưa đăng ký GIS hoặc chưa có world_pos."""
    points = []
    for row in storage.find_person_track_history(person_id):
        if row["world_x"] is None or row["world_y"] is None:
            continue
        try:
            lat, lng = camera_registry.local_to_latlng(row["camera_id"], row["world_x"], row["world_y"])
        except ValueError:
            continue
        points.append({**row, "lat": lat, "lng": lng})
    return points


def render_html(person_id: int, points: list[dict]) -> str:
    """Sinh HTML standalone (Leaflet + OSM qua CDN) vẽ lộ trình + mũi tên hướng đi hiện tại."""
    arrow_bearing = None
    if len(points) >= 2:
        p1, p2 = points[-2], points[-1]
        arrow_bearing = camera_registry._bearing_deg(p1["lat"], p1["lng"], p2["lat"], p2["lng"])

    center = points[len(points) // 2] if points else {"lat": 0.0, "lng": 0.0}

    html = _HTML_TEMPLATE
    html = html.replace("__PERSON_ID__", str(person_id))
    html = html.replace("__POINTS_JSON__", json.dumps(points))
    html = html.replace("__BEARING_JSON__", json.dumps(arrow_bearing))
    html = html.replace("__CENTER_LAT__", str(center["lat"]))
    html = html.replace("__CENTER_LNG__", str(center["lng"]))
    return html


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vẽ lộ trình 1 person_id lên bản đồ thật (OSM)")
    parser.add_argument("person_id", type=int)
    parser.add_argument("--output", default="person_path.html")
    args = parser.parse_args()

    _hydrate_camera_registry()
    points = build_path_points(args.person_id)
    Path(args.output).write_text(render_html(args.person_id, points), encoding="utf-8")
    print(f"Đã ghi {len(points)} điểm vào {args.output}")
