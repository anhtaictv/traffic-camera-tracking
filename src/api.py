import asyncio
import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import camera_registry, storage, webrtc_stream
from .storage import _get_connection

app = FastAPI()
# ponytail: CORS mở toàn bộ để dashboard dev (Vite) gọi được -> siết lại origin cụ thể
# khi deploy thật.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# hydrate camera_registry (RAM) từ DB lúc khởi động app, để cameras đã lưu vẫn còn sau restart
for _cam in storage.list_cameras():
    camera_registry.register_camera(
        _cam["camera_id"], _cam["lat"], _cam["lng"], _cam["facing_deg"], _cam["fov_deg"]
    )


class CameraIn(BaseModel):
    camera_id: str
    lat: float
    lng: float
    facing_deg: float
    fov_deg: float = 90.0


class WebRTCOfferIn(BaseModel):
    camera_id: str
    source: str
    sdp: str
    type: str

_EVENT_COLUMNS = (
    "id, camera_id, timestamp, track_ids, vehicle_plate, vehicle_color, "
    "vehicle_type, driver_height_cm"
)


def _event_row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0],
        "camera_id": row[1],
        "timestamp": row[2],
        "track_ids": json.loads(row[3]),
        "vehicle_plate": row[4],
        "vehicle_color": row[5],
        "vehicle_type": row[6],
        "driver_height_cm": row[7],
    }


@app.get("/api/tracks")
def list_tracks(limit: int = 200) -> list[dict]:
    """Danh sách track gần nhất có world_pos (để vẽ lên map)."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT track_id, camera_id, world_x, world_y FROM suspect_tracks "
            "WHERE world_x IS NOT NULL ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [{"track_id": r[0], "camera_id": r[1], "world_x": r[2], "world_y": r[3]} for r in rows]


@app.get("/api/events")
def list_events(limit: int = 50) -> list[dict]:
    """Danh sách accident event gần nhất."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            f"SELECT {_EVENT_COLUMNS} FROM accident_events ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [_event_row_to_dict(r) for r in rows]


@app.get("/api/cameras")
def list_cameras() -> list[dict]:
    """Danh sách camera đã đăng ký (vị trí GIS + góc nhìn)."""
    return storage.list_cameras()


@app.post("/api/cameras")
def upsert_camera(camera: CameraIn) -> dict:
    """Thêm/sửa vị trí GIS + góc nhìn 1 camera (dùng cho map cấu hình camera)."""
    camera_registry.register_camera(
        camera.camera_id, camera.lat, camera.lng, camera.facing_deg, camera.fov_deg
    )
    storage.save_camera(camera.camera_id, camera.lat, camera.lng, camera.facing_deg, camera.fov_deg)
    return {"ok": True}


@app.get("/api/persons/{person_id}/sightings")
def person_sightings(person_id: int, camera_id: str, radius_m: float = 500.0) -> list[dict]:
    """Nơi 1 person_id từng xuất hiện, ở camera hiện tại + camera GIS gần đó (nếu có đăng ký GIS)."""
    try:
        nearby = camera_registry.nearby_cameras(camera_id, radius_m)
    except ValueError:
        nearby = []  # camera chưa đăng ký GIS -> chỉ tìm trong đúng camera này
    camera_ids = [camera_id] + [c for c, _ in nearby]
    return storage.find_person_sightings(person_id, camera_ids, since_timestamp=0.0)


@app.post("/webrtc/offer")
async def webrtc_offer(offer: WebRTCOfferIn) -> dict:
    """Signaling WebRTC: nhận SDP offer từ browser cho 1 camera, trả về SDP answer."""
    sdp, type_ = await webrtc_stream.build_answer(offer.camera_id, offer.source, offer.sdp, offer.type)
    return {"sdp": sdp, "type": type_}


@app.websocket("/ws/events")
async def stream_events(websocket: WebSocket) -> None:
    """Đẩy accident event mới cho client mỗi ~1s."""
    # ponytail: poll DB thay vì pub/sub thật -> đủ cho 1 dashboard/demo,
    # nâng cấp lên message queue (Kafka/RabbitMQ, roadmap Phase 0) khi nhiều client/camera.
    await websocket.accept()
    conn = _get_connection()
    last_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM accident_events").fetchone()[0]
    conn.close()

    try:
        while True:
            conn = _get_connection()
            rows = conn.execute(
                f"SELECT {_EVENT_COLUMNS} FROM accident_events WHERE id > ? ORDER BY id",
                (last_id,),
            ).fetchall()
            conn.close()

            for row in rows:
                last_id = row[0]
                await websocket.send_json(_event_row_to_dict(row))

            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass
