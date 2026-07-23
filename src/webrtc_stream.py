import asyncio
import json

import av
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack

from . import ingest, detection, tracking, cross_camera, storage
from .main import _DETECT_INTERVAL, _extrapolate_tracks
from .models import Frame, Track

# giữ tham chiếu các peer connection đang mở, tránh bị garbage-collect giữa chừng
_active_connections: set[RTCPeerConnection] = set()


class CameraTrack(VideoStreamTrack):
    """Video track chạy detect+track+ghép person_id trên 1 nguồn video, lặp lại
    từ đầu khi hết (demo khi chưa có camera/RTSP thật). Đẩy metadata track (bbox,
    class_id, person_id) qua data_channel kèm mỗi frame để browser vẽ overlay +
    click chọn người."""

    def __init__(self, camera_id: str, source: str):
        super().__init__()
        self.camera_id = camera_id
        self.source = source
        self.data_channel = None
        self._frame_count = 0
        self._last_real_tracks: list[Track] = []
        ingest.register_camera_source(camera_id, source)

    async def recv(self):
        pts, time_base = await self.next_timestamp()

        # detect+track+save_track (+ face embedding) là CPU/GPU-bound đồng bộ -> chạy trong
        # thread riêng (asyncio.to_thread) thay vì trực tiếp trong recv(), tránh block toàn
        # bộ event loop của FastAPI (WebSocket /ws/events, request khác) trong lúc xử lý.
        frame, tracks = await asyncio.to_thread(self._process_frame)

        if self.data_channel is not None and self.data_channel.readyState == "open":
            payload = [
                {"track_id": t.track_id, "class_id": t.class_id, "person_id": t.person_id, "bbox": t.bbox}
                for t in tracks
            ]
            self.data_channel.send(json.dumps(payload))

        video_frame = av.VideoFrame.from_ndarray(frame.image, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

    def _process_frame(self) -> tuple[Frame, list[Track]]:
        frame = ingest.read_frame(self.camera_id)
        if frame is None:
            ingest.reset_camera(self.camera_id)  # lặp lại từ đầu
            frame = ingest.read_frame(self.camera_id)

        # detect_objects (YOLO) đồng bộ mất ~57ms/frame, không theo kịp nhịp phát ~30fps
        # cố định của aiortc (VideoStreamTrack.next_timestamp) -> giật hình. Áp dụng cùng
        # frame-skip detection như main.py: chỉ detect thật mỗi _DETECT_INTERVAL frame.
        remainder = self._frame_count % _DETECT_INTERVAL
        if remainder == 0:
            tracks = tracking.update_tracks(self.camera_id, detection.detect_objects(frame))
            self._last_real_tracks = tracks
        else:
            tracks = _extrapolate_tracks(self.camera_id, self._last_real_tracks, remainder / _DETECT_INTERVAL)
        self._frame_count += 1

        for track in tracks:
            track.timestamp = frame.timestamp
            if track.class_id == "person":
                cross_camera.resolve_global_identity(track, frame)
            storage.save_track(track)
        return frame, tracks


async def build_answer(camera_id: str, source: str, offer_sdp: str, offer_type: str) -> tuple[str, str]:
    """Nhận SDP offer từ browser, trả về SDP answer (signaling qua 1 HTTP request)."""
    pc = RTCPeerConnection()
    _active_connections.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "closed"):
            _active_connections.discard(pc)
            await pc.close()

    camera_track = CameraTrack(camera_id, source)
    pc.addTrack(camera_track)

    @pc.on("datachannel")
    def on_datachannel(channel):
        camera_track.data_channel = channel

    offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return pc.localDescription.sdp, pc.localDescription.type
